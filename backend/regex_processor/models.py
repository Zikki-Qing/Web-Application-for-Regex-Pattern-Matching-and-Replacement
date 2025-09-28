from django.db import models
from django.utils import timezone
from django.core.files.storage import FileSystemStorage
from django.core.exceptions import ValidationError
import json
import os

# Custom file storage
file_storage = FileSystemStorage(location='media/processed_files/')

class FileProcessingRequest(models.Model):
    """
    File processing request model - stores user-submitted natural language descriptions and file processing requirements
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    STEP_CHOICES = [
        ('parse', 'Parse file'),
        ('generate_regex', 'Generate regex'),
        ('preview', 'Preview data'),
        ('replace', 'Execute replacement'),
        ('export', 'Export result'),
    ]
    
    FILE_TYPE_CHOICES = [
        ('csv', 'CSV file'),
        ('excel', 'Excel file'),
        ('xlsx', 'Excel 2007+'),
        ('xls', 'Excel 97-2003'),
    ]
    
    # Basic information
    natural_language_description = models.TextField(
        verbose_name="Natural language description",
        help_text="User-described requirements, e.g.: Format all phone numbers as xxx-xxxx-xxxx"
    )
    replacement_value = models.TextField(
        verbose_name="Replacement value",
        help_text="Target format or content for replacement"
    )
    
    # File information
    original_file_name = models.CharField(
        max_length=255,
        verbose_name="Original file name"
    )
    file_type = models.CharField(
        max_length=10,
        choices=FILE_TYPE_CHOICES,
        verbose_name="File type"
    )
    file_size = models.PositiveIntegerField(
        verbose_name="File size (bytes)"
    )
    
    # File storage paths
    original_file = models.FileField(
        upload_to='original_files/',
        storage=file_storage,
        verbose_name="Original file",
        help_text="Uploaded original file"
    )
    current_file = models.FileField(
        upload_to='current_files/',
        storage=file_storage,
        null=True,
        blank=True,
        verbose_name="Current processing file",
        help_text="Currently processing file"
    )
    processed_file = models.FileField(
        upload_to='processed_files/',
        storage=file_storage,
        null=True,
        blank=True,
        verbose_name="Processed result file",
        help_text="File after processing completion"
    )
    
    # Processing configuration
    target_columns = models.JSONField(
        default=list,
        verbose_name="Target columns",
        help_text="List of column names to process, empty list means process all columns"
    )
    preserve_headers = models.BooleanField(
        default=True,
        verbose_name="Preserve headers"
    )
    
    # Status management
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Processing status"
    )
    
    # Progress tracking
    progress = models.PositiveIntegerField(
        default=0,
        verbose_name="Progress percentage",
        help_text="Progress percentage from 0-100"
    )
    current_step = models.CharField(
        max_length=20,
        choices=STEP_CHOICES,
        null=True,
        blank=True,
        verbose_name="Current step"
    )
    step_message = models.TextField(
        null=True,
        blank=True,
        verbose_name="Step message",
        help_text="Detailed description of current step"
    )
    eta_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Estimated remaining time (seconds)",
        help_text="Estimated time to complete remaining tasks"
    )
    
    # Task ID (Celery)
    task_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Celery task ID"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Created at"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated at"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Processing start time"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Completion time"
    )
    
    # Metadata
    user_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="User IP"
    )
    
    class Meta:
        verbose_name = "File processing request"
        verbose_name_plural = "File processing requests"
        ordering = ['-created_at']
        # Add database constraints
        constraints = [
            models.CheckConstraint(
                check=models.Q(progress__gte=0) & models.Q(progress__lte=100),
                name='progress_range_check'
            ),
            models.CheckConstraint(
                check=models.Q(eta_seconds__isnull=True) | models.Q(eta_seconds__gte=0),
                name='eta_seconds_positive_check'
            ),
        ]
    
    def __str__(self):
        return f"File processing {self.id}: {self.original_file_name}"
    
    def clean(self):
        """Validate state transition legality"""
        super().clean()
        
        # State transition rules
        valid_transitions = {
            'pending': ['processing', 'failed'],
            'processing': ['completed', 'failed'],
            'completed': [],  # Completed state cannot transition
            'failed': ['pending'],  # Failed state can restart
        }
        
        if self.pk:  # Only validate existing objects
            old_instance = FileProcessingRequest.objects.get(pk=self.pk)
            if old_instance.status != self.status:
                if self.status not in valid_transitions.get(old_instance.status, []):
                    raise ValidationError(
                        f"Invalid state transition: {old_instance.status} -> {self.status}"
                    )
    
    def get_file_path(self, file_type='original'):
        """Get file path"""
        if file_type == 'original':
            return self.original_file.path if self.original_file else None
        elif file_type == 'current':
            return self.current_file.path if self.current_file else None
        elif file_type == 'processed':
            return self.processed_file.path if self.processed_file else None
        return None
    
    def update_progress(self, progress, step=None, message=None, eta_seconds=None):
        """Update progress information"""
        self.progress = min(100, max(0, progress))
        if step:
            self.current_step = step
        if message:
            self.step_message = message
        if eta_seconds is not None:
            self.eta_seconds = eta_seconds
        self.save(update_fields=['progress', 'current_step', 'step_message', 'eta_seconds', 'updated_at'])
    
    def start_processing(self):
        """Start processing"""
        self.status = 'processing'
        self.started_at = timezone.now()
        self.progress = 0
        self.current_step = 'parse'
        self.step_message = 'Starting file processing...'
        self.save()
    
    def complete_processing(self):
        """Complete processing"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.progress = 100
        self.current_step = 'export'
        self.step_message = 'Processing completed'
        self.eta_seconds = 0
        self.save()
    
    def fail_processing(self, error_message):
        """Processing failed"""
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.step_message = f'Processing failed: {error_message}'
        self.eta_seconds = 0
        self.save()
    
    def get_estimated_completion_time(self):
        """Get estimated completion time"""
        if self.eta_seconds and self.started_at:
            from datetime import timedelta
            return self.started_at + timedelta(seconds=self.eta_seconds)
        return None


