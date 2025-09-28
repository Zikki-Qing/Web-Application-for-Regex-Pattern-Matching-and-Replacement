from django.urls import path
from . import views

app_name = 'regex_processor'

urlpatterns = [
    # File upload and processing
    path('upload/', views.upload_and_process_file, name='upload_file'),
    
    # Status query
    path('status/<int:request_id>/', views.get_processing_status, name='get_status'),
    
    # File download
    path('download/<int:request_id>/', views.download_result, name='download_result'),
    
    # Processing logs
    path('logs/<int:request_id>/', views.get_processing_logs, name='get_processing_logs'),
    
    # Statistics
    path('statistics/<int:request_id>/', views.get_request_statistics, name='get_request_statistics'),
    
    # Health check
    path('health/', views.health_check, name='health_check'),
]
