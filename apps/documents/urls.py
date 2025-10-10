from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('upload/', views.upload_document, name='upload'),
    path('view/<uuid:document_id>/', views.view_document, name='view'),
    path('download/<uuid:document_id>/', views.download_document, name='download'),
]