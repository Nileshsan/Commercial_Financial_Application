from rest_framework import views, status
from rest_framework.response import Response
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import pandas as pd
import os

class TransactionUploadView(views.APIView):
    def post(self, request, *args, **kwargs):
        try:
            file = request.FILES.get('file')
            if not file:
                return Response({"error": "No file was uploaded."}, status=status.HTTP_400_BAD_REQUEST)

            # Save file
            fs = FileSystemStorage(location=settings.MEDIA_ROOT)
            filename = fs.save(f'transaction_uploads/{file.name}', file)
            file_path = fs.path(filename)

            # Process the file based on its extension
            _, ext = os.path.splitext(file.name)
            
            if ext.lower() in ['.xls', '.xlsx']:
                df = pd.read_excel(file_path)
            elif ext.lower() == '.csv':
                df = pd.read_csv(file_path)
            else:
                return Response({
                    "error": "Unsupported file format. Please upload Excel or CSV files."
                }, status=status.HTTP_400_BAD_REQUEST)

            # Process the data (placeholder - implement actual processing logic)
            # Here you would typically:
            # 1. Validate the data structure
            # 2. Clean/transform the data
            # 3. Save to database
            # 4. Return success response

            return Response({
                "message": "File uploaded and processed successfully",
                "filename": filename,
                "rows_processed": len(df)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
