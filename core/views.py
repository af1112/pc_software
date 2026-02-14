from django.shortcuts import render, HttpResponse, redirect
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
import os
import traceback
import sys

@login_required
def main_dashboard(request):
    """
    Main landing dashboard showing available modules based on organization subscription.
    """
    # Get user profile and organization
    profile = getattr(request.user, 'profile', None)
    organization = profile.organization if profile else None
    
    context = {
        'organization': organization,
        # Access is granted if:
        # 1. User is superuser OR
        # 2. (Organization allows OR no organization assigned) AND (User has direct permission)
        'can_use_expenses': request.user.is_superuser or ((organization.can_use_expenses if organization else True) and request.user.has_perm('users.can_access_expenses')),
        'can_use_ticketing': request.user.is_superuser or ((organization.can_use_ticketing if organization else True) and request.user.has_perm('users.can_access_ticketing')),
        'can_use_attendance': request.user.is_superuser or ((organization.can_use_attendance if organization else True) and request.user.has_perm('users.can_access_attendance')),
        'can_use_projects': request.user.is_superuser or ((organization.can_use_projects if organization else True) and request.user.has_perm('users.can_access_projects')),
        'can_use_dms': request.user.is_superuser or ((organization.can_use_dms if organization else True) and request.user.has_perm('users.can_access_dms')),
        'can_use_ai': request.user.is_superuser or ((organization.can_use_ai if organization else True) and request.user.has_perm('users.can_access_ai')),
        'can_use_menu': request.user.is_superuser or ((organization.can_use_menu if organization else True) and request.user.has_perm('users.can_access_menu')),
        'can_use_club': request.user.is_superuser or ((organization.can_use_club if organization else True) and request.user.has_perm('users.can_access_club')),
        'is_superuser': request.user.is_superuser
    }
    
    return render(request, 'main_dashboard.html', context)

    

def home_redirect(request):
    """
    Root path handler:
    - If user is authenticated -> go to dashboard
    - Else -> go to login page
    """
    if request.user.is_authenticated:
        return redirect('main_dashboard')
    return redirect('/accounts/login/')

