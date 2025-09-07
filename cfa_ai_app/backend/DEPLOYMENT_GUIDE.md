# Deployment Guide for CFA on Hostinger

## Prerequisites
1. A Hostinger account with:
   - Python support
   - SSH access
   - MySQL database
   - Domain configured

## Step 1: Initial Server Setup
1. Log in to your Hostinger control panel
2. Create a new MySQL database and user
3. Note down the database credentials

## Step 2: Project Preparation
1. Update settings_prod.py with your:
   - Database credentials
   - Domain name
   - Email settings
   - Static/media paths

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 3: Upload Files
1. Connect to your Hostinger via SSH or FTP
2. Upload the project files to: /home/username/cfa_ai_app/

## Step 4: Configure the Environment
1. SSH into your server and navigate to the project directory:
```bash
cd /home/username/cfa_ai_app/backend
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install additional packages:
```bash
pip install gunicorn mysqlclient
```

## Step 5: Django Setup
1. Collect static files:
```bash
python manage.py collectstatic --noinput
```

2. Run migrations:
```bash
python manage.py migrate
```

3. Create superuser:
```bash
python manage.py createsuperuser
```

## Step 6: Configure Web Server
1. Update the nginx_config file with your domain
2. Update the gunicorn.service file with your paths
3. Copy configurations:
```bash
sudo cp nginx_config /etc/nginx/sites-available/cfa
sudo ln -s /etc/nginx/sites-available/cfa /etc/nginx/sites-enabled/
sudo cp gunicorn.service /etc/systemd/system/
```

## Step 7: Start Services
1. Start Gunicorn:
```bash
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
```

2. Restart Nginx:
```bash
sudo systemctl restart nginx
```

## Step 8: SSL Setup
1. Install SSL certificate through Hostinger control panel
2. Update nginx_config with SSL paths
3. Restart Nginx

## Step 9: Verify Deployment
1. Visit your domain to verify the site is working
2. Check the logs for any errors:
```bash
tail -f /home/username/logs/django.log
```

## Common Issues and Solutions

### Static Files Not Loading
1. Check STATIC_ROOT and MEDIA_ROOT paths
2. Verify file permissions
3. Run collectstatic again

### Database Connection Issues
1. Verify database credentials
2. Check database host and port
3. Ensure MySQL server is running

### 502 Bad Gateway
1. Check Gunicorn service status
2. Verify socket file permissions
3. Check error logs

### SSL Certificate Issues
1. Verify certificate paths
2. Check certificate expiration
3. Validate Nginx SSL configuration

## Maintenance

### Regular Updates
1. Pull latest code changes
2. Activate virtual environment
3. Install any new dependencies
4. Run migrations
4. Restart Gunicorn
```bash
sudo systemctl restart gunicorn
```

### Backup Strategy
1. Database: Regular MySQL dumps
2. Media files: Regular file backups
3. Configuration files: Version control

### Monitoring
1. Check server logs regularly
2. Monitor disk space usage
3. Keep track of SSL certificate expiration
4. Monitor application performance

For any issues, check the logs at:
- Application logs: /home/username/logs/django.log
- Nginx error logs: /var/log/nginx/error.log
- Gunicorn logs: journalctl -u gunicorn
