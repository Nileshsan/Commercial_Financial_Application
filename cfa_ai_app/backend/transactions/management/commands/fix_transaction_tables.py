from django.core.management.base import BaseCommand
from django.db import connection
import os

class Command(BaseCommand):
    help = 'Fix transactions tables by recreating them'

    def handle(self, *args, **options):
        # Read the SQL file
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        sql_file = os.path.join(app_dir, 'migrations', 'fix_tables.sql')
        
        with open(sql_file, 'r') as f:
            sql = f.read()
            
        # Split into individual statements
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        
        with connection.cursor() as cursor:
            for statement in statements:
                try:
                    cursor.execute(statement)
                    self.stdout.write(self.style.SUCCESS(f'Successfully executed: {statement[:100]}...'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error executing: {statement[:100]}...'))
                    self.stdout.write(self.style.ERROR(str(e)))
