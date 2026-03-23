#!/bin/bash

# Local Development Setup Script
# This script sets up the local development environment

echo "🏠 Setting up Local Development Environment..."

# Ensure we're using local environment
export DJANGO_ENV=local

# Install dependencies if needed
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install requirements
echo "📚 Installing requirements..."
pip install -r requirements.txt

# Run migrations
echo "🗄️ Running database migrations..."
python manage.py migrate

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if needed
echo "👤 Checking for superuser..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    print('Creating superuser...')
    import os
    os.system('python manage.py createsuperuser')
else:
    print('Superuser already exists.')
"

echo ""
echo "🎉 Local development setup complete!"
echo ""
echo "🚀 To start the development server:"
echo "   source .venv/bin/activate"
echo "   python manage.py runserver"
echo ""
echo "🌐 Access the application at: http://localhost:8000"
echo ""
echo "🔧 Environment Variables in Use:"
echo "DJANGO_ENV=$DJANGO_ENV"
echo "DEBUG=DEBUG"
echo "DATABASE=SQLite (db.sqlite3)"
