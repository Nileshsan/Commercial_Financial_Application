from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os
import xml.etree.ElementTree as ET

class TallyDataImportView(viewsets.ViewSet):
    """
    ViewSet for handling Tally data import operations
    """
    def create(self, request):
        """
        Handle the upload of Tally data files
        """
        try:
            file = request.FILES.get('file')
            if not file:
                return Response({"error": "No file was uploaded."}, status=status.HTTP_400_BAD_REQUEST)

            # Save file
            fs = FileSystemStorage(location=settings.MEDIA_ROOT)
            filename = fs.save(f'tally_imports/{file.name}', file)
            file_path = fs.path(filename)

            # Process the file (placeholder - implement actual processing logic)
            # For now, just verify it's XML
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                return Response({
                    "message": "File uploaded and validated successfully",
                    "filename": filename
                }, status=status.HTTP_200_OK)
            except ET.ParseError:
                return Response({
                    "error": "Invalid XML file"
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def process(self, request):
        """
        Process an already uploaded Tally data file
        """
        filename = request.data.get('filename')
        if not filename:
            return Response({"error": "No filename provided"}, status=status.HTTP_400_BAD_REQUEST)

        file_path = os.path.join(settings.MEDIA_ROOT, 'tally_imports', filename)
        if not os.path.exists(file_path):
            return Response({"error": "File not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            # Placeholder for actual processing logic
            return Response({
                "message": "File processing initiated",
                "filename": filename
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
