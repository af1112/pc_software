try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from PIL import Image
except ImportError:
    try:
        import Image
    except ImportError:
        Image = None
import re
import os
import logging
import json
import base64
import mimetypes
import shutil
from decimal import Decimal, InvalidOperation
from datetime import datetime
import requests

logger = logging.getLogger(__name__)

# If Tesseract is not in PATH, set it here. 
tesseract_path_user = os.path.expandvars(r'%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe')
tesseract_path_program_files = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

if pytesseract:
    if os.path.exists(tesseract_path_user):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path_user
    elif os.path.exists(tesseract_path_program_files):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path_program_files

def detect_category(text):
    """
    Detects expense category based on keywords in the text.
    """
    text = text.lower()
    categories = {
        'Food': ['restaurant', 'cafe', 'coffee', 'burger', 'pizza', 'dining', 'lunch', 'dinner', 'food', 'bakery', 'kitchen'],
        'Transport': ['taxi', 'uber', 'cab', 'fuel', 'petrol', 'gas', 'station', 'parking', 'flight', 'airline', 'ticket', 'transport', 'train', 'bus'],
        'Accommodation': ['hotel', 'motel', 'stay', 'inn', 'resort', 'booking', 'airbnb', 'room'],
        'Material': ['hardware', 'tools', 'equipment', 'supply', 'cement', 'steel', 'paint', 'building', 'material'],
        'Communication': ['telecom', 'internet', 'wifi', 'phone', 'mobile', 'data', 'omantel', 'ooredoo'],
        'Office Supplies': ['stationery', 'paper', 'print', 'ink', 'toner', 'pen', 'notebook'],
    }

    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in text:
                return category
    
    return 'General' # Default


def _ocr_available():
    if pytesseract is None or Image is None:
        return False
    tesseract_cmd = getattr(getattr(pytesseract, 'pytesseract', None), 'tesseract_cmd', '')
    if tesseract_cmd and os.path.exists(tesseract_cmd):
        return True
    return shutil.which(tesseract_cmd or 'tesseract') is not None


def _to_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_date_value(date_value):
    normalized = _to_text(date_value)
    if not normalized:
        return None

    normalized = normalized.replace('/', '-')
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%m-%d-%Y', '%d-%m-%y', '%m-%d-%y'):
        try:
            return datetime.strptime(normalized, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


def _ai_receipt_provider():
    return os.environ.get('AI_RECEIPT_PROVIDER', 'openai').strip().lower()


def _extract_with_openai_vision(image_path):
    api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not api_key:
        return None
    if _ai_receipt_provider() != 'openai':
        return None

    model = os.environ.get('OPENAI_RECEIPT_MODEL', 'gpt-4o')
    mime_type, _ = mimetypes.guess_type(image_path)
    mime_type = mime_type or 'image/jpeg'

    with open(image_path, 'rb') as image_file:
        image_b64 = base64.b64encode(image_file.read()).decode('utf-8')

    prompt = (
        "Extract receipt data and respond as JSON with keys: "
        "date (YYYY-MM-DD or null), amount (number or null), merchant (string or null), "
        "category (string or null), description (string or null), reference_number (string or null), "
        "currency (3-letter code or null), confidence (0..1), raw_text (string or null). "
        "Rules: amount must be total payable amount, not tax line. "
        "If uncertain, set value to null."
    )

    response = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': model,
            'response_format': {'type': 'json_object'},
            'messages': [
                {
                    'role': 'system',
                    'content': 'You are an accurate OCR and receipt information extraction engine.',
                },
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': prompt},
                        {'type': 'image_url', 'image_url': {'url': f'data:{mime_type};base64,{image_b64}'}},
                    ],
                },
            ],
            'temperature': 0,
        },
        timeout=60,
    )
    response.raise_for_status()

    payload = response.json()
    content = payload.get('choices', [{}])[0].get('message', {}).get('content')
    if not content:
        return None

    parsed = json.loads(content)
    amount = _normalize_amount(str(parsed.get('amount'))) if parsed.get('amount') is not None else None

    return {
        'date': _normalize_date_value(parsed.get('date')),
        'amount': float(amount) if amount is not None else None,
        'description': _to_text(parsed.get('description')),
        'category': _to_text(parsed.get('category')),
        'merchant': _to_text(parsed.get('merchant')),
        'reference_number': _to_text(parsed.get('reference_number')),
        'currency': _to_text(parsed.get('currency')),
        'raw_text': _to_text(parsed.get('raw_text')) or '',
        'confidence': max(0.0, min(float(parsed.get('confidence') or 0.9), 1.0)),
        'error': None,
    }


