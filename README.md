# CodeShift Backend

CodeShift Backend is a FastAPI service for AI-assisted code transpilation. Authenticated users can submit source code or upload a source file, choose a target language, and receive generated code. The service uses Google Gemini through LangChain, can validate generated Python and Go code, stores user and transpilation history in PostgreSQL, and caches repeated conversions.

The web client is maintained separately in the `codeshift-web` project.

## Features

- Email/password registration and login with bearer JWT authentication.
- Raw text and file-upload transpilation endpoints.
- Source-language detection for uploaded files and explicit language selection for raw code.
- Gemini-backed code generation with output cleanup.
- Optional syntax validation, including a bounded repair loop when validation fails.
- PostgreSQL persistence for users and per-user transpilation history.
- In-memory caching for repeated source/language combinations.
- An authenticated evaluation endpoint for the prompt benchmark suite.

## Architecture

| Path | Responsibility |
| --- | --- |
| `app/main.py` | FastAPI app, CORS, middleware, exception handling, and router setup |
| `app/api/url_def.py` | API route declarations |
| `app/handlers/` | HTTP request handling for auth, transpilation, history, and evaluation |
| `app/services/` | Authentication, transpilation, history, and output-file services |
| `app/models/` | SQLAlchemy models |
| `app/validators/` | Generated-code validators |
| `app/helpers/` | Configuration helpers, logging, cache, exceptions, and utilities |
| `app/alembic/` | Database migration configuration and revisions |

## Supported languages

The backend accepts Python, Go, JavaScript, TypeScript, Java, and Rust as source or target languages. Syntax validation is currently implemented for Python and Go; other languages may be generated without equivalent validator coverage.

## Requirements

- Python 3.14 or newer.
- PostgreSQL 16 (or a compatible PostgreSQL version).
- A Google Gemini API key. If `GOOGLE_API_KEY` is not set, the app attempts to read the `transpiler_ai_key` parameter from AWS Systems Manager Parameter Store in `us-east-1`.
- Go installed and on `PATH` if you want to run Go validation locally. The Docker image installs Go.

## Configuration

Create `.env.development` in the backend project directory. For a PostgreSQL server reachable at `your-postgres.example.com` on port 5432:

```env
ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://<user>:<password>@your-postgres.example.com:5432/<database>
GOOGLE_API_KEY=your_gemini_api_key
JWT_SECRET_KEY=replace-with-a-long-random-secret
```

`DATABASE_URL` is required. `GOOGLE_API_KEY` can be omitted when AWS credentials are configured to read the SSM parameter described above. Set a strong, private `JWT_SECRET_KEY` outside local development; the built-in development fallback must not be used in production.

The app loads `.env.<ENVIRONMENT>` (for example, `.env.development`) and falls back to `.env` if that file does not exist. The JWT secret is read from the process environment. Do not commit environment files or secrets.

## Run locally

From the backend project directory:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start PostgreSQL and ensure the database named in `DATABASE_URL` exists. Apply the database migrations:

```bash
alembic -c app/alembic.ini upgrade head
```

Start the API on port 8080 (the default API port configured in the web frontend):

```bash
ENVIRONMENT=development uvicorn app.main:app --reload --reload-exclude 'app/generated_code/**' --host 0.0.0.0 --port 8080
```

Replace `your-backend.example.com` with the hostname where the API is reachable. The API root is `http://your-backend.example.com:8080/`. Interactive API documentation is available at:

- Swagger UI: `http://your-backend.example.com:8080/docs`
- ReDoc: `http://your-backend.example.com:8080/redoc`

## Run with Docker Compose

The Compose setup runs the API on host port 8000 and PostgreSQL on host port 5432. It expects a `.env.development` file because that file is passed to the API container. For database connections from the API container, use the Compose service hostname `postgres-db`:

```env
ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://codeshift:localdevpassword@postgres-db:5432/codeshift
GOOGLE_API_KEY=your_gemini_api_key
JWT_SECRET_KEY=replace-with-a-long-random-secret
```

The Compose file uses `localdevpassword` as its local PostgreSQL password; use matching credentials in `DATABASE_URL`. Do not reuse this local configuration in production.

Start the database and apply migrations from the API image:

```bash
docker compose up -d postgres-db
docker compose run --rm transpiler-api alembic -c app/alembic.ini upgrade head
docker compose up --build
```

With Compose, replace `your-backend.example.com` with the hostname where the Docker host is reachable. The API is available at `http://your-backend.example.com:8000/`, with docs at `http://your-backend.example.com:8000/docs` and `http://your-backend.example.com:8000/redoc`.

