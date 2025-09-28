from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    FileProcessingRequest, FileMetadata, GeneratedRegex, 
    ProcessingResult, ProcessingLog
)


@admin.register(FileProcessingRequest)
class FileProcessingRequestAdmin(admin.ModelAdmin):
    """
    File processing request management
    """
    list_display = [
        'id', 'original_file_name', 'file_type', 'file_size_mb',
        'status', 'progress_display', 'current_step', 'created_at'
    ]
    list_filter = [
        'status', 'file_type', 'current_step', 'created_at'
    ]
    search_fields = [
        'original_file_name', 'natural_language_description', 
        'replacement_value', 'id'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'started_at', 'completed_at',
        'progress_display', 'eta_display', 'file_size_mb'
    ]
    fieldsets = [
        ('Basic Information', {
            'fields': [
                'id', 'original_file_name', 'file_type', 'file_size_mb',
                'natural_language_description', 'replacement_value'
            ]
        }),
        ('Processing Configuration', {
            'fields': [
                'target_columns', 'preserve_headers', 'case_sensitive'
            ]
        }),
        ('Status Information', {
            'fields': [
                'status', 'progress_display', 'current_step', 'step_message',
                'eta_display', 'started_at', 'completed_at'
            ]
        }),
        ('Time Information', {
            'fields': ['created_at', 'updated_at']
        })
    ]
    
    def progress_display(self, obj):
        """Progress display"""
        if obj.progress is None:
            return "Not started"
        return f"{obj.progress}%"
    progress_display.short_description = "Progress"
    
    def eta_display(self, obj):
        """Estimated completion time display"""
        if obj.eta_seconds is None:
            return "Unknown"
        return f"{obj.eta_seconds} seconds"
    eta_display.short_description = "Estimated remaining time"
    
    def file_size_mb(self, obj):
        """File size display"""
        if obj.file_size is None:
            return "Unknown"
        return f"{obj.file_size / 1024 / 1024:.2f} MB"
    file_size_mb.short_description = "File size"


@admin.register(FileMetadata)
class FileMetadataAdmin(admin.ModelAdmin):
    """
    File metadata management
    """
    list_display = [
        'id', 'request_link', 'total_rows', 'total_columns',
        'encoding', 'parsed_at'
    ]
    list_filter = ['encoding', 'parsed_at']
    search_fields = ['request__id', 'request__original_file_name']
    readonly_fields = ['id', 'parsed_at']
    
    def request_link(self, obj):
        """Request link"""
        url = reverse('admin:regex_processor_fileprocessingrequest_change', args=[obj.request.id])
        return format_html('<a href="{}">Request #{}</a>', url, obj.request.id)
    request_link.short_description = "Associated request"


@admin.register(GeneratedRegex)
class GeneratedRegexAdmin(admin.ModelAdmin):
    """
    Generated regex management
    """
    list_display = [
        'id', 'request_link', 'pattern_preview', 'confidence_score',
        'generated_at'
    ]
    list_filter = ['confidence_score', 'generated_at']
    search_fields = ['request__id', 'pattern']
    readonly_fields = ['id', 'generated_at']
    
    def request_link(self, obj):
        """Request link"""
        url = reverse('admin:regex_processor_fileprocessingrequest_change', args=[obj.request.id])
        return format_html('<a href="{}">Request #{}</a>', url, obj.request.id)
    request_link.short_description = "Associated request"
    
    def pattern_preview(self, obj):
        """Regex pattern preview"""
        if len(obj.pattern) > 50:
            return f"{obj.pattern[:50]}..."
        return obj.pattern
    pattern_preview.short_description = "Regex pattern"


@admin.register(ProcessingResult)
class ProcessingResultAdmin(admin.ModelAdmin):
    """
    Processing result management
    """
    list_display = [
        'id', 'request_link', 'total_replacements', 'processing_time',
        'created_at'
    ]
    list_filter = ['created_at']
    search_fields = ['request__id', 'request__original_file_name']
    readonly_fields = ['id', 'created_at']
    
    def request_link(self, obj):
        """Request link"""
        url = reverse('admin:regex_processor_fileprocessingrequest_change', args=[obj.request.id])
        return format_html('<a href="{}">Request #{}</a>', url, obj.request.id)
    request_link.short_description = "Associated request"


@admin.register(ProcessingLog)
class ProcessingLogAdmin(admin.ModelAdmin):
    """
    Processing log management
    """
    list_display = [
        'id', 'request_link', 'level', 'message_preview', 'created_at'
    ]
    list_filter = ['level', 'created_at']
    search_fields = [
        'request__id', 'message', 'request__original_file_name'
    ]
    readonly_fields = ['id', 'created_at']
    
    def request_link(self, obj):
        """Request link"""
        url = reverse('admin:regex_processor_fileprocessingrequest_change', args=[obj.request.id])
        return format_html('<a href="{}">Request #{}</a>', url, obj.request.id)
    request_link.short_description = "Associated request"
    
    def message_preview(self, obj):
        """Message preview"""
        if len(obj.message) > 100:
            return f"{obj.message[:100]}..."
        return obj.message
    message_preview.short_description = "Log message"


# Custom Admin site titles
admin.site.site_header = "Regex Processing System"
admin.site.site_title = "Regex Processor Admin"
admin.site.index_title = "Data Management"
