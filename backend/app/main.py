from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.error_handlers import request_validation_handler
from app.api import router


app = FastAPI(
    title="Risk Metrics Calculator",
    description="API расчёта риск-метрик гипотетических сделок",
    version="0.1.0",
)

app.add_exception_handler(
    RequestValidationError,
    request_validation_handler,
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}