import requests

file_path = r"C:\Users\Admin\Nilesh_Projects\CFA\cfa_ai_app\new_backend.zip"
with open(file_path, "rb") as f:
    response = requests.put("https://transfer.sh/new_backend.zip", data=f)
print(response.text)