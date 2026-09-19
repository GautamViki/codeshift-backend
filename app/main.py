from fastapi import FastAPI

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

app.include_router(url_def.router)
app.middleware("http")(log_requests)
register_exception_handlers(app)


@app.get("/")
def read_root():
    return {"status": "running", "service": "Polyglot Refactor Engine"}