
from django.http import JsonResponse
from accounts.models import UserCompany, Company, User
from django.views.decorators.csrf import csrf_exempt



@csrf_exempt
def create_company(request):
    import json
    if request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode())
            else:
                data = request.POST
            user_company_name = data.get('user_company', '').strip()
            user_company, _ = UserCompany.objects.get_or_create(name=user_company_name)
            company = Company.objects.create(
                name=data.get('name', '').strip(),
                user_company=user_company,
                api_key=data.get('api_key', '').strip(),
                address=data.get('address', '').strip()
            )
            return JsonResponse({'message': 'Company created', 'company_id': company.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)


@csrf_exempt
def create_user(request):
    import json
    if request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode())
            else:
                data = request.POST
            user_company_name = data.get('user_company', '').strip()
            company_name = data.get('company', '').strip()
            client_name = data.get('client', '').strip()
            user_company, _ = UserCompany.objects.get_or_create(name=user_company_name)
            company, _ = Company.objects.get_or_create(name=company_name, user_company=user_company)
            client = None
            if client_name:
                from accounts.models import Client
                client, _ = Client.objects.get_or_create(name=client_name)
            user = User.objects.create_user(
                email=data.get('email', '').strip(),
                username=data.get('username', '').strip(),
                password=data.get('password', '').strip(),
                user_company=user_company,
                company=company,
                role=data.get('role', 'employee'),
                client=client if client else None
            )
            return JsonResponse({'message': 'User created', 'user_id': user.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=405)
from django.shortcuts import render

from django.contrib.auth.views import LoginView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from accounts.models import Company, User

class CustomLoginView(LoginView):
    template_name = 'login.html'

# API endpoint to get API key for logged-in user's company
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_api_key(request):
    user = request.user
    company = getattr(user, 'company', None)
    if company and company.api_key:
        # Return wrapper expected by mobile client: { status: 'success', data: { api_token: ..., token: ... } }
        return Response({'status': 'success', 'data': {'api_token': company.api_key, 'token': company.api_key}})
    return Response({'status': 'error', 'message': 'API key not found for this user/company.'}, status=404)

def admin_frontend(request):
    return render(request, 'admin_frontend.html')


