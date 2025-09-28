# File Processing System

A full-stack web application for processing CSV and Excel files with natural language instructions for text replacement and data transformation.

## Project Structure

```
myproject/
├── backend/                    # Django REST API backend
│   ├── manage.py              # Django management script
│   ├── db.sqlite3             # SQLite database (development)
│   ├── myproject/             # Django project settings
│   │   ├── __init__.py
│   │   ├── settings.py        # Django configuration
│   │   ├── urls.py            # Main URL routing
│   │   └── celery.py          # Celery configuration
│   ├── regex_processor/       # Main Django application
│   │   ├── admin.py           # Django admin interface
│   │   ├── models.py          # Database models
│   │   ├── views.py           # API endpoints
│   │   ├── serializers.py     # Data serialization
│   │   ├── services.py        # Business logic
│   │   ├── tasks.py           # Celery tasks
│   │   ├── urls.py            # App URL routing
│   │   ├── migrations/        # Database migrations
│   │   └── test_urls.py       # URL testing utilities
│   ├── media/                 # File upload storage
│   │   └── processed_files/
│   │       └── original_files/
│   └── start_celery.sh        # Celery worker startup script
└── frontend/                   # React frontend application
    ├── public/                 # Static assets
    ├── src/                    # Source code
    │   ├── components/         # Reusable components
    │   ├── pages/              # Page components
    │   │   ├── UploadPage.jsx      # File upload interface
    │   │   ├── TaskDetailPage.jsx  # Task status and results
    │   │   ├── HistoryPage.jsx     # Processing history
    │   │   ├── GlobalStatsPage.jsx # System statistics
    │   │   ├── HealthPage.jsx      # System health check
    │   │   └── NotFoundPage.jsx    # 404 error page
    │   ├── services/           # API services
    │   │   ├── api.js          # JavaScript API client
    │   │   └── api.ts          # TypeScript API client
    │   ├── types/              # TypeScript type definitions
    │   ├── utils/              # Utility functions
    │   ├── App.js              # Main application component
    │   ├── App.css             # Application styles
    │   ├── index.js            # Application entry point
    │   └── index.css           # Global styles
    ├── package.json            # Node.js dependencies
    ├── package-lock.json       # Dependency lock file
    └── tsconfig.json           # TypeScript configuration
```

## Features

- **File Upload**: Support for CSV and Excel files (.csv, .xlsx)
- **Natural Language Processing**: Describe transformations in plain English
- **Column Selection**: Choose specific columns for processing
- **Real-time Processing**: Track processing status and progress
- **File Download**: Download processed results
- **Processing History**: View past processing requests
- **System Statistics**: Monitor system performance and usage
- **Health Monitoring**: Check system status and API health

## Technology Stack

### Backend
- **Django 4.x**: Web framework
- **Django REST Framework**: API development
- **SQLite**: Database (development)
- **Celery**: Asynchronous task processing
- **Pandas**: Data manipulation and analysis
- **OpenPyXL**: Excel file processing

### Frontend
- **React 18.x**: UI framework
- **Ant Design**: UI component library
- **Axios**: HTTP client
- **React Router**: Client-side routing
- **PapaParse**: CSV parsing
- **SheetJS**: Excel file parsing

## Prerequisites

- Python 3.8+
- Node.js 16+
- npm or yarn

## Installation

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Run database migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

5. Create a superuser (optional):
```bash
python manage.py createsuperuser
```

6. Start the Django development server:
```bash
python manage.py runserver
```

The backend API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install Node.js dependencies:
```bash
npm install
```

3. Start the React development server:
```bash
npm start
```

The frontend will be available at `http://localhost:3000`

## API Endpoints

### File Processing
- `POST /api/v1/upload/` - Upload and process files
- `GET /api/v1/status/{id}/` - Get processing status
- `GET /api/v1/download/{id}/` - Download processed file

### History and Statistics
- `GET /api/v1/history/` - Get processing history
- `GET /api/v1/stats/` - Get system statistics
- `GET /api/v1/logs/{id}/` - Get processing logs

### System
- `GET /api/v1/health/` - Health check

## Usage

1. **Upload File**: Go to the upload page and select a CSV or Excel file
2. **Describe Processing**: Enter a natural language description of the transformation
3. **Set Replacement Value**: Specify the replacement text or pattern
4. **Select Columns**: Choose which columns to process (optional)
5. **Start Processing**: Click "Start Processing" to begin
6. **Monitor Progress**: View real-time processing status and logs
7. **Download Results**: Download the processed file when complete

## Development

### Running Tests
```bash
# Backend tests
cd backend
python manage.py test

# Frontend tests
cd frontend
npm test
```

### Code Style
```bash
# Backend (using black and flake8)
cd backend
black .
flake8 .

# Frontend (using ESLint and Prettier)
cd frontend
npm run lint
npm run format
```

## Deployment

### Backend Deployment
1. Set up a production database (PostgreSQL recommended)
2. Configure environment variables
3. Set up a web server (nginx + gunicorn)
4. Configure Celery workers for background tasks

### Frontend Deployment
1. Build the production bundle:
```bash
cd frontend
npm run build
```
2. Serve the build directory with a web server

## Environment Variables

### Backend (.env)
```
DEBUG=False
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:password@localhost/dbname
CELERY_BROKER_URL=redis://localhost:6379/0
```

### Frontend (.env)
```
REACT_APP_API_URL=http://localhost:8000/api/v1
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions, please open an issue in the GitHub repository.
