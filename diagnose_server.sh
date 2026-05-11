set -eu

pwd
whoami || true
date || true

echo "--- python ---"
python3 --version || true
which python3 || true

echo "--- env ---"
echo "DJANGO_ENV=${DJANGO_ENV-}"
echo "DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE-}"

echo "--- django settings/db ---"
python3 - <<'PY'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings')
from django.conf import settings
print('SETTINGS_MODULE=', os.environ.get('DJANGO_SETTINGS_MODULE'))
print('DEBUG=', getattr(settings,'DEBUG',None))
print('DATABASES.default.ENGINE=', settings.DATABASES['default'].get('ENGINE'))
print('DATABASES.default.NAME=', settings.DATABASES['default'].get('NAME'))
PY

echo "--- db file check (sqlite only) ---"
python3 - <<'PY'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings')
from django.conf import settings
engine = settings.DATABASES['default'].get('ENGINE')
name = settings.DATABASES['default'].get('NAME')
if engine and 'sqlite3' in engine:
    import pathlib, sqlite3
    p = pathlib.Path(str(name))
    print('SQLITE PATH=', p)
    print('EXISTS=', p.exists())
    if p.exists():
        print('SIZE=', p.stat().st_size)
        conn = sqlite3.connect(str(p))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        print('TABLES_COUNT=', len(tables))
        print('HAS_django_session=', 'django_session' in tables)
        print('FIRST_TABLES=', tables[:30])
        conn.close()
else:
    print('NOT SQLITE, skipping sqlite inspection')
PY

echo "--- migrations status (non-destructive) ---"
python3 manage.py showmigrations --list || true
python3 manage.py migrate --check || true

printf "\nDONE\n"
