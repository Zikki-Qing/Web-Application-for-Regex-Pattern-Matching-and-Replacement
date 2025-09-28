import re
import pandas as pd
import json
import time
import os
import tempfile
from typing import Dict, List, Tuple, Optional
from django.core.files.uploadedfile import UploadedFile
from django.core.files.base import ContentFile
from django.utils import timezone
from .models import FileProcessingRequest, FileMetadata, GeneratedRegex, ProcessingResult, ProcessingLog


class FileParserService:
    """
    File parsing service - unified file parsing functionality
    """
    
    @staticmethod
    def parse_file(file: UploadedFile, file_type: str) -> Tuple[List[str], List[List[str]], Dict]:
        """
        Parse uploaded file
        
        Args:
            file: Uploaded file object
            file_type: File type (csv, xlsx, xls)
            
        Returns:
            tuple: (headers, rows_data, metadata)
        """
        try:
            if file_type in ['csv']:
                return FileParserService._parse_csv(file)
            elif file_type in ['xlsx', 'xls', 'excel']:
                return FileParserService._parse_excel(file)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
        except Exception as e:
            raise Exception(f"File parsing failed: {str(e)}")
    
    @staticmethod
    def _parse_csv(file: UploadedFile) -> Tuple[List[str], List[List[str]], Dict]:
        """Parse CSV file"""
        # Try different encodings
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
        df = None
        
        for encoding in encodings:
            try:
                file.seek(0)  # Reset file pointer
                df = pd.read_csv(file, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            raise Exception("Unable to parse file encoding")
        
        # Convert to list format
        headers = df.columns.tolist()
        rows_data = df.values.tolist()
        
        # Handle NaN values
        rows_data = [[str(cell) if pd.notna(cell) else '' for cell in row] for row in rows_data]
        
        metadata = {
            'encoding': encoding,
            'delimiter': ',',
            'total_rows': len(rows_data),
            'total_columns': len(headers)
        }
        
        return headers, rows_data, metadata
    
    @staticmethod
    def _parse_excel(file: UploadedFile) -> Tuple[List[str], List[List[str]], Dict]:
        """Parse Excel file"""
        try:
            file.seek(0)
            df = pd.read_excel(file, engine='openpyxl')
        except Exception as e:
            try:
                file.seek(0)
                df = pd.read_excel(file, engine='xlrd')
            except Exception as e2:
                raise Exception(f"Excel file parsing failed: {str(e2)}")
        
        # Convert to list format
        headers = df.columns.tolist()
        rows_data = df.values.tolist()
        
        # Handle NaN values
        rows_data = [[str(cell) if pd.notna(cell) else '' for cell in row] for row in rows_data]
        
        metadata = {
            'encoding': 'utf-8',
            'delimiter': None,
            'total_rows': len(rows_data),
            'total_columns': len(headers)
        }
        
        return headers, rows_data, metadata


class LLMService:
    """
    LLM service - generate regular expressions
    """
    
    @staticmethod
    def generate_regex(natural_language: str, replacement_value: str, 
                      sample_data: List[str] = None) -> Dict:
        """
        Generate regular expression based on natural language description
        
        Args:
            natural_language: Natural language description
            replacement_value: Replacement value
            sample_data: Sample data (optional)
            
        Returns:
            dict: Dictionary containing regex pattern and related information
        """
        start_time = time.time()
        
        try:
            # Here should call real LLM API
            # For now, simulate with rule-based matching
            regex_pattern, confidence = LLMService._mock_llm_generation(
                natural_language, replacement_value, sample_data
            )
            
            generation_time = time.time() - start_time
            
            return {
                'pattern': regex_pattern,
                'flags': {'ignorecase': True, 'multiline': True},
                'column_patterns': {},
                'confidence_score': confidence,
                'generation_time': generation_time
            }
            
        except Exception as e:
            raise Exception(f"LLM regex generation failed: {str(e)}")
    
    @staticmethod
    def _mock_llm_generation(natural_language: str, replacement_value: str, 
                           sample_data: List[str] = None) -> Tuple[str, float]:
        """
        Mock LLM regex generation (should call real LLM API in actual project)
        """
        # Simple rule-based matching
        natural_language = natural_language.lower()
        
        # Phone number matching
        if 'phone' in natural_language or 'mobile' in natural_language:
            if 'xxx-xxxx-xxxx' in replacement_value:
                return r'(\d{3})(\d{4})(\d{4})', 0.95
            elif 'xxx xxxx xxxx' in replacement_value:
                return r'(\d{3})(\d{4})(\d{4})', 0.95
        
        # Email matching
        elif 'email' in natural_language:
            return r'(\w+)@(\w+\.\w+)', 0.90
        
        # ID card matching
        elif 'id' in natural_language and 'card' in natural_language:
            return r'(\d{6})(\d{8})(\d{4})', 0.95
        
        # Default number matching
        elif 'number' in natural_language or 'digit' in natural_language:
            return r'(\d+)', 0.80
        
        # General text matching
        else:
            return r'(.+)', 0.70


class ProgressTracker:
    """
    Progress tracking service
    """
    
    def __init__(self, file_request: FileProcessingRequest):
        self.file_request = file_request
        self.start_time = time.time()
        self.step_start_time = time.time()
    
    def update_step(self, step: str, message: str, progress: int, eta_seconds: Optional[int] = None):
        """Update current step"""
        self.file_request.update_progress(
            progress=progress,
            step=step,
            message=message,
            eta_seconds=eta_seconds
        )
        
        # Log step
        ProcessingLog.objects.create(
            request=self.file_request,
            level='info',
            message=f"Step update: {step} - {message}",
            details={
                'step': step,
                'progress': progress,
                'eta_seconds': eta_seconds
            }
        )
        
        # Update step start time
        self.step_start_time = time.time()
    
    def update_progress(self, progress: int, message: str = None, eta_seconds: Optional[int] = None):
        """Update progress"""
        self.file_request.update_progress(
            progress=progress,
            message=message,
            eta_seconds=eta_seconds
        )
    
    def calculate_eta(self, current_progress: int, total_items: int, processed_items: int) -> int:
        """Calculate estimated remaining time"""
        if processed_items == 0:
            return None
        
        elapsed_time = time.time() - self.start_time
        items_per_second = processed_items / elapsed_time
        remaining_items = total_items - processed_items
        
        if items_per_second > 0:
            return int(remaining_items / items_per_second)
        return None
    
    def log_progress(self, level: str, message: str, details: Dict = None):
        """Log progress"""
        ProcessingLog.objects.create(
            request=self.file_request,
            level=level,
            message=message,
            details=details or {}
        )


class StepProgressCalculator:
    """
    Step progress calculator
    """
    
    # Progress ranges for each step
    STEP_PROGRESS_RANGES = {
        'parse': (0, 20),
        'generate_regex': (20, 40),
        'preview': (40, 50),
        'replace': (50, 90),
        'export': (90, 100),
    }
    
    @classmethod
    def get_step_progress(cls, step: str, sub_progress: float = 0.0) -> int:
        """Get step progress"""
        if step not in cls.STEP_PROGRESS_RANGES:
            return 0
        
        start, end = cls.STEP_PROGRESS_RANGES[step]
        return int(start + (end - start) * sub_progress)
    
    @classmethod
    def get_parse_progress(cls, total_rows: int, processed_rows: int) -> int:
        """Calculate parsing progress"""
        if total_rows == 0:
            return cls.get_step_progress('parse', 1.0)
        
        sub_progress = min(1.0, processed_rows / total_rows)
        return cls.get_step_progress('parse', sub_progress)
    
    @classmethod
    def get_replace_progress(cls, total_rows: int, processed_rows: int) -> int:
        """Calculate replacement progress"""
        if total_rows == 0:
            return cls.get_step_progress('replace', 1.0)
        
        sub_progress = min(1.0, processed_rows / total_rows)
        return cls.get_step_progress('replace', sub_progress)


class FileStorageService:
    """
    File storage service - handle file storage and reading
    """
    
    @staticmethod
    def save_uploaded_file(file_request: FileProcessingRequest, uploaded_file: UploadedFile):
        """
        Save uploaded file
        
        Args:
            file_request: File processing request object
            uploaded_file: Uploaded file object
        """
        # Save original file
        file_request.original_file.save(
            uploaded_file.name,
            uploaded_file,
            save=True
        )
        
        # Copy as current processing file
        file_request.current_file.save(
            f"current_{uploaded_file.name}",
            uploaded_file,
            save=True
        )
    
    @staticmethod
    def save_processed_file(file_request: FileProcessingRequest, processed_data: pd.DataFrame):
        """
        Save processed file
        
        Args:
            file_request: File processing request object
            processed_data: Processed DataFrame
        """
        # Save based on original file type
        if file_request.file_type in ['xlsx', 'xls']:
            # Save as Excel file
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
                processed_data.to_excel(tmp_file.name, index=False, engine='openpyxl')
                
                with open(tmp_file.name, 'rb') as f:
                    file_request.processed_file.save(
                        f"processed_{file_request.original_file_name}",
                        ContentFile(f.read()),
                        save=True
                    )
                
                os.unlink(tmp_file.name)
        else:
            # Save as CSV file
            with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tmp_file:
                processed_data.to_csv(tmp_file.name, index=False, encoding='utf-8')
                
                with open(tmp_file.name, 'rb') as f:
                    file_request.processed_file.save(
                        f"processed_{file_request.original_file_name}",
                        ContentFile(f.read()),
                        save=True
                    )
                
                os.unlink(tmp_file.name)
    
    @staticmethod
    def get_file_dataframe(file_request: FileProcessingRequest, file_type='current') -> pd.DataFrame:
        """
        Get file DataFrame
        
        Args:
            file_request: File processing request object
            file_type: File type ('original', 'current', 'processed')
            
        Returns:
            pd.DataFrame: File data
        """
        file_path = file_request.get_file_path(file_type)
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"File does not exist: {file_path}")
        
        # Read based on file type
        if file_request.file_type in ['xlsx', 'xls']:
            return pd.read_excel(file_path, engine='openpyxl')
        else:
            # Try different encodings
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            for encoding in encodings:
                try:
                    return pd.read_csv(file_path, encoding=encoding)
                except UnicodeDecodeError:
                    continue
            raise Exception("Unable to parse file encoding")
    
    @staticmethod
    def create_metadata(file_request: FileProcessingRequest, df: pd.DataFrame, encoding='utf-8', delimiter=','):
        """
        Create file metadata
        
        Args:
            file_request: File processing request object
            df: Data DataFrame
            encoding: File encoding
            delimiter: Delimiter
        """
        # Create metadata
        metadata = FileMetadata.objects.create(
            request=file_request,
            headers=df.columns.tolist(),
            total_rows=len(df),
            total_columns=len(df.columns),
            encoding=encoding,
            delimiter=delimiter,
            preview_data=df.head(5).values.tolist()
        )
        
        return metadata


