import os
import re
import sys
from pathlib import Path

import django
from django.test import Client

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

c = Client()
r1 = c.get('/attendance/quick/')
print('STEP1', r1.status_code, r1.headers.get('Location'))

login_url = r1.headers.get('Location')
r2 = c.get(login_url)
html = r2.content.decode('utf-8')
m = re.search(r'name="next" value="([^"]*)"', html)
next_value = m.group(1) if m else ''
print('STEP2 next_value=', next_value)

r3 = c.post('/accounts/login/', {
    'username': 'redir_test_user',
    'password': 'pass12345',
    'next': next_value,
})
print('STEP3', r3.status_code, r3.headers.get('Location'))
