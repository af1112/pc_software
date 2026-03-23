# Force redeploy: 2026-02-13 19:43
# Final attempt to trigger Vercel build
import os
import sys
import traceback

# For Vercel, we need to make sure the root and apps directories are in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

try:
    from django.core.wsgi import get_wsgi_application
    app = get_wsgi_application()
except Exception:
    error_msg = traceback.format_exc()
    print(error_msg)
    
    def app(environ, start_response):
        status = '500 Internal Server Error'
        body = f"<h1>Vercel Deployment Error (Detailed)</h1><pre>{error_msg}</pre>".encode('utf-8')
        headers = [('Content-Type', 'text/html'), ('Content-Length', str(len(body)))]
        start_response(status, headers)
        return [body]
