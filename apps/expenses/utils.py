from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
from django.utils.translation import gettext as _
try:
    from xhtml2pdf import pisa
except ImportError:
    pisa = None
from django.conf import settings
import os
import logging
try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    pdfmetrics = None
    TTFont = None

logger = logging.getLogger(__name__)

def render_to_pdf(template_src, context_dict={}):
    if pisa is None:
        return HttpResponse(
            _("PDF generation is temporarily unavailable due to server compatibility issues. Please contact admin."),
            status=503,
        )

    # Register Persian font
    if pdfmetrics:
        try:
            font_path = os.path.join(str(settings.BASE_DIR), 'static', 'fonts', 'IRANYekanWebRegular.ttf')
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('IranYekan', font_path))
            else:
                logger.debug("Font file not found at %s", font_path)
        except Exception as e:
            # Ignore if already registered
            pass

    template = get_template(template_src)
    html  = template.render(context_dict)
    result = BytesIO()
    
    # Handle static files for xhtml2pdf
    def link_callback(uri, rel):
        """
        Convert HTML URIs to absolute system paths so xhtml2pdf can access those resources
        """
        sUrl = settings.STATIC_URL        # Typically /static/
        sRoot = str(settings.STATIC_ROOT) # Typically /home/userX/project/static/
        mUrl = settings.MEDIA_URL         # Typically /media/
        mRoot = str(settings.MEDIA_ROOT)  # Typically /home/userX/project/media/

        # Ensure sUrl starts with / for consistent matching
        if not sUrl.startswith('/'):
            sUrl = '/' + sUrl
            
        # Ensure mUrl starts with / for consistent matching
        if not mUrl.startswith('/'):
            mUrl = '/' + mUrl

        if uri.startswith(mUrl):
            path = os.path.join(mRoot, uri.replace(mUrl, ""))
        elif uri.startswith(sUrl):
            path = os.path.join(sRoot, uri.replace(sUrl, ""))
            
            # Check if file exists in STATIC_ROOT, if not check STATICFILES_DIRS
            if not os.path.isfile(path):
                if hasattr(settings, 'STATICFILES_DIRS'):
                    for static_dir in settings.STATICFILES_DIRS:
                        static_dir = str(static_dir)
                        possible_path = os.path.join(static_dir, uri.replace(sUrl, ""))
                        if os.path.isfile(possible_path):
                            path = possible_path
                            break
        else:
            return uri

        # make sure that file exists
        if not os.path.isfile(path):
             # Fallback: if path construction failed, try to find it in STATICFILES_DIRS manually
             # assuming uri matches a static file pattern
             if '/static/' in uri:
                 relative_path = uri.split('/static/')[-1]
                 if hasattr(settings, 'STATICFILES_DIRS'):
                    for static_dir in settings.STATICFILES_DIRS:
                        static_dir = str(static_dir)
                        possible_path = os.path.join(static_dir, relative_path)
                        if os.path.isfile(possible_path):
                            return possible_path
            
             # If still not found, print debug info
             logger.debug("File not found in link_callback. URI: %s, Path: %s", uri, path)
             # We don't raise exception here to allow other resources to load if possible, 
             # but for fonts it will likely fail later.
             # raise Exception('media URI must start with %s or %s' % (sUrl, mUrl))

        return path

    # For Farsi/Arabic support, we use UTF-8 encoding.
    # xhtml2pdf requires a font that supports these characters (e.g. DejaVuSans) in the CSS.
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result, link_callback=link_callback)
    
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None


def extract_receipt_data(image_path):
    """
    Extract data from receipt image using OCR
    """
    try:
        import pytesseract
        from PIL import Image
        import re
    except ImportError:
        return {
            'error': 'OCR functionality is not available. Please install pytesseract and Pillow.',
            'merchant': '',
            'amount': '',
            'date': '',
            'description': ''
        }
    
    try:
        # Open image
        image = Image.open(image_path)
        
        # Extract text using OCR
        text = pytesseract.image_to_string(image)
        
        # Extract merchant (first line or company name pattern)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        merchant = lines[0] if lines else ''
        
        # Extract amount (look for currency patterns)
        amount_patterns = [
            r'[\$£€]\s*\d+\.?\d*',  # $123.45
            r'\d+\.?\d*\s*[\$£€]',  # 123.45$
            r'OMR\s*\d+\.?\d*',      # OMR 123.45
            r'\d+\.?\d*\s*OMR',      # 123.45 OMR
            r'Total[:\s]*\d+\.?\d*', # Total: 123.45
            r'Amount[:\s]*\d+\.?\d*' # Amount: 123.45
        ]
        
        amount = ''
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount = match.group()
                break
        
        # Extract date (common date patterns)
        date_patterns = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # 12/31/2023
            r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',  # 2023/12/31
            r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2,4}',  # 31 Dec 2023
        ]
        
        date = ''
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date = match.group()
                break
        
        # Generate description from first few lines
        description = ' '.join(lines[:3]) if len(lines) >= 3 else ' '.join(lines)
        
        return {
            'merchant': merchant,
            'amount': amount,
            'date': date,
            'description': description,
            'raw_text': text
        }
        
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return {
            'error': f'OCR extraction failed: {str(e)}',
            'merchant': '',
            'amount': '',
            'date': '',
            'description': ''
        }
