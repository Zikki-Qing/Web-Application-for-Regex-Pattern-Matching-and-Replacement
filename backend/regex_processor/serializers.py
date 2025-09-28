from rest_framework import serializers
from .models import FileProcessingRequest, FileMetadata, GeneratedRegex, ProcessingResult, ProcessingLog
import json


class FileProcessingRequestSerializer(serializers.ModelSerializer):
    """
    File processing request serializer
    """
    class Meta:
        model = FileProcessingRequest
        fields = [
            'id', 'natural_language_description', 'replacement_value',
            'original_file_name', 'file_type', 'file_size',
            'target_columns', 'preserve_headers', 'status',
            'progress', 'current_step', 'step_message', 'eta_seconds',
            'created_at', 'updated_at', 'started_at', 'completed_at'
        ]
        read_only_fields = ['id', 'status', 'progress', 'current_step', 'step_message', 'eta_seconds', 'created_at', 'updated_at', 'started_at', 'completed_at']


class FileMetadataSerializer(serializers.ModelSerializer):
    """
    File metadata serializer
    """
    class Meta:
        model = FileMetadata
        fields = [
            'id', 'headers', 'total_rows', 'total_columns',
            'encoding', 'delimiter', 'preview_data', 'parsed_at'
        ]
        read_only_fields = ['id', 'parsed_at']


class GeneratedRegexSerializer(serializers.ModelSerializer):
    """
    Generated regex serializer
    """
    class Meta:
        model = GeneratedRegex
        fields = [
            'id', 'pattern', 'flags', 'column_patterns',
            'confidence_score', 'generation_time', 'generated_at'
        ]
        read_only_fields = ['id', 'generated_at']


class ProcessingResultSerializer(serializers.ModelSerializer):
    """
    Processing result serializer
    """
    replacement_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = ProcessingResult
        fields = [
            'id', 'total_replacements', 'column_replacements',
            'processing_time', 'error_message', 'error_details',
            'replacement_rate', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_replacement_rate(self, obj):
        return obj.get_replacement_rate()


class ProcessingLogSerializer(serializers.ModelSerializer):
    """
    Processing log serializer
    """
    class Meta:
        model = ProcessingLog
        fields = [
            'id', 'level', 'message', 'details',
            'row_number', 'column_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class FileUploadSerializer(serializers.Serializer):
    """
    File upload serializer
    """
    file = serializers.FileField(
        help_text="Uploaded CSV or Excel file (supports .csv, .xlsx, .xls formats)"
    )
    natural_language_description = serializers.CharField(
        max_length=1000,
        help_text="Natural language description, e.g.: Format all phone numbers as xxx-xxxx-xxxx"
    )
    replacement_value = serializers.CharField(
        max_length=500,
        help_text="Replacement value, e.g.: xxx-xxxx-xxxx"
    )
    target_columns = serializers.JSONField(
        required=False,
        default=list,
        help_text="List of target column names"
    )
    preserve_headers = serializers.BooleanField(
        default=True,
        help_text="Whether to preserve headers"
    )
    
    def validate_file(self, value):
        """Validate file type and size"""
        # Check file type
        allowed_extensions = ['.csv', '.xlsx', '.xls']
        file_extension = value.name.lower().split('.')[-1]
        if f'.{file_extension}' not in allowed_extensions:
            raise serializers.ValidationError(
                f"Unsupported file type. Supported types: {', '.join(allowed_extensions)}"
            )
        
        # Check file size (limit to 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 10MB")
        
        return value
    
    def validate_target_columns(self, value):
        """Validate target_columns field"""
        if not value:
            return []
        
        if not isinstance(value, list):
            raise serializers.ValidationError("target_columns must be a list")
        
        return value


class ProcessingStatusSerializer(serializers.Serializer):
    """
    Processing status serializer
    """
    request_id = serializers.IntegerField()
    status = serializers.CharField()
    progress = serializers.FloatField()
    current_step = serializers.CharField()
    step_message = serializers.CharField()
    eta_seconds = serializers.IntegerField()
    message = serializers.CharField()
    result_url = serializers.URLField(required=False)
    error_details = serializers.DictField(required=False)