def _normalize_amount(amount_str):
    cleaned = amount_str.replace(',', '').strip()
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _extract_date(text):
    date_candidates = re.findall(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})', text)
    for candidate in date_candidates:
        normalized = candidate.replace('/', '-')
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%m-%d-%Y', '%d-%m-%y', '%m-%d-%y'):
            try:
                parsed = datetime.strptime(normalized, fmt)
                return parsed.strftime('%Y-%m-%d')
            except ValueError:
                continue
    return None


def _extract_amount(text):
    amount_pattern = r'\d{1,3}(?:,\d{3})*(?:\.\d{2,3})'
    candidates = re.findall(amount_pattern, text)
    if not candidates:
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    keyword_lines = [line for line in lines if any(k in line.lower() for k in ['total', 'net', 'amount', 'balance'])]

    prioritized = []
    for line in keyword_lines:
        for match in re.findall(amount_pattern, line):
            value = _normalize_amount(match)
            if value is not None:
                prioritized.append(value)

    if prioritized:
        return float(max(prioritized))

    values = []
    for amt in candidates:
        value = _normalize_amount(amt)
        if value is not None:
            values.append(value)

    if not values:
        return None

    # Heuristic: prefer a realistic positive value and avoid tiny tax fragments if bigger total exists.
    values.sort()
    return float(values[-1])


def _extract_merchant(lines):
    if not lines:
        return None

    noisy_tokens = {'invoice', 'tax', 'qty', 'description', 'amount', 'total', 'date'}
    for line in lines[:6]:
        lowered = line.lower()
        if len(line) < 3:
            continue
        if any(token in lowered for token in noisy_tokens):
            continue
        if re.search(r'\d{3,}', lowered):
            continue
        return line

    return lines[0]


def _run_ocr_with_rotation(img):
    best_text = ''
    best_conf = -1.0

    for angle in (0, 90, 180, 270):
        candidate = img.rotate(angle, expand=True) if angle else img
        text = pytesseract.image_to_string(candidate, lang='eng+fas', config='--oem 3 --psm 6')
        data = pytesseract.image_to_data(candidate, output_type=pytesseract.Output.DICT)

        conf_values = []
        for conf in data.get('conf', []):
            try:
                value = float(conf)
            except (TypeError, ValueError):
                continue
            if value >= 0:
                conf_values.append(value)

        avg_conf = (sum(conf_values) / len(conf_values)) if conf_values else 0.0
        if avg_conf > best_conf and text.strip():
            best_conf = avg_conf
            best_text = text

    return best_text, round(max(best_conf, 0.0) / 100.0, 3)

def extract_receipt_data(image_path):
    """
    Scans a receipt image and extracts Date, Amount, Vendor, and Category.
    Returns a dict: {'date': 'YYYY-MM-DD', 'amount': 0.00, 'description': '...', 'category': '...', 'raw_text': '...'}
    """
    result = {
        'date': None,
        'amount': None,
        'description': None,
        'category': None,
        'merchant': None,
        'reference_number': None,
        'currency': None,
        'raw_text': '',
        'confidence': 0.0,
        'error': None,
    }

    try:
        # 0. Prefer strong AI extraction when configured, fallback to local OCR.
        try:
            ai_result = _extract_with_openai_vision(image_path)
            if ai_result:
                result.update(ai_result)
                if result.get('amount') is not None or result.get('merchant') or result.get('date'):
                    return result
        except Exception:
            logger.exception('AI receipt extraction failed; falling back to local OCR.')

        # 1. Check if OCR dependencies are available
        if not _ocr_available():
            result['error'] = 'OCR engine is not available on this server.'
            return result

        # 2. OCR Scan with orientation handling
        img = Image.open(image_path)
        img = img.convert('L')
        text, confidence = _run_ocr_with_rotation(img)
        result['raw_text'] = text
        result['confidence'] = confidence

        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            result['error'] = 'Unable to read text from receipt.'
            return result
        
        # 3. Detect Category
        result['category'] = detect_category(text)

        # 4. Extract Date
        result['date'] = _extract_date(text)

        # 5. Extract Amount
        result['amount'] = _extract_amount(text)

        # 6. Merchant and Description
        result['merchant'] = _extract_merchant(lines)
        result['description'] = lines[0]

        # If no critical fields detected, return meaningful error for UI.
        if result['amount'] is None and result['date'] is None:
            result['error'] = 'Receipt text detected but amount/date could not be extracted reliably.'
            
    except Exception as e:
        logger.exception("OCR Error while processing receipt: %s", image_path)
        result['error'] = str(e)
    
    return result