def run_migrations_view(request):
    """
    """
    Safely run migrations on production.
    Usage: /run-migrations/  OR  /run-migrations/?key=AKAF_SECRET_RESTORE_2026&fake=1
    """
    secret_key = request.GET.get('key')
    force_fake = request.GET.get('fake') == '1'
    
    # Use is_authenticated only if user is logged in, otherwise default to False
    is_authorized = False
    if request.user.is_authenticated:
        is_authorized = (request.user.is_superuser or request.user.is_staff)
    
    if not is_authorized and secret_key != 'AKAF_SECRET_RESTORE_2026':
        return HttpResponse("Unauthorized. Please use the secret key or login as staff.", status=403)
        
    output = []
    output.append("--- RUNNING MIGRATIONS (Vercel Fix Mode) ---")
    output.append(f"Force Fake: {force_fake}")
    
    try:
        from django.core.management import call_command
        from io import StringIO
        from django.db import connection
        
        # Action 1: Create Default Organization if requested
        if request.GET.get('init_org') == '1':
            output.append("🚀 Initializing Default Organization...")
            try:
                with connection.cursor() as cursor:
                    # Check if organizations table exists
                    cursor.execute("SHOW TABLES LIKE 'organizations_organization'")
                    if cursor.fetchone():
                        cursor.execute("SELECT COUNT(*) FROM organizations_organization")
                        count = cursor.fetchone()[0]
                        if count == 0:
                            cursor.execute("""
                                INSERT INTO organizations_organization 
                                (name, slug, is_active, can_use_expenses, can_use_ticketing, can_use_attendance, can_use_projects, can_use_dms, can_use_ai, can_use_menu, can_use_club, created_at, updated_at)
                                VALUES ('Default Company', 'default', 1, 1, 1, 1, 1, 1, 1, 1, 1, NOW(), NOW())
                            """)
                            output.append("✅ Created 'Default Company'.")
                        else:
                            output.append(f"ℹ️ {count} organizations already exist.")
                    else:
                        output.append("❌ organizations_organization table does not exist yet. Run migrations first.")
            except Exception as e:
                output.append(f"❌ Org Init failed: {str(e)}")

        # Inspection part
        output.append("\nInspecting table 'users_userprofile'...")
        has_org_col = False
        with connection.cursor() as cursor:
            try:
                cursor.execute("DESCRIBE users_userprofile")
                columns = cursor.fetchall()
                output.append("Columns in users_userprofile:")
                for col in columns:
                    output.append(f" - {col[0]} ({col[1]})")
                    if col[0] == 'organization_id':
                        has_org_col = True
            except Exception as e:
                output.append(f"Could not describe table: {str(e)}")

        # Emergency Fix for MySQL Error 1072
        if not has_org_col:
            output.append("⚠️ Emergency: organization_id missing. Attempting manual SQL injection...")
            with connection.cursor() as cursor:
                try:
                    # Disable foreign key checks for a moment
                    cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
                    cursor.execute("ALTER TABLE users_userprofile ADD COLUMN organization_id BIGINT NULL;")
                    cursor.execute("SET FOREIGN_KEY_CHECKS=1;")
                    output.append("✅ Successfully added organization_id column via raw SQL.")
                except Exception as e:
                    output.append(f"❌ Manual SQL failed (maybe it exists?): {str(e)}")

        out = StringIO()
        
        if force_fake:
            output.append("🛠️ FORCE FAKE MODE ACTIVATED")
            call_command('migrate', '--fake', interactive=False, stdout=out)
            output.append(out.getvalue())
            output.append("✅ Forced fake migration completed.")
        else:
            # Step 1: Try migrate organizations first
            try:
                output.append("Priority 1: Migrating 'organizations' app...")
                call_command('migrate', 'organizations', interactive=False, stdout=out)
                output.append(out.getvalue())
                out = StringIO() # reset for next command
            except Exception as e:
                output.append(f"Note: 'organizations' migration message: {str(e)}")

            # Step 2: Try normal migrate
            try:
                output.append("Priority 2: Running full migrate...")
                call_command('migrate', interactive=False, stdout=out)
            except Exception as e:
                err_str = str(e).lower()
                if "keyerror: 'organization'" in err_str or "already exists" in err_str or "1072" in err_str or "1060" in err_str:
                    output.append(f"Detected migration conflict/error: {str(e)}")
                    output.append("Attempting recovery: --fake-initial...")
                    call_command('migrate', '--fake-initial', interactive=False, stdout=out)
                else:
                    raise e
                    
            output.append(out.getvalue())
            output.append("✅ Migrations completed successfully!")
    except Exception as e:
        output.append(f"❌ Migration failed: {str(e)}")
        output.append(traceback.format_exc())
    
    return HttpResponse("<pre>" + "\n".join(output) + "</pre>")

def restore_data_view(request):
    """
    Emergency data restore view for Vercel/Shared Hosting.
    Usage: /restore-data/?key=AKAF_SECRET_RESTORE_2026
    """
    secret_key = request.GET.get('key')
    if secret_key != 'AKAF_SECRET_RESTORE_2026':
        return HttpResponse("Unauthorized", status=403)
    
    output = []
    output.append("--- DEBUG LOGS ---")
    output.append(f"Python Version: {sys.version}")
    
    try:
        # Check DB Connection Info (Safe)
        from django.conf import settings
        from django.db import connection
        db_conf = settings.DATABASES['default']
        output.append(f"DB Engine: {db_conf['ENGINE']}")
        output.append(f"DB Host: {db_conf.get('HOST', 'N/A')}")
        
        # Step 1: Just try to connect and run a simple query
        output.append("Testing database connection...")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                output.append("✅ Database connection test successful!")
        except Exception as conn_err:
            output.append(f"⚠️ Direct connection failed: {str(conn_err)}")
            output.append("Attempting to ensure database exists via pymysql...")
            try:
                import pymysql
                temp_conn = pymysql.connect(
                    host=db_conf['HOST'],
                    user=db_conf['USER'],
                    password=db_conf['PASSWORD'],
                    port=int(db_conf.get('PORT', 4000)),
                    ssl={'ca': None} if 'ssl' in db_conf.get('OPTIONS', {}) else None,
                    connect_timeout=5
                )
                with temp_conn.cursor() as cursor:
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_conf['NAME']}")
                temp_conn.close()
                output.append(f"✅ Database {db_conf['NAME']} verified/created.")
            except Exception as py_err:
                output.append(f"❌ Pymysql connection failed: {str(py_err)}")
                # Don't raise yet, try migrate anyway
        
        # Step 1: Force Clean Database (Drop all tables)
        output.append("🧹 Cleaning database (dropping all tables)...")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                for table in tables:
                    cursor.execute(f"DROP TABLE IF EXISTS {table[0]}")
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            output.append("✅ Database cleaned successfully.")
        except Exception as clean_err:
            output.append(f"⚠️ Clean failed: {str(clean_err)}")

        # Step 2: Run fresh migrate
        output.append("Running fresh migrations...")
        try:
            call_command('migrate', interactive=False)
            output.append("✅ Fresh migration successful!")
        except Exception as mig_err:
            output.append(f"❌ Migration failed: {str(mig_err)}")
            raise mig_err
        
        # Step 3: Create Superuser if not exists
        output.append("Checking for admin user...")
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if not User.objects.filter(username='admin').exists():
                User.objects.create_superuser('admin', 'admin@example.com', 'admin123456')
                output.append("✅ Admin user created (admin / admin123456)")
            else:
                output.append("ℹ️ Admin user already exists.")
        except Exception as user_err:
            output.append(f"⚠️ Could not create admin: {str(user_err)}")

        # Load data
        data_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data.json')
        if os.path.exists(data_file):
            output.append(f"Loading data from {data_file}...")
            call_command('loaddata', data_file)
            output.append("✅ Data restored successfully!")
            return HttpResponse("<br>".join(output), status=200)
        else:
            output.append(f"❌ ERROR: data.json not found at {data_file}")
            return HttpResponse("<br>".join(output), status=404)
            
    except Exception as e:
        error_trace = traceback.format_exc()
        output.append(f"❌ CRITICAL ERROR: {str(e)}")
        output.append("<pre>" + error_trace + "</pre>")
        return HttpResponse("<br>".join(output), status=500)
