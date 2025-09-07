from django import forms
from .models import Client, ClientDocument

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'name', 'email', 'phone', 'address',
            'client_type', 'tax_number', 'website',
            'annual_revenue', 'employee_count',
            'risk_level', 'credit_limit',
            'company_name', 'tags'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'tags': forms.TextInput(attrs={'data-role': 'tagsinput'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to form fields
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control'
            })

    def clean_company_name(self):
        company_name = self.cleaned_data.get('company_name')
        if not company_name:
            raise forms.ValidationError("Company name is required")
        return company_name

class ClientDocumentForm(forms.ModelForm):
    class Meta:
        model = ClientDocument
        fields = ['document_type', 'file', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