class FileExportService:
    """
    File export service - directly stream file reading and return
    """
    
    @staticmethod
    def get_file_response(file_request: FileProcessingRequest, file_type='processed'):
        """
        Get file response
        
        Args:
            file_request: File processing request object
            file_type: File type ('original', 'current', 'processed')
            
        Returns:
            HttpResponse: File response
        """
        from django.http import HttpResponse, FileResponse
        import mimetypes
        
        file_path = file_request.get_file_path(file_type)
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"File does not exist: {file_path}")
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            if file_request.file_type in ['xlsx', 'xls']:
                mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            else:
                mime_type = 'text/csv'
        
        # Set filename
        if file_type == 'processed':
            filename = f"processed_{file_request.original_file_name}"
        else:
            filename = file_request.original_file_name
        
        # Return file response
        response = FileResponse(
            open(file_path, 'rb'),
            content_type=mime_type
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response


class StreamingFileProcessor:
    """
    Streaming file processor - use pandas streaming for large files
    """
    
    @staticmethod
    def process_file_streaming(file_request: FileProcessingRequest, 
                              regex_pattern: str, 
                              replacement_value: str,
                              target_columns: List[str] = None) -> Dict:
        """
        Stream process file - integrated progress tracking
        
        Args:
            file_request: File processing request object
            regex_pattern: Regex pattern
            replacement_value: Replacement value
            target_columns: Target column name list
            
        Returns:
            dict: Processing result statistics
        """
        import re
        
        # Create progress tracker
        tracker = ProgressTracker(file_request)
        
        try:
            # Update step: start replacement
            tracker.update_step(
                step='replace',
                message='Starting regex replacement...',
                progress=StepProgressCalculator.get_step_progress('replace', 0.0)
            )
            
            # Get current file DataFrame
            df = FileStorageService.get_file_dataframe(file_request, 'current')
            total_rows = len(df)
            
            # Determine columns to process
            if target_columns:
                target_columns = [col for col in target_columns if col in df.columns]
            else:
                target_columns = df.columns.tolist()
            
            # Statistics
            total_replacements = 0
            column_replacements = {}
            
            # Compile regex
            regex = re.compile(regex_pattern, re.IGNORECASE | re.MULTILINE)
            
            # Process each column
            for col_idx, column in enumerate(target_columns):
                if column in df.columns:
                    # Update progress message
                    tracker.update_progress(
                        progress=StepProgressCalculator.get_replace_progress(total_rows, 0),
                        message=f'Processing column: {column} ({col_idx + 1}/{len(target_columns)})'
                    )
                    
                    # Apply regex replacement
                    original_values = df[column].astype(str)
                    processed_values = original_values.apply(
                        lambda x: regex.sub(replacement_value, x)
                    )
                    
                    # Calculate replacement count
                    column_replacements[column] = (original_values != processed_values).sum()
                    total_replacements += column_replacements[column]
                    
                    # Update DataFrame
                    df[column] = processed_values
                    
                    # Log
                    if column_replacements[column] > 0:
                        tracker.log_progress(
                            level='info',
                            message=f"Column {column} replaced {column_replacements[column]} values",
                            details={
                                'column': column,
                                'replacements': column_replacements[column],
                                'pattern': regex_pattern,
                                'replacement': replacement_value
                            }
                        )
                    
                    # Update progress
                    progress = StepProgressCalculator.get_replace_progress(
                        total_rows, 
                        (col_idx + 1) / len(target_columns)
                    )
                    eta = tracker.calculate_eta(progress, total_rows, col_idx + 1)
                    
                    tracker.update_progress(
                        progress=progress,
                        message=f'Processed column: {column}',
                        eta_seconds=eta
                    )
            
            # Update step: start export
            tracker.update_step(
                step='export',
                message='Exporting processing results...',
                progress=StepProgressCalculator.get_step_progress('export', 0.0)
            )
            
            # Save processed file
            FileStorageService.save_processed_file(file_request, df)
            
            # Update progress: export complete
            tracker.update_progress(
                progress=100,
                message='Processing completed',
                eta_seconds=0
            )
            
            processing_time = time.time() - tracker.start_time
            
            # Create processing result
            result = ProcessingResult.objects.create(
                request=file_request,
                total_replacements=total_replacements,
                column_replacements=column_replacements,
                processing_time=processing_time
            )
            
            return {
                'total_replacements': total_replacements,
                'column_replacements': column_replacements,
                'processing_time': processing_time,
                'result_id': result.id
            }
            
        except Exception as e:
            # Log error
            tracker.log_progress(
                level='error',
                message=f'Streaming processing failed: {str(e)}',
                details={'error': str(e)}
            )
            raise e


class FileProcessingService:
    """
    File processing service - main file processing logic (compatibility wrapper)
    """
    
    @staticmethod
    def parse_file(file, file_type):
        """
        Parse file and return header information and data (compatibility method)
        
        Args:
            file: Uploaded file object
            file_type: File type ('csv', 'xlsx', 'xls')
            
        Returns:
            tuple: (headers, rows_data, metadata)
        """
        return FileParserService.parse_file(file, file_type)
    
    @staticmethod
    def process_file_request(request_id):
        """
        Process file request
        
        Args:
            request_id: File processing request ID
            
        Returns:
            ProcessingResult: Processing result object
        """
        try:
            # Get file request
            file_request = FileProcessingRequest.objects.get(id=request_id)
            
            # Update status to processing
            file_request.status = 'processing'
            file_request.started_at = timezone.now()
            file_request.save()
            
            # Here can add specific processing logic
            # For now return a basic result object
            result = ProcessingResult.objects.create(
                request=file_request,
                status='completed',
                total_rows=0,
                processed_rows=0,
                replacement_count=0
            )
            
            # Update status to completed
            file_request.status = 'completed'
            file_request.completed_at = timezone.now()
            file_request.save()
            
            return result
            
        except FileProcessingRequest.DoesNotExist:
            raise Exception(f"File processing request does not exist: {request_id}")
        except Exception as e:
            # Update status to failed
            try:
                file_request = FileProcessingRequest.objects.get(id=request_id)
                file_request.status = 'failed'
                file_request.completed_at = timezone.now()
                file_request.save()
            except:
                pass
            raise Exception(f"File processing failed: {str(e)}")
    @staticmethod
    def get_file_preview(file):
        """
        Get file preview information
        
        Args:
            file: File object
            
        Returns:
            dict: Preview information containing headers and sample_data
        """
        try:
            # Determine file type
            file_name = file.name.lower()
            if file_name.endswith('.csv'):
                file_type = 'csv'
            elif file_name.endswith(('.xlsx', '.xls')):
                file_type = 'excel'
            else:
                return {'headers': [], 'sample_data': []}
            
            # Parse file to get headers
            headers, rows_data, metadata = FileParserService.parse_file(file, file_type)
            
            # Get first few rows as sample data
            sample_data = rows_data[:5] if rows_data else []
            
            return {
                'headers': headers,
                'sample_data': sample_data,
                'total_rows': len(rows_data),
                'file_type': file_type
            }
            
        except Exception as e:
            logger.error(f'File preview error: {str(e)}')
            return {'headers': [], 'sample_data': []}
