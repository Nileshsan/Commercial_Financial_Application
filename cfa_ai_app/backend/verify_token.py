import requests
import json
import sys

def list_users():
    # Print existing users via Django ORM by running manage.py shell separately
    pass

def post_and_fetch_api_token(payload):
    try:
        r = requests.post('http://127.0.0.1:8000/api/token/', json=payload, timeout=10)
        print('\n=== TOKEN REQUEST ===')
        print('REQUEST:', payload)
        print('STATUS:', r.status_code)
        print('RESPONSE:', r.text)
        if r.status_code == 200:
            data = r.json()
            access = data.get('access')
            if access:
                headers = {'Authorization': f'Bearer {access}'}
                ar = requests.get('http://127.0.0.1:8000/api/user/api-token/', headers=headers, timeout=10)
                print('\n=== API TOKEN (user/api-token/) ===')
                print('status', ar.status_code)
                print(ar.text)
    except Exception as e:
        print('ERROR:', e)

if __name__ == '__main__':
    # Try with an email-based login first (project USERNAME_FIELD = email)
    post_and_fetch_api_token({'email':'testuser@example.com','password':'TestPass123'})
    # Also try with username payload to validate mapping
    post_and_fetch_api_token({'username':'testuser@example.com','password':'TestPass123'})
