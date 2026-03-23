# Environment Configuration Guide

## Problem Solved
This setup prevents local and server configurations from conflicting when deploying via Git.

## How It Works

### 1. Environment Detection
The system automatically detects the environment using the `DJANGO_ENV` environment variable:
- `DJANGO_ENV=local` → Uses local development settings
- `DJANGO_ENV=production` → Uses production server settings
- Default (no variable set) → Uses local settings

### 2. Configuration Files

#### Local Development (`settings_local.py`)
- SQLite database (`db.sqlite3`)
- Debug mode enabled
- Local host permissions
- Console email backend
- No security headers

#### Production Server (`settings_production.py`)
- MySQL database with environment variables
- Debug mode disabled
- Production domain permissions
- SMTP email backend
- Full security headers
- Production logging

### 3. Deployment Instructions

#### For Local Development:
```bash
# No special setup needed - defaults to local
python manage.py runserver
```

#### For Production Server:
```bash
# Set production environment
export DJANGO_ENV=production

# Set database credentials (or use .env file)
export DB_NAME=pc_software_db
export DB_USER=pc_user
export DB_PASSWORD=your_password
export DB_HOST=localhost
export DB_PORT=3306

# Set production secret key
export SECRET_KEY=your-production-secret-key

# Run migrations and collect static files
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py runserver 0.0.0.0:8000
```

### 4. Git Workflow Safety

#### Files That Will NOT Conflict:
- `settings_local.py` - Local only (gitignored)
- `settings_production.py` - Server only (gitignored) 
- `.env` - Environment variables (gitignored)
- `db.sqlite3` - Local database (gitignored)

#### Files That ARE Shared:
- `settings.py` - Main settings (environment-aware)
- `models.py` - Database models
- `views.py` - Application logic
- `templates/` - HTML templates
- `static/` - CSS/JS/images

### 5. Quick Start Commands

#### Pull Latest Changes on Server:
```bash
git pull origin main
export DJANGO_ENV=production
python manage.py migrate
python manage.py collectstatic --noinput
systemctl restart gunicorn  # or your deployment method
```

#### Pull Latest Changes Locally:
```bash
git pull origin main
# No environment setup needed - automatically uses local settings
python manage.py runserver
```

### 6. Benefits
✅ **No Configuration Conflicts**: Local and server settings are completely separate
✅ **Security**: Production secrets never committed to Git
✅ **Flexibility**: Easy to switch between environments
✅ **Safety**: Can't accidentally overwrite production settings with local ones
✅ **Git Clean**: Only shared code is version controlled

### 7. Troubleshooting

#### If site doesn't work after pull:
1. Check environment variable: `echo $DJANGO_ENV`
2. For server: Should be `production`
3. For local: Should be `local` or unset
4. Restart the application after changing environment

#### If database errors occur:
1. Verify environment variables are set correctly
2. Check database connection settings in the appropriate settings file
3. Run migrations: `python manage.py migrate`

This setup ensures that local development and production server configurations never interfere with each other!
