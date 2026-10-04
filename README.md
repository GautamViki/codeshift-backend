# CodeShift Backend

This project is a FastAPI backend for AI-assisted code transpilation. It allows authenticated users to submit source code or uploaded files, translate them into a target language with Gemini, validate the output, store results, and keep a history of past transpilation requests.

## What the project does

- Registers and authenticates users with email/password and JWT tokens
- Accepts raw code or uploaded source files
- Detects the source language from the file extension or request parameters
- Uses LangChain + Google Gemini to generate target-language code
- Cleans the LLM output and strips markdown fences or surrounding text
- Validates generated code using language-specific validators
- Retries a small repair loop when validation fails
- Saves generated code to disk and stores metadata in PostgreSQL/SQLAlchemy models
- Reuses cached transpilation results for repeated inputs

## Current architecture

### App entry points

- [app/main.py](app/main.py): creates the FastAPI app, CORS config, exception handlers, and includes the API router
- [app/api/url_def.py](app/api/url_def.py): declares all routes

### Core layers

- [app/handlers](app/handlers): handles HTTP requests for auth, transpilation, and history
- [app/services](app/services): contains the business logic for auth, transpilation, and history
- [app/models](app/models): ORM models for users and transpilation records
- [app/validators](app/validators): validation rules for generated code
- [app/helpers](app/helpers): constants, logging, cache, exceptions, utilities
- [app/database.py](app/database.py): SQLAlchemy async database setup
- [app/dependencies.py](app/dependencies.py): auth dependency for protected routes

## Supported languages

The code currently defines these languages in [app/helpers/constants.py](app/helpers/constants.py):

- Python
- Go
- JavaScript
- TypeScript
- Java
- Rust

Validation is currently implemented for:

- Python
- Go

## Security and data flow

The app uses:

- JWT-based authentication via `OAuth2PasswordBearer`
- bcrypt password hashing in [app/services/auth.py](app/services/auth.py)
- Async SQLAlchemy sessions for the database layer
- a hash-based cache key for repeated transpilation requests

## Prerequisites

Before running the backend, you need:

- Python 3.14+ (from [pyproject.toml](pyproject.toml))
- PostgreSQL running and available via `DB_URL`
- Go installed and available in `PATH` for Go validation checks
- A Google Gemini API key

## Environment variables

Create a `.env` or `.env.development` file with values like:

```env
ENVIRONMENT=development
DB_URL=postgresql+asyncpg://user:password@localhost:5432/codeshift
GOOGLE_API_KEY=your_gemini_api_key
JWT_SECRET_KEY=change_this_in_production
```

The app loads environment files automatically from [app/config.py](app/config.py). If `ENVIRONMENT=development`, it tries to load `.env.development` first, then falls back to `.env`.

## Local setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the app

```bash
ENVIRONMENT=development uv run uvicorn app.main:app --reload --reload-exclude 'app/generated_code/**' --host 0.0.0.0 --port 8080
```

### 3. Open API docs

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API endpoints

### Health check

```bash
curl http://localhost:8000/
```

Response:

```json
{
  "status": "running",
  "service": "Polyglot Refactor Engine"
}
```

### Register a user

`POST /api/v1/auth/register`

Uses form data:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -F "email=user@example.com" \
  -F "password=secret123"
```

Example response:

```json
{
  "id": 1,
  "email": "user@example.com"
}
```

### Login

`POST /api/v1/auth/login`

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -F "email=user@example.com" \
  -F "password=secret123"
```

Example response:

```json
{
  "access_token": "<jwt-token>",
  "token_type": "bearer"
}
```

### Transpile a file

`POST /api/v1/transpile-file`

Requires Bearer token auth. Upload a file and pass the target language.

```bash
curl -X POST http://localhost:8000/api/v1/transpile-file \
  -H "Authorization: Bearer <token>" \
  -F "file=@example.py" \
  -F "target_language=go" \
  -F "validate_syntax=true" \
  -F "use_cache=true"
```

Example response:

```json
{
  "success": true,
  "transpilation_id": 12,
  "filename": "example.go",
  "saved_path": "generated_code/example.go",
  "validation_message": "Code passed Go compiler syntax checks.",
  "cached": false
}
```

### Transpile raw source text

`POST /api/v1/transpile-raw`

Requires Bearer token auth. The request body is plain text, and language parameters are passed as query params.

```bash
curl -X POST "http://localhost:8000/api/v1/transpile-raw?source_language=python&target_language=go&validate_syntax=true&use_cache=true" \
  -H "Authorization: Bearer <token>" \
  --data-binary $'def add(a, b):\n    return a + b\n'
```

Response is plain text containing the transpiled output.

### Fetch transpilation history

`GET /api/v1/history`

```bash
curl "http://localhost:8000/api/v1/history?limit=20&offset=0" \
  -H "Authorization: Bearer <token>"
```

Example response:

```json
[
  {
    "id": 12,
    "source_language": "python",
    "target_language": "go",
    "created_at": "2026-10-04T10:20:00Z"
  }
]
```

## Transpilation flow

A single transpile request follows this flow:

1. The client sends source code or an uploaded file
2. The request handler validates language support and file encoding
3. The transpiler builds a prompt for Gemini
4. The LLM generates target-language code
5. The result is cleaned from markdown/extra text
6. A validator checks the generated code
7. If validation fails, the app asks the model to repair the output and retries
8. The final code is saved to disk and recorded in the database
9. The API returns the result and validation status

## Cache and repair behavior

The app includes:

- in-memory transpile cache using a hash of source+language pair
- database-backed transpilation history per user
- a bounded repair loop in [app/services/transpiler.py](app/services/transpiler.py)

This makes repeated conversions faster and gives the LLM a small feedback loop when compiler validation fails.

## Notes

- The project is currently a backend-only service. It does not include a frontend.
- The system is designed around authenticated use, not anonymous public translation.
- The current validation logic is strongest for Python and Go, while other languages are supported as generation targets but may not have equally rich validation coverage.

## Repository structure

```text
codeshift-backend/
├── app/
│   ├── api/
│   ├── aws_configs/
│   ├── generated_code/
│   ├── handlers/
│   ├── helpers/
│   ├── models/
│   ├── services/
│   ├── validators/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   └── main.py
├── alembic/
├── logs/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── README.md
└── .env.example (if present in your environment)
```
