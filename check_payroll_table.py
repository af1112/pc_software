#!/usr/bin/env python
import os
import sys
import django

# Setup Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pc_software.settings')
django.setup()

from apps.hr_personnel.models import PayrollRun

print(f"PayrollRun table name: {PayrollRun._meta.db_table}")

try:
    count = PayrollRun.objects.count()
    print(f"PayrollRun records count: {count}")
except Exception as e:
    print(f"Error accessing PayrollRun: {e}")
    print("Table likely doesn't exist")
