from fastapi import APIRouter

from app.schemas import (
    CalculationRequest,
    CalculationResponse,
    ErrorResponse,
)
from app.services import process_calculation


router = APIRouter(
    prefix="/api/v1/calculations",
    tags=["Расчёты"],
)


@router.post(
    "/dv01",
    response_model=CalculationResponse,
    summary="Рассчитать DV01 для набора сделок",
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Отсутствует тело запроса или некорректный JSON",
        },
        422: {
            "model": ErrorResponse,
            "description": "Некорректная структура запроса",
        },
    },
)

def calculate_dv01(
    request: CalculationRequest,
) -> CalculationResponse:
    return process_calculation(request)
