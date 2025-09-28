from celery import shared_task
from celery.exceptions import Retry
from django.core.mail import send_mail
from django.conf import settings
import logging
import traceback

from .models import FileProcessingRequest, ProcessingLog
from .services import FileStorageService, StreamingFileProcessor, ProgressTracker, StepProgressCalculator

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_file_task(self, request_id):
    """
    Process file task - use streaming processing and progress tracking
    
    Args:
        request_id: File processing request ID
        
    Returns:
        dict: Processing result
    """
    try:
        logger.info(f"Starting file processing task: {request_id}")
        
        # Get file request
        file_request = FileProcessingRequest.objects.get(id=request_id)
        
        # Start processing
        file_request.start_processing()
        
        # Create progress tracker
        tracker = ProgressTracker(file_request)
        
        # 1. Parse file
        tracker.update_step(
            step='parse',
            message='Parsing file...',
            progress=StepProgressCalculator.get_step_progress('parse', 0.0)
        )
        
        try:
            df = FileStorageService.get_file_dataframe(file_request, 'original')
            metadata = FileStorageService.create_metadata(file_request, df)
            
            # Update parsing completion progress
            tracker.update_step(
                step='parse',
                message=f'File parsing completed: {metadata.total_rows} rows x {metadata.total_columns} columns',
                progress=StepProgressCalculator.get_step_progress('parse', 1.0)
            )
            
        except Exception as e:
            tracker.log_progress('error', f'File parsing failed: {str(e)}')
            raise e
        
        # 2. Generate regex
        tracker.update_step(
            step='generate_regex',
            message='Generating regex...',
            progress=StepProgressCalculator.get_step_progress('generate_regex', 0.0)
        )
        
        from .services import LLMService
        sample_data = metadata.get_preview_data(5)
        regex_info = LLMService.generate_regex(
            file_request.natural_language_description,
            file_request.replacement_value,
            sample_data
        )
        
        # Save generated regex
        from .models import GeneratedRegex
        GeneratedRegex.objects.create(
            request=file_request,
            **regex_info
        )
        
        # Update regex generation completion progress
        tracker.update_step(
            step='generate_regex',
            message=f'Regex generation completed: {regex_info["pattern"]}',
            progress=StepProgressCalculator.get_step_progress('generate_regex', 1.0)
        )
        
        # 3. Preview data
        tracker.update_step(
            step='preview',
            message='Previewing data...',
            progress=StepProgressCalculator.get_step_progress('preview', 0.0)
        )
        
        # Here can add data preview logic
        tracker.update_step(
            step='preview',
            message='Data preview completed',
            progress=StepProgressCalculator.get_step_progress('preview', 1.0)
        )
        
        # 4. Stream process file
        result = StreamingFileProcessor.process_file_streaming(
            file_request,
            regex_info['pattern'],
            file_request.replacement_value,
            file_request.target_columns
        )
        
        # 5. Complete processing
        file_request.complete_processing()
        
        logger.info(f"File processing completed: {request_id}")
        
        return {
            'status': 'SUCCESS',
            'request_id': request_id,
            'result_id': result['result_id'],
            'message': 'File processing completed',
            'statistics': {
                'total_replacements': result['total_replacements'],
                'processing_time': result['processing_time']
            }
        }
        
    except FileProcessingRequest.DoesNotExist:
        logger.error(f"File processing request does not exist: {request_id}")
        return {
            'status': 'FAILURE',
            'request_id': request_id,
            'error': 'File processing request does not exist'
        }
        
    except Exception as exc:
        logger.error(f"File processing failed: {request_id}, error: {str(exc)}")
        
        # Update status to failed
        try:
            file_request = FileProcessingRequest.objects.get(id=request_id)
            file_request.fail_processing(str(exc))
        except:
            pass
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying file processing task: {request_id}, attempt {self.request.retries + 1}")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        
        return {
            'status': 'FAILURE',
            'request_id': request_id,
            'error': str(exc),
            'retries': self.request.retries
        }

@shared_task
def cleanup_old_tasks():
    """
    Clean up old task data
    
    Periodically clean up failed tasks and logs older than 7 days
    """
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        # Clean up failed requests from 7 days ago
        cutoff_date = timezone.now() - timedelta(days=7)
        
        old_requests = FileProcessingRequest.objects.filter(
            status='failed',
            created_at__lt=cutoff_date
        )
        
        count = old_requests.count()
        old_requests.delete()
        
        logger.info(f"Cleaned up {count} old tasks")
        
        return {
            'status': 'SUCCESS',
            'cleaned_count': count
        }
        
    except Exception as exc:
        logger.error(f"Cleanup task failed: {str(exc)}")
        return {
            'status': 'FAILURE',
            'error': str(exc)
        }

@shared_task
def send_notification_email(request_id, status, message):
    """
    Send notification email
    
    Args:
        request_id: Request ID
        status: Processing status
        message: Message content
    """
    try:
        file_request = FileProcessingRequest.objects.get(id=request_id)
        
        subject = f"File processing {status} - {file_request.original_file_name}"
        message = f"""
        File processing {status} notification
        
        File name: {file_request.original_file_name}
        Request ID: {request_id}
        Status: {status}
        Message: {message}
        
        Processing time: {file_request.updated_at}
        """
        
        # Email settings need to be configured here
        # send_mail(
        #     subject,
        #     message,
        #     settings.DEFAULT_FROM_EMAIL,
        #     [user_email],
        #     fail_silently=False,
        # )
        
        logger.info(f"Sent notification email: {request_id}")
        
    except Exception as exc:
        logger.error(f"Failed to send email: {str(exc)}")

@shared_task
def health_check():
    """
    Health check task
    
    Check system status and task queue
    """
    try:
        from .models import FileProcessingRequest
        
        # Count tasks by status
        stats = {
            'pending': FileProcessingRequest.objects.filter(status='pending').count(),
            'processing': FileProcessingRequest.objects.filter(status='processing').count(),
            'completed': FileProcessingRequest.objects.filter(status='completed').count(),
            'failed': FileProcessingRequest.objects.filter(status='failed').count(),
        }
        
        logger.info(f"System status: {stats}")
        
        return {
            'status': 'HEALTHY',
            'stats': stats
        }
        
    except Exception as exc:
        logger.error(f"Health check failed: {str(exc)}")
        return {
            'status': 'UNHEALTHY',
            'error': str(exc)
        } 