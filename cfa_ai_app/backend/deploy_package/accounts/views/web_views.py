from django.views.generic import ListView, CreateView, DetailView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q
from accounts.models import Client, ClientDocument
from accounts.forms import ClientForm

class ClientListView(LoginRequiredMixin, ListView):
    model = Client
    template_name = 'client_list.html'
    context_object_name = 'clients'
    paginate_by = 9

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(company=self.request.user.company)

        # Apply filters
        search = self.request.GET.get('search')
        client_type = self.request.GET.get('client_type')
        risk_level = self.request.GET.get('risk_level')
        status = self.request.GET.get('status')

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(tax_number__icontains=search)
            )

        if client_type:
            queryset = queryset.filter(client_type=client_type)

        if risk_level:
            queryset = queryset.filter(risk_level=risk_level)

        if status:
            is_active = status == 'active'
            queryset = queryset.filter(is_active=is_active)

        return queryset.order_by('-created_at')

class ClientCreateView(LoginRequiredMixin, CreateView):
    model = Client
    template_name = 'client_register.html'
    form_class = ClientForm
    success_url = reverse_lazy('client_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        
        # Handle document uploads
        files = self.request.FILES.getlist('document_file[]')
        types = self.request.POST.getlist('document_type[]')
        notes = self.request.POST.getlist('document_notes[]')

        for file, doc_type, note in zip(files, types, notes):
            if file and doc_type:
                ClientDocument.objects.create(
                    client=self.object,
                    document_type=doc_type,
                    file=file,
                    notes=note
                )

        messages.success(self.request, 'Client registered successfully!')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

class ClientDetailView(LoginRequiredMixin, DetailView):
    model = Client
    template_name = 'client_detail.html'
    context_object_name = 'client'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['documents'] = self.object.documents.all()
        context['activities'] = self.object.activities.all()[:10]
        return context

class ClientUpdateView(LoginRequiredMixin, UpdateView):
    model = Client
    template_name = 'client_update.html'
    form_class = ClientForm
    
    def get_success_url(self):
        return reverse_lazy('client_detail', kwargs={'pk': self.object.pk})
