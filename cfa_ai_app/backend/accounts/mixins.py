from rest_framework.exceptions import PermissionDenied

class CompanyFilterMixin:
    """
    A mixin that filters querysets based on the authenticated company.
    Requires the view to have a get_queryset method and the model to have a company field.
    """
    def get_queryset(self):
        queryset = super().get_queryset()
        company = getattr(self.request.auth, 'id', None)
        if not company:
            raise PermissionDenied("Company authentication required")
        return queryset.filter(company_id=company)
