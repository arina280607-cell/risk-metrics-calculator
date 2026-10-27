# Frontend калькулятора DV01

React + TypeScript + CSS, сборка через Vite.

## Локальный запуск

Открыть терминал в папке frontend.

1. Установить зависимости командой `npm ci`.
2. Скопировать `.env.example` в `.env.local`.
   В PowerShell: `Copy-Item .env.example .env.local`.
3. Запустить `npm run dev`.
4. Открыть адрес Local из терминала.

## Демонстрационный режим

В `.env.local` установить `VITE_DEMO_MODE=true`.

Учебные сценарии:

- RU000A000008, позиция 95000: результат -37.9905 RUB.
- RU000A000008, позиция -95000: результат 37.9905 RUB.
- RU000A000016: отсутствуют параметры инструмента.

Данные демонстрационные. В production-сборке деморежим отключён.

## Подключение backend

В `.env.local` установить `VITE_DEMO_MODE=false`.
В `VITE_API_URL` указать адрес backend и перезапустить Vite.

Frontend отправляет POST /api/v1/calculations/dv01.

Поля JSON-запроса: isin и position_amount.
position_amount — сумма в рублях, без дополнительной конвертации.

При успехе ожидаются:
status = SUCCESS, metric = DV01, result_value,
result_currency = RUB, rate_shift_bps = 1.

При ошибке ожидается error.code.

Backend должен разрешать обращения с адреса frontend
при локальной разработке, обычно http://localhost:5173.

Каждая сделка рассчитывается отдельно.
Общий итог показывается после успешного расчёта всех актуальных сделок.

## Проверки

- `npm run lint`
- `npm run build`