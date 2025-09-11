#!/bin/bash

# Exit on error
set -e

echo "Starting deployment..."

# Navigate to the project directory
cd /opt/cfa-backend

# Activate virtual environment
source venv/bin/activate

# Install/upgrade dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate

# Copy service files
cp gunicorn.service /etc/systemd/system/
cp nginx_config /etc/nginx/sites-available/cfa

# Create symbolic link for nginx if it doesn't exist
if [ ! -f /etc/nginx/sites-enabled/cfa ]; then
    ln -s /etc/nginx/sites-available/cfa /etc/nginx/sites-enabled/cfa
fi

# Create required directories
mkdir -p logs
mkdir -p media
mkdir -p static

# Set permissions
chown -R root:root /opt/cfa-backend
chmod -R 755 /opt/cfa-backend/static
chmod -R 755 /opt/cfa-backend/media
chmod -R 755 /opt/cfa-backend/logs

# Reload systemd
systemctl daemon-reload

# Restart services
systemctl restart gunicorn
systemctl restart nginx

echo "Deployment completed successfully!"

# Check service status
systemctl status gunicorn
systemctl status nginx
