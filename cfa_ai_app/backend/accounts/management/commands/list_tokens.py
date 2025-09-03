from django.core.management.base import BaseCommand
from accounts.models import Token

class Command(BaseCommand):
    help = 'List all user tokens with username and client association.'

    def handle(self, *args, **options):
        tokens = Token.objects.select_related('user')
        if not tokens.exists():
            self.stdout.write('No tokens found.')
            return
        for token in tokens:
            user = token.user
            client = getattr(user, 'client', None)
            self.stdout.write(f'Token: {token.key}\n  User: {user.username} (id={user.id})\n  Client: {client}\n')