## API endpoints

All application routes use the `/api/v1` prefix, except for the health endpoint at `/`.
The examples below use `https://your-backend.example.com` as a placeholder base URL; replace it with your deployed API URL.

| Method and path | Authentication | Description |
| --- | --- | --- |
| `GET /` | No | Health check |
| `POST /api/v1/auth/register` | No | Register with email and password form fields |
| `POST /api/v1/auth/login` | No | Log in with email and password form fields; returns a bearer token |
| `POST /api/v1/transpile-raw` | Bearer token | Transpile a plain-text request body |
| `POST /api/v1/transpile-file` | Bearer token | Transpile an uploaded source file |
| `GET /api/v1/history` | Bearer token | List the authenticated user's recent transpilation history |
| `POST /api/v1/eval` | Bearer token | Run the prompt evaluation suite; accepts optional `prompt_version` (default `v1`) |

### Register

```bash
curl -X POST https://your-backend.example.com/api/v1/auth/register \
  -F 'email=user@example.com' \
  -F 'password=choose-a-password'
```

Registration requires a valid email and a password of at least 6 characters (maximum 72 UTF-8 bytes).

### Login

```bash
curl -X POST https://your-backend.example.com/api/v1/auth/login \
  -F 'email=user@example.com' \
  -F 'password=choose-a-password'
```

The response includes an `access_token` and `token_type: "bearer"`. Access tokens expire after 30 minutes.

### Transpile raw code

Provide the source code as a plain-text body. Language and behavior options are query parameters:

```bash
curl -X POST \
  'https://your-backend.example.com/api/v1/transpile-raw?source_language=python&target_language=go&validate_syntax=true&use_cache=true' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'Content-Type: text/plain' \
  --data-binary $'def add(a, b):\n    return a + b\n'
```

The response body is plain text containing the generated code. The request body must be valid UTF-8 and no larger than 1 MB.

### Transpile a file

The source language is detected from the uploaded file extension:

```bash
curl -X POST https://your-backend.example.com/api/v1/transpile-file \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -F 'file=@example.py' \
  -F 'target_language=go' \
  -F 'validate_syntax=true' \
  -F 'use_cache=true'
```

The endpoint returns JSON with the success status, transpilation ID, generated filename and path, validation message, and cache status. Uploaded files must be UTF-8 text and use a supported language extension.

### Fetch history

History is scoped to the authenticated user. `limit` defaults to 20 (maximum 100) and `offset` defaults to 0:

```bash
curl 'https://your-backend.example.com/api/v1/history?limit=20&offset=0' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

### Run evaluation

```bash
curl -X POST 'https://your-backend.example.com/api/v1/eval?prompt_version=v1' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

The response summarizes benchmark totals, pass rate, and failures.

## Transpilation flow

1. An authenticated request supplies raw code or a source file.
2. The handler validates the language, encoding, and request size where applicable.
3. The transpilation service sends a language-specific prompt to Gemini.
4. The generated response is cleaned to extract code.
5. If validation is enabled and a validator exists, the output is checked and may be repaired with a bounded retry loop.
6. Generated code is saved under `app/generated_code/`, and request metadata is recorded in PostgreSQL history.
7. The API returns the result.

## Database migrations

Database schema changes are managed with Alembic. The migration environment reads `DATABASE_URL` and converts the async PostgreSQL URL to a synchronous driver URL for migration execution. Run migrations after creating the database and before using database-backed endpoints:

```bash
alembic -c app/alembic.ini upgrade head
```

## Tests and linting

The test and lint commands require `pytest` and `ruff` to be installed; they are development tools and are not included in `requirements.txt`. Install them in the active environment if needed:

```bash
pip install pytest ruff
```

Run the backend tests from the project root:

```bash
pytest app/tests
```

Run Ruff:

```bash
ruff check app
```

## Repository structure

```text
codeshift-backend/
├── app/
│   ├── alembic/       # Alembic configuration and migration revisions
│   ├── api/           # Route declarations
│   ├── aws_configs/   # AWS Systems Manager secret lookup
│   ├── eval/          # Prompt evaluation cases, metrics, and runner
│   ├── generated_code/# Generated transpilation output
│   ├── handlers/      # HTTP handlers
│   ├── helpers/       # Constants, cache, exceptions, logging, utilities
│   ├── models/        # SQLAlchemy models
│   ├── services/      # Business logic
│   ├── tests/         # Backend tests
│   └── validators/    # Generated-code validators
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── README.md
```
