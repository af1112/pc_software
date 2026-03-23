#!/bin/bash

# Production Deployment Script
# This script safely deploys the latest changes from Git to production

echo "🚀 Starting Production Deployment..."

# Set production environment
export DJANGO_ENV=production

# Pull latest changes from Git
echo "📥 Pulling latest changes from Git..."
git pull origin main

# Check if pull was successful
if [ $? -ne 0 ]; then
    echo "❌ Git pull failed. Please check for conflicts."
    exit 1
fi

# Run database migrations
echo "🗄️ Running database migrations..."
python manage.py migrate

if [ $? -ne 0 ]; then
    echo "❌ Database migration failed."
    exit 1
fi

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

if [ $? -ne 0 ]; then
    echo "❌ Static file collection failed."
    exit 1
fi

# Restart the application (adjust based on your deployment method)
echo "🔄 Restarting application..."
systemctl restart gunicorn || echo "⚠️ Could not restart gunicorn - please restart manually"

# Check application status
echo "🔍 Checking application status..."
sleep 5

if curl -f http://localhost:8000 > /dev/null 2>&1; then
    echo "✅ Application is running successfully!"
else
    echo "❌ Application may not be responding. Please check logs."
fi

echo "🎉 Deployment completed!"
echo ""
echo "📋 Next Steps:"
echo "1. Verify the application is working at your domain"
echo "2. Check logs if there are any issues: tail -f logs/django.log"
echo "3. Monitor the application for any errors"
echo ""
echo "🔧 Environment Variables in Use:"
echo "DJANGO_ENV=$DJANGO_ENV"
echo "DB_NAME=${DB_NAME:-not_set}"
echo "DB_HOST=${DB_HOST:-not_set}"
