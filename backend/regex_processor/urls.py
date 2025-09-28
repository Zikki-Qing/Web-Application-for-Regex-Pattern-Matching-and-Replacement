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
    path('stats/', views.get_global_statistics, name='get_global_statistics'),
    path('statistics/<int:request_id>/', views.get_request_statistics, name='get_request_statistics'),
    
    # History and management
    path('history/', views.get_processing_history, name='get_processing_history'),
    path('history/<int:request_id>/', views.get_request_detail, name='get_request_detail'),
    path('history/<int:request_id>/delete/', views.delete_request, name='delete_request'),
    
    # Health check
    path('health/', views.health_check, name='health_check'),
]
