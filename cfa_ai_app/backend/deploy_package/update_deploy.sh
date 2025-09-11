#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting deployment update...${NC}"

# 1. Backup database
echo -e "${YELLOW}Creating database backup...${NC}"
python manage.py dumpdata --exclude auth.permission --exclude contenttypes > backup_$(date +%Y%m%d_%H%M%S).json

# 2. Activate virtual environment
source venv/bin/activate

# 3. Install/update requirements
echo -e "${YELLOW}Updating dependencies...${NC}"
pip install -r requirements.txt

# 4. Apply migrations
echo -e "${YELLOW}Applying database migrations...${NC}"
python manage.py migrate

# 5. Collect static files
echo -e "${YELLOW}Collecting static files...${NC}"
python manage.py collectstatic --noinput

# 6. Clear cache
echo -e "${YELLOW}Clearing cache...${NC}"
python manage.py clear_cache

# 7. Restart services
echo -e "${YELLOW}Restarting services...${NC}"
sudo systemctl restart gunicorn
sudo systemctl restart nginx

echo -e "${GREEN}Deployment update completed!${NC}"
echo -e "${YELLOW}Please check the logs for any errors.${NC}"
echo -e "Gunicorn logs: sudo journalctl -u gunicorn"
echo -e "Nginx logs: sudo tail -f /var/log/nginx/error.log"
