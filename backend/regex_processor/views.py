from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.http import HttpResponse, Http404
from django.core.files.base import ContentFile
from .models import FileProcessingRequest, ProcessingLog, FileMetadata, ProcessingResult
from .serializers import FileUploadSerializer
from .services import FileProcessingService
import logging
import pandas as pd
import re
import io
import json

logger = logging.getLogger(__name__)

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])   # Required for multipart parsing
def upload_and_process_file(request):
    """
    Upload file and start processing
    
    Receives: file, natural language description, replacement value, etc.
    Returns: processing request ID and file preview information
    """
    try:
        # Copy multipart parsed data and perform type corrections
        data = request.data.copy()

        # Convert boolean strings to boolean
        for key in ('preserve_headers', 'case_sensitive'):
            val = data.get(key)
            if isinstance(val, str):
                data[key] = val.lower() in ('true', '1', 'yes', 'on')

        serializer = FileUploadSerializer(data=data)  # DRF automatically handles JSONField
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'Data validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create processing request
        file_request = FileProcessingRequest.objects.create(
            original_file=serializer.validated_data['file'],
            natural_language_description=serializer.validated_data['natural_language_description'],
            replacement_value=serializer.validated_data['replacement_value'],
            target_columns=serializer.validated_data.get('target_columns', []),
            preserve_headers=serializer.validated_data.get('preserve_headers', True),
            original_file_name=serializer.validated_data['file'].name,
            file_type='csv' if serializer.validated_data['file'].name.endswith('.csv') else 'excel',
            file_size=serializer.validated_data['file'].size,
            status='processing'  # Start processing
        )

        # Execute file processing
        processing_success = True
        error_message = None
        
        try:
            processed_data = process_file_content(
                file_request.original_file,
                file_request.natural_language_description,
                file_request.replacement_value,
                file_request.target_columns,
                file_request.preserve_headers,
                file_request.file_type
            )
            
            # Save processed file
            from pathlib import Path
            
            # File naming: CSV keeps .csv; Excel unified to .xlsx
            orig = Path(file_request.original_file_name)
            if file_request.file_type == 'csv':
                processed_name = f"processed_{orig.stem}.csv"
            else:
                processed_name = f"processed_{orig.stem}.xlsx"
            
            file_request.processed_file.save(
                processed_name,
                ContentFile(processed_data),
                save=True
            )
            
            file_request.status = 'completed'
            file_request.progress = 100
            file_request.save()
            
        except Exception as e:
            logger.error(f'Processing error: {str(e)}')
            file_request.status = 'failed'
            file_request.save()
            processing_success = False
            error_message = str(e)

        # Get file preview
        preview_data = FileProcessingService.get_file_preview(file_request.original_file)

        if processing_success:
            return Response({
                'success': True,
                'data': {
                    'request_id': file_request.id,
                    'task_id': 'mock_task_id',
                    'preview': preview_data
                }
            })
        else:
            return Response({
                'success': False,
                'error': 'File processing failed',
                'details': error_message,
                'data': {
                    'request_id': file_request.id,
                    'preview': preview_data
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        logger.error(f'Upload error: {str(e)}')
        return Response({
            'success': False,
            'error': 'File upload failed',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def process_file_content(file, description, replacement_value, target_columns, preserve_headers, file_type):
    """
    Process file content and return **bytes** for proper ContentFile saving.
    """
    try:
        # 1. Read file
        file.seek(0)
        if file_type == 'csv':
            df = pd.read_csv(file)
        else:
            # Force using openpyxl to read xlsx, avoiding engine differences
            df = pd.read_excel(file, engine='openpyxl')

        # 2. Column selection & replacement (keep your logic unchanged)
        if not target_columns:
            target_columns = df.columns.tolist()
        
        print(f"Description: {description}")
        print(f"Target columns: {target_columns}")
        print(f"Replacement value: {replacement_value}")
        
        for column in target_columns:
            if column in df.columns:
                print(f"Processing column: {column}")
                print(f"Original data: {df[column].tolist()}")
                
                df[column] = df[column].astype(str).apply(
                    lambda x: apply_simple_replacement(x, description, replacement_value)
                )
                print(f"Processed data: {df[column].tolist()}")

        # 3. Export as **bytes**:
        if file_type == 'csv':
            # CSV uses StringIO, then encode to bytes (add BOM for Excel compatibility)
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            data_bytes = buf.getvalue().encode('utf-8-sig')
        else:
            # Excel must use BytesIO
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Processed Data')
            data_bytes = buf.getvalue()

        return data_bytes
        
    except Exception as e:
        logger.error(f'File processing error: {str(e)}')
        raise e

def apply_simple_replacement(text, description, replacement_value):
    """
    Apply simple text replacement
    """
    try:
        # Perform simple text replacement based on description
        description_lower = description.lower()
        
        # If description contains "mask" or "hide", replace entire text with replacement value
        if 'mask' in description_lower or 'hide' in description_lower:
            return replacement_value
        
        # If description contains "replace", replace entire text with replacement value
        if 'replace' in description_lower:
            return replacement_value
        
        # By default, return original text
        return text
        
    except Exception as e:
        print(f"Replacement error: {e}")
        return text

@api_view(['GET'])
def get_processing_status(request, request_id):
    """
    Get processing status
    
    Returns: current processing status, progress, results, etc.
    """
    try:
        file_request = FileProcessingRequest.objects.get(id=request_id)
        
        return Response({
            'success': True,
            'data': {
                'request_id': file_request.id,
                'status': file_request.status,
                'progress': file_request.progress,
                'task_id': 'mock_task_id',
                'created_at': file_request.created_at,
                'started_at': file_request.started_at,
                'completed_at': file_request.completed_at
            }
        })
        
    except FileProcessingRequest.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Request not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Failed to get status',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def download_result(request, request_id):
    """
    Download processed result file
    
    Returns: processed file
    """
    from django.http import FileResponse, Http404
    import mimetypes
    from pathlib import Path
    
    try:
        fr = FileProcessingRequest.objects.get(id=request_id)

        # Must be processed file
        if not fr.processed_file:
            # If no output, return original file (or directly error, depends on your product logic)
            if not fr.original_file:
                raise Http404("File not found")
            f = fr.original_file
            download_name = Path(fr.original_file.name).name
        else:
            f = fr.processed_file
            download_name = Path(fr.processed_file.name).name  # ✅ Use real processed file name

        # Guess MIME type
        mime, _ = mimetypes.guess_type(download_name)
        mime = mime or 'application/octet-stream'

        # Use FileResponse for streaming, avoid read() into memory
        return FileResponse(
            f.open('rb'),
            as_attachment=True,
            filename=download_name,
            content_type=mime
        )

    except FileProcessingRequest.DoesNotExist:
        raise Http404("Request not found")
    except Exception as e:
        logger.error(f'Download error: {e}')
        return Response({'success': False, 'error': 'Download failed', 'details': str(e)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_processing_logs(request, request_id):
    """
    Get processing logs
    
    Returns: detailed logs of the processing process
    """
    try:
        file_request = FileProcessingRequest.objects.get(id=request_id)
        logs = ProcessingLog.objects.filter(request=file_request).order_by('-created_at')
        
        log_data = []
        for log in logs:
            log_data.append({
                'id': log.id,
                'level': log.level.upper(),
                'message': log.message,
                'details': log.details,
                'row_number': log.row_number,
                'column_name': log.column_name,
                'created_at': log.created_at
            })
        
        return Response({
            'success': True,
            'data': {
                'logs': log_data,
                'total': len(log_data)
            }
        })
        
    except FileProcessingRequest.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Request not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Failed to get logs',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_request_statistics(request, request_id):
    """
    Get request statistics
    
    Returns: processing statistics
    """
    try:
        file_request = FileProcessingRequest.objects.get(id=request_id)
        
        # Get processing result statistics
        stats = {
            'total_rows': 0,
            'successful_replacements': 0,
            'failed_replacements': 0,
            'processing_time': 0,
            'replacement_rate': 0
        }
        
        # Get total rows from file metadata
        if hasattr(file_request, 'file_metadata') and file_request.file_metadata:
            stats['total_rows'] = file_request.file_metadata.total_rows
        
        # Get replacement statistics from processing result
        if hasattr(file_request, 'processing_result') and file_request.processing_result:
            result = file_request.processing_result
            stats['successful_replacements'] = result.total_replacements
            stats['processing_time'] = result.processing_time or 0
            stats['replacement_rate'] = result.get_replacement_rate()
        
        # Calculate processing duration
        if file_request.started_at and file_request.completed_at:
            duration = file_request.completed_at - file_request.started_at
            stats['processing_time'] = duration.total_seconds()
        
        return Response({
            'success': True,
            'data': stats
        })
        
    except FileProcessingRequest.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Request not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'error': 'Failed to get statistics',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def health_check(request):
    """
    Health check
    
    Returns: system health status
    """
    try:
        # Check database connection
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        return Response({
            'success': True,
            'data': {
                'status': 'healthy',
                'database': 'connected',
                'celery': 'connected',
                'timestamp': timezone.now()
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'data': {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now()
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_processing_history(request):
    """
    Get processing history with pagination and filtering
    
    Query parameters:
    - page: Page number (default: 1)
    - page_size: Number of items per page (default: 20)
    - status: Filter by status (optional)
    
    Returns: paginated list of processing requests
    """
    try:
        # Get query parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        status_filter = request.GET.get('status')
        
        # Build queryset
        queryset = FileProcessingRequest.objects.all().order_by('-created_at')
        
        # Apply status filter if provided
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Calculate pagination
        total_count = queryset.count()
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        # Get paginated results
        requests = queryset[start_index:end_index]
        
        # Serialize the data
        history_data = []
        for req in requests:
            history_data.append({
                'id': req.id,
                'original_file_name': req.original_file_name,
                'file_type': req.file_type,
                'file_size': req.file_size,
                'natural_language_description': req.natural_language_description,
                'replacement_value': req.replacement_value,
                'target_columns': req.target_columns,
                'preserve_headers': req.preserve_headers,
                'status': req.status,
                'progress': req.progress,
                'current_step': req.current_step,
                'step_message': req.step_message,
                'eta_seconds': req.eta_seconds,
                'created_at': req.created_at,
                'started_at': req.started_at,
                'completed_at': req.completed_at,
                'download_url': f'/api/v1/download/{req.id}/' if req.processed_file else None,
                'preview_url': f'/api/v1/preview/{req.id}/1/',
                'logs_url': f'/api/v1/logs/{req.id}/',
                'stats_url': f'/api/v1/statistics/{req.id}/'
            })
        
        # Calculate pagination info
        total_pages = (total_count + page_size - 1) // page_size
        has_next = page < total_pages
        has_previous = page > 1
        
        return Response({
            'success': True,
            'data': {
                'results': history_data,
                'pagination': {
                    'current_page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': total_pages,
                    'has_next': has_next,
                    'has_previous': has_previous,
                    'next_page': page + 1 if has_next else None,
                    'previous_page': page - 1 if has_previous else None
                }
            }
        })
        
    except Exception as e:
        logger.error(f'History retrieval error: {str(e)}')
        return Response({
            'success': False,
            'error': 'Failed to retrieve processing history',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_request_detail(request, request_id):
    """
    Get detailed information about a specific processing request
    
    Returns: detailed request information
    """
    try:
        req = FileProcessingRequest.objects.get(id=request_id)
        
        # Get related metadata if exists
        metadata = None
        try:
            metadata_obj = FileMetadata.objects.get(request=req)
            metadata = {
                'total_rows': metadata_obj.total_rows,
                'total_columns': metadata_obj.total_columns,
                'headers': metadata_obj.headers,
                'encoding': metadata_obj.encoding,
                'sample_data': metadata_obj.sample_data,
                'parsed_at': metadata_obj.parsed_at
            }
        except FileMetadata.DoesNotExist:
            pass
        
        # Get processing result if exists
        result = None
        try:
            result_obj = ProcessingResult.objects.get(request=req)
            result = {
                'status': result_obj.status,
                'total_rows': result_obj.total_rows,
                'processed_rows': result_obj.processed_rows,
                'replacement_count': result_obj.replacement_count,
                'column_replacement_stats': result_obj.column_replacement_stats,
                'created_at': result_obj.created_at
            }
        except ProcessingResult.DoesNotExist:
            pass
        
        # Get recent logs (last 10)
        logs = ProcessingLog.objects.filter(request=req).order_by('-created_at')[:10]
        log_data = []
        for log in logs:
            log_data.append({
                'id': log.id,
                'level': log.level,
                'message': log.message,
                'created_at': log.created_at,
                'details': log.details
            })
        
        return Response({
            'success': True,
            'data': {
                'request': {
                    'id': req.id,
                    'original_file_name': req.original_file_name,
                    'file_type': req.file_type,
                    'file_size': req.file_size,
                    'natural_language_description': req.natural_language_description,
                    'replacement_value': req.replacement_value,
                    'target_columns': req.target_columns,
                    'preserve_headers': req.preserve_headers,
                    'status': req.status,
                    'progress': req.progress,
                    'current_step': req.current_step,
                    'step_message': req.step_message,
                    'eta_seconds': req.eta_seconds,
                    'created_at': req.created_at,
                    'started_at': req.started_at,
                    'completed_at': req.completed_at,
                    'download_url': f'/api/v1/download/{req.id}/' if req.processed_file else None,
                    'preview_url': f'/api/v1/preview/{req.id}/1/',
                    'logs_url': f'/api/v1/logs/{req.id}/',
                    'stats_url': f'/api/v1/statistics/{req.id}/'
                },
                'metadata': metadata,
                'result': result,
                'recent_logs': log_data
            }
        })
        
    except FileProcessingRequest.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Request not found'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f'Request detail retrieval error: {str(e)}')
        return Response({
            'success': False,
            'error': 'Failed to retrieve request details',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
def delete_request(request, request_id):
    """
    Delete a processing request and its associated files
    
    Returns: deletion confirmation
    """
    try:
        req = FileProcessingRequest.objects.get(id=request_id)
        
        # Delete associated files
        if req.original_file:
            req.original_file.delete(save=False)
        if req.processed_file:
            req.processed_file.delete(save=False)
        
        # Delete the request record
        req.delete()
        
        return Response({
            'success': True,
            'message': 'Request deleted successfully'
        })
        
    except FileProcessingRequest.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Request not found'
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f'Request deletion error: {str(e)}')
        return Response({
            'success': False,
            'error': 'Failed to delete request',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_global_statistics(request):
    """
    Get global processing statistics
    
    Returns: comprehensive system statistics including overview, file types, recent activity, and performance metrics
    """
    try:
        from django.db.models import Count, Q
        from datetime import datetime, timedelta
        
        # Calculate date ranges
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        
        # Overview statistics
        total_requests = FileProcessingRequest.objects.count()
        completed_requests = FileProcessingRequest.objects.filter(status='completed').count()
        failed_requests = FileProcessingRequest.objects.filter(status='failed').count()
        processing_requests = FileProcessingRequest.objects.filter(status='processing').count()
        pending_requests = FileProcessingRequest.objects.filter(status='pending').count()
        
        # Calculate success rate
        processed_requests = completed_requests + failed_requests
        success_rate = (completed_requests / processed_requests * 100) if processed_requests > 0 else 0
        
        overview = {
            'total_requests': total_requests,
            'completed_requests': completed_requests,
            'failed_requests': failed_requests,
            'processing_requests': processing_requests,
            'pending_requests': pending_requests,
            'success_rate': round(success_rate, 1)
        }
        
        # File type statistics
        file_type_stats = FileProcessingRequest.objects.values('file_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        file_types = [
            {'file_type': stat['file_type'], 'count': stat['count']}
            for stat in file_type_stats
        ]
        
        # Recent activity (last 24 hours)
        requests_last_24h = FileProcessingRequest.objects.filter(
            created_at__gte=last_24h
        ).count()
        
        recent_activity = {
            'requests_last_24h': requests_last_24h,
            'requests_last_7d': FileProcessingRequest.objects.filter(
                created_at__gte=last_7d
            ).count()
        }
        
        # Performance metrics
        completed_with_duration = FileProcessingRequest.objects.filter(
            status='completed',
            started_at__isnull=False,
            completed_at__isnull=False
        )
        
        avg_duration_seconds = None
        if completed_with_duration.exists():
            durations = []
            for req in completed_with_duration:
                if req.started_at and req.completed_at:
                    duration = (req.completed_at - req.started_at).total_seconds()
                    durations.append(duration)
            
            if durations:
                avg_duration_seconds = sum(durations) / len(durations)
        
        performance = {
            'avg_duration_seconds': round(avg_duration_seconds, 2) if avg_duration_seconds else None,
            'total_processing_time_hours': round(
                sum([(req.completed_at - req.started_at).total_seconds() 
                     for req in completed_with_duration 
                     if req.started_at and req.completed_at]) / 3600, 2
            ) if completed_with_duration.exists() else 0
        }
        
        # Status distribution for charts
        status_distribution = {
            'completed': completed_requests,
            'failed': failed_requests,
            'processing': processing_requests,
            'pending': pending_requests
        }
        
        # Recent requests (last 10)
        recent_requests = FileProcessingRequest.objects.order_by('-created_at')[:10]
        recent_requests_data = []
        for req in recent_requests:
            recent_requests_data.append({
                'id': req.id,
                'file_name': req.original_file_name,
                'file_type': req.file_type,
                'status': req.status,
                'created_at': req.created_at,
                'progress': req.progress
            })
        
        return Response({
            'success': True,
            'data': {
                'overview': overview,
                'file_types': file_types,
                'recent_activity': recent_activity,
                'performance': performance,
                'status_distribution': status_distribution,
                'recent_requests': recent_requests_data,
                'generated_at': now.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f'Global statistics error: {str(e)}')
        return Response({
            'success': False,
            'error': 'Failed to retrieve global statistics',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
