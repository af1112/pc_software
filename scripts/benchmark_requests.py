import os
import sys
import django
from pathlib import Path
from time import perf_counter
from django.test import Client
from django.db import connection
from django.test.utils import CaptureQueriesContext

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()


def measure(label, fn, repeat=3):
    runs = []
    for _ in range(repeat):
        t0 = perf_counter()
        with CaptureQueriesContext(connection) as ctx:
            resp = fn()
        elapsed_ms = (perf_counter() - t0) * 1000
        db_ms = 0.0
        for q in ctx.captured_queries:
            try:
                db_ms += float(q.get('time', 0.0)) * 1000
            except Exception:
                pass
        runs.append((resp, elapsed_ms, len(ctx), db_ms))

    avg_ms = sum(r[1] for r in runs) / repeat
    avg_queries = sum(r[2] for r in runs) / repeat
    avg_db_ms = sum(r[3] for r in runs) / repeat
    resp = runs[-1][0]
    loc = resp.headers.get('Location') if hasattr(resp, 'headers') else None
    print(
        f"{label}: status={resp.status_code} avg_time_ms={avg_ms:.2f} "
        f"avg_queries={avg_queries:.1f} avg_db_time_ms={avg_db_ms:.2f} location={loc}"
    )


def main():
    c = Client()
    measure('GET /accounts/login/', lambda: c.get('/accounts/login/?next=/attendance/quick/'))
    measure('POST /accounts/login/', lambda: c.post('/accounts/login/?next=/attendance/quick/', {
        'username': 'redir_test_user',
        'password': 'pass12345',
        'next': '/attendance/quick/'
    }))
    measure('GET /attendance/quick/', lambda: c.get('/attendance/quick/'))
    measure('GET /attendance/ (dashboard)', lambda: c.get('/attendance/'))
    measure('GET / (main_dashboard)', lambda: c.get('/'))


if __name__ == '__main__':
    main()
