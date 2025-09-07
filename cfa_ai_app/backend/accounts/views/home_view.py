from django.views.generic import TemplateView
from django.db.models import Sum, Count
from accounts.models import Client
from transactions.models import TallyTransaction  # Import if you have this model

class HomeView(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get client statistics
        context['total_clients'] = Client.objects.count()
        context['active_clients'] = Client.objects.filter(is_active=True).count()

        try:
            # Try to get transaction statistics if the model exists
            context['total_transactions'] = TallyTransaction.objects.count()
            context['pending_amount'] = TallyTransaction.objects.filter(
                status='pending'
            ).aggregate(
                total=Sum('amount')
            )['total'] or 0
        except:
            # If TallyTransaction model doesn't exist or there's an error
            context['total_transactions'] = 0
            context['pending_amount'] = 0

        return context