class FileMetadata(models.Model):
    """
    File metadata model - stores file metadata, not actual data
    """
    request = models.OneToOneField(
        FileProcessingRequest,
        on_delete=models.CASCADE,
        related_name='file_metadata',
        verbose_name="Associated request"
    )
    
    # File basic information
    headers = models.JSONField(
        default=list,
        verbose_name="Header list"
    )
    total_rows = models.PositiveIntegerField(
        default=0,
        verbose_name="Total rows"
    )
    total_columns = models.PositiveIntegerField(
        default=0,
        verbose_name="Total columns"
    )
    
    # File format information
    encoding = models.CharField(
        max_length=20,
        default='utf-8',
        verbose_name="File encoding"
    )
    delimiter = models.CharField(
        max_length=5,
        null=True,
        blank=True,
        verbose_name="Delimiter",
        help_text="CSV file delimiter"
    )
    
    # Preview data (only store first few rows for display)
    preview_data = models.JSONField(
        default=list,
        verbose_name="Preview data",
        help_text="First 5 rows of data for preview"
    )
    
    # Timestamp
    parsed_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Parse time"
    )
    
    class Meta:
        verbose_name = "File metadata"
        verbose_name_plural = "File metadata"
    
    def __str__(self):
        return f"File metadata {self.id}: {self.total_rows} rows x {self.total_columns} columns"
    
    def get_preview_data(self, limit=5):
        """Get preview data"""
        return self.preview_data[:limit] if self.preview_data else []


class GeneratedRegex(models.Model):
    """
    Generated regex model - stores LLM-generated regular expressions
    """
    request = models.OneToOneField(
        FileProcessingRequest,
        on_delete=models.CASCADE,
        related_name='generated_regex',
        verbose_name="Associated request"
    )
    
    # Regex information
    pattern = models.TextField(
        verbose_name="Regex pattern",
        help_text="LLM-generated regular expression"
    )
    flags = models.JSONField(
        default=dict,
        verbose_name="Regex flags",
        help_text="Regex flags such as ignorecase, etc."
    )
    
    # Column-level regex (if different columns need different processing)
    column_patterns = models.JSONField(
        default=dict,
        verbose_name="Column-level regex",
        help_text="Regex for different columns, format: {'column_name': 'regex'}"
    )
    
    # Generation information
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Confidence score",
        help_text="LLM-generated confidence score (0-1)"
    )
    generation_time = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Generation time (seconds)"
    )
    
    # Timestamp
    generated_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Generation time"
    )
    
    class Meta:
        verbose_name = "Generated regex"
        verbose_name_plural = "Generated regex"
    
    def __str__(self):
        return f"Regex {self.id}: {self.pattern[:30]}..."


class ProcessingResult(models.Model):
    """
    Processing result model - stores processed file data
    """
    request = models.OneToOneField(
        FileProcessingRequest,
        on_delete=models.CASCADE,
        related_name='processing_result',
        verbose_name="Associated request"
    )
    
    # Processing statistics
    total_replacements = models.PositiveIntegerField(
        default=0,
        verbose_name="Total replacements"
    )
    column_replacements = models.JSONField(
        default=dict,
        verbose_name="Column replacements",
        help_text="Format: {'column_name': replacement_count}"
    )
    processing_time = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Processing time (seconds)"
    )
    
    # Error information
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name="Error message"
    )
    error_details = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        verbose_name="Error details"
    )
    
    # Timestamp
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Result generation time"
    )
    
    class Meta:
        verbose_name = "Processing result"
        verbose_name_plural = "Processing results"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Result {self.id}: {self.total_replacements} replacements"
    
    def get_replacement_rate(self):
        """Calculate replacement rate"""
        if not self.request.file_metadata:
            return 0
        total_cells = self.request.file_metadata.total_columns * self.request.file_metadata.total_rows
        return (self.total_replacements / total_cells) * 100 if total_cells > 0 else 0


class ProcessingLog(models.Model):
    """
    Processing log model - records detailed logs of the processing process
    """
    LOG_LEVEL_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('debug', 'Debug'),
    ]
    
    request = models.ForeignKey(
        FileProcessingRequest,
        on_delete=models.CASCADE,
        related_name='processing_logs',
        verbose_name="Associated request"
    )
    
    level = models.CharField(
        max_length=10,
        choices=LOG_LEVEL_CHOICES,
        verbose_name="Log level"
    )
    message = models.TextField(
        verbose_name="Log message"
    )
    details = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        verbose_name="Details"
    )
    
    # Location information (for problem identification)
    row_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Row number"
    )
    column_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Column name"
    )
    
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Record time"
    )
    
    class Meta:
        verbose_name = "Processing log"
        verbose_name_plural = "Processing logs"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.level.upper()}: {self.message[:50]}..."
