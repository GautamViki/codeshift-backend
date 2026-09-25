from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import url_def
from app.helpers.exception_handlers import register_exception_handlers
from app.helpers.lifespan import lifespan
from app.helpers.middleware import log_requests
from app.helpers.warnings_config import configure_warnings

configure_warnings()

app = FastAPI(
    title="Polyglot Refactor Engine",
    description="API for modernizing and transpiling Python and Go codebases.",
    lifespan=lifespan,
)

# 1. Define allowed origins (replace or expand with your frontend URLs)
origins = [
    "https://code-transpiler-ai.onrender.com",
    "http://localhost:5173",  # Default Vite port
]

# 2. Add CORS Middleware BEFORE routing and custom http middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Use ["*"] ONLY for local development
    allow_credentials=True,
    allow_methods=["*"],  # Allows OPTIONS, POST, GET, etc.
    allow_headers=["*"],  # Allows Content-Type and custom headers
)

app.include_router(url_def.router)
app.middleware("http")(log_requests)
register_exception_handlers(app)


@app.get("/")
def read_root():
    return {"status": "running", "service": "Polyglot Refactor Engine"}