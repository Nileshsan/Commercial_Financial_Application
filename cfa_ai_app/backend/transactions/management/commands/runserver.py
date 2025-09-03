from django.core.management.commands.runserver import Command as RunserverCommand
from django.db import OperationalError
import logging

logger = logging.getLogger(__name__)


class Command(RunserverCommand):
    """Override the default runserver to be resilient when DB user connection limits
    have been exhausted by skipping the migration check if it raises OperationalError.

    This is a development-time safety net only. Do not use in production without
    understanding the implications (skipping migration checks can hide schema drift).
    """

    def check_migrations(self):
        try:
            return super().check_migrations()
        except OperationalError as e:
            # Log and continue — avoids crashing the dev server when DB is temporarily
            # over capacity (e.g., max_connections_per_hour exceeded).
            logger.error(
                "runserver: DB OperationalError during migration check: %s. Skipping migration check.",
                e,
            )
            return None
