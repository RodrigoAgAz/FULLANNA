# ANNA Project Guidelines

## About ANNA
ANNA is a healthcare chatbot for patient assistance that:
- Processes natural language input to identify user intents with regex and AI
- Provides access to medical records and FHIR healthcare data
- Handles appointment scheduling and management
- Conducts symptom analysis with severity assessment and guidance
- Retrieves and explains lab results and medications
- Supports multiple languages via translation services

## Commands
- Start server: `uvicorn anna_project.asgi:application --reload`
- Run tests: `python manage.py test`
- Run specific test: `python manage.py test test_chat_view`
- Run chatbot client: `python Django_app/chatbot/chat_client.py`
- Celery worker: `celery -A anna_project worker --loglevel=info`

## Architecture
- **Handlers**: Process messages via ChatHandler (core), SymptomGuidanceHandler, AppointmentHandler
- **Services**: Provide business logic (FHIRService, LanguageService, IntentService)
- **API Endpoints**: Django view functions in endpoints.py that handle HTTP requests
- **Session Management**: Redis-based user sessions with context tracking
- **FHIR Integration**: Healthcare data access with fhirclient library

## Code Style
- **Imports**: Standard lib → Django → Third-party → Local (with comment separators)
- **Formatting**: 4-space indentation, ~100 char line limit
- **Naming**: snake_case (files/vars), PascalCase (classes), verb_noun (functions)
- **Patterns**: Thorough error handling with try/except and logging
- **Async**: Uses Django async with Uvicorn, `sync_to_async` for synchronous code
- **Logging**: Named loggers with appropriate levels (debug/info/error)
- **Security**: Input validation, secure session handling, healthcare data sensitivity
- **Testing**: Each major component has dedicated test files