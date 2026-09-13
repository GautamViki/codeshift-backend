from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.helpers.exceptions import TranspilerError
from app.helpers.exception_handlers import transpiler_exception_handler, unhandled_exception_handler
from app.helpers.middleware import log_requests
from app.helpers.warnings_config import configure_warnings
from app.helpers.lifespan import on_startup, on_shutdown
from app.routers import transpile

configure_warnings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()


app = FastAPI(
    title="Polyglot Refactor Engine",
    description="API for modernizing and transpiling Python and Go codebases.",
    lifespan=lifespan,
)

app.include_router(transpile.router)

app.middleware("http")(log_requests)

app.exception_handler(TranspilerError)(transpiler_exception_handler)
app.exception_handler(Exception)(unhandled_exception_handler)


@app.get("/")
def read_root():
    return {"status": "running", "service": "Polyglot Refactor Engine"}