export const DEMO_MODE =
  import.meta.env.DEV && import.meta.env.VITE_DEMO_MODE === 'true'

const API_URL = (import.meta.env.VITE_API_URL ?? '').trim().replace(/\/$/, '')

export type TradeInput = { isin: string; quantity: number }
export type FieldError = { field: string; code: string; message: string }
export type ApiError = { code: string; message: string; details: FieldError[] }

export type TradeSuccess = {
  index: number
  status: 'SUCCESS'
  isin: string
  quantity: number
  position_value: number
  result_value: number
  duration_used: number
  convexity_used: number
  rate_shift_bps: 1
}

export type TradeFailure = {
  index: number
  status: 'ERROR'
  error: ApiError
}

export type CalculationResponse = {
  calculation_id: string
  status: 'SUCCESS' | 'PARTIAL_SUCCESS' | 'ERROR'
  results: (TradeSuccess | TradeFailure)[]
  total_value: number | null
}

const errorMessages: Record<string, string> = {
  INSTRUMENT_NOT_FOUND: 'Инструмент не найден. Проверьте ISIN.',
  PARAMETER_SNAPSHOT_NOT_FOUND: 'По инструменту пока нет данных для расчёта.',
  MISSING_INSTRUMENT_PARAMETERS: 'Недостаточно параметров инструмента.',
  INVALID_INSTRUMENT_PARAMETERS: 'Параметры инструмента требуют проверки.',
  VALIDATION_ERROR: 'Проверьте данные сделки.',
  CALCULATION_NOT_READY: 'Бэкенд запущен, но расчёт ещё не подключён.',
  DEMO_INPUT_NOT_SUPPORTED: 'В деморежиме доступны количества 100, -100 и -10.',
}

export function errorMessage(error: ApiError): string {
  return Object.hasOwn(errorMessages, error.code)
    ? errorMessages[error.code]
    : error.message
}

export function isValidIsin(value: string): boolean {
  if (!/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(value)) return false

  const digits = [...value]
    .map((char) =>
      /[A-Z]/.test(char) ? String(char.charCodeAt(0) - 55) : char,
    )
    .join('')

  const sum = [...digits].reverse().reduce((total, char, index) => {
    const digit = Number(char) * (index % 2 === 1 ? 2 : 1)
    return total + Math.floor(digit / 10) + digit % 10
  }, 0)

  return sum % 10 === 0
}

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Сервер вернул неподходящий формат ответа.')
  }
  return value as Record<string, unknown>
}

function decimal(value: unknown): number {
  if (
    (typeof value !== 'number' && typeof value !== 'string') ||
    (typeof value === 'string' &&
      !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(value)) ||
    !Number.isFinite(Number(value))
  ) {
    throw new Error('Сервер вернул некорректное числовое значение.')
  }
  return Number(value)
}

function parseError(value: unknown): ApiError {
  const data = record(value)

  if (typeof data.code !== 'string' || typeof data.message !== 'string') {
    throw new Error('Сервер вернул некорректное описание ошибки.')
  }

  const details = Array.isArray(data.details)
    ? data.details.map((item) => {
        const detail = record(item)

        if (
          typeof detail.field !== 'string' ||
          typeof detail.code !== 'string' ||
          typeof detail.message !== 'string'
        ) {
          throw new Error('Сервер вернул некорректное описание поля.')
        }

        return {
          field: detail.field,
          code: detail.code,
          message: detail.message,
        }
      })
    : []

  return { code: data.code, message: data.message, details }
}

export function parseCalculation(
  value: unknown,
  inputs: TradeInput[],
): CalculationResponse {
  const data = record(value)

  if (
    data.metric !== 'DV01' ||
    data.result_currency !== 'RUB' ||
    typeof data.calculation_id !== 'string' ||
    !data.calculation_id ||
    !Array.isArray(data.results) ||
    data.results.length !== inputs.length
  ) {
    throw new Error('Ответ сервера не соответствует запросу DV01.')
  }

  const seen = new Set<number>()

  const results = data.results
    .map((item): TradeSuccess | TradeFailure => {
      const row = record(item)
      const index = row.index

      if (
        typeof index !== 'number' ||
        !Number.isInteger(index) ||
        index < 0 ||
        index >= inputs.length ||
        seen.has(index)
      ) {
        throw new Error('Сервер вернул некорректные номера сделок.')
      }

      seen.add(index)

      if (row.status === 'ERROR') {
        return { index, status: 'ERROR', error: parseError(row.error) }
      }

      if (
        row.status !== 'SUCCESS' ||
        row.isin !== inputs[index].isin ||
        decimal(row.quantity) !== inputs[index].quantity ||
        row.rate_shift_bps !== 1
      ) {
        throw new Error('Результат сервера относится к другой сделке.')
      }

      return {
        index,
        status: 'SUCCESS',
        isin: row.isin,
        quantity: decimal(row.quantity),
        position_value: decimal(row.position_value),
        result_value: decimal(row.result_value),
        duration_used: decimal(row.duration_used),
        convexity_used: decimal(row.convexity_used),
        rate_shift_bps: 1,
      }
    })
    .sort((a, b) => a.index - b.index)

  const count = results.filter((row) => row.status === 'SUCCESS').length
  const status =
    count === 0
      ? 'ERROR'
      : count === inputs.length
        ? 'SUCCESS'
        : 'PARTIAL_SUCCESS'

  if (
    data.status !== status ||
    (count === 0 ? data.total_value !== null : data.total_value === null)
  ) {
    throw new Error('Сервер вернул несогласованный итог расчёта.')
  }

  return {
    calculation_id: data.calculation_id,
    status,
    results,
    total_value: count === 0 ? null : decimal(data.total_value),
  }
}

// Только готовые учебные ответы. Формулу DV01 фронтенд не вычисляет.
function demoCalculation(inputs: TradeInput[]): unknown {
  const fixtures = new Map([
    [100, { position: '95000', result: '-37.9905' }],
    [-100, { position: '-95000', result: '37.9905' }],
    [-10, { position: '-9500', result: '3.79905' }],
  ])

  let totalUnits = 0

  const results = inputs.map((input, index) => {
    const fixture = fixtures.get(input.quantity)

    const code =
      input.isin === 'RU000A000016'
        ? 'MISSING_INSTRUMENT_PARAMETERS'
        : input.isin !== 'RU000A000008'
          ? 'INSTRUMENT_NOT_FOUND'
          : !fixture
            ? 'DEMO_INPUT_NOT_SUPPORTED'
            : null

    if (code || !fixture) {
      return {
        index,
        status: 'ERROR',
        result_value: null,
        error: {
          code: code ?? 'DEMO_INPUT_NOT_SUPPORTED',
          message: 'Учебный пример ошибки.',
          details: [],
        },
      }
    }

    // Суммирование готовых фикстур с точностью до 5 знаков.
    totalUnits += Math.round(Number(fixture.result) * 100000)

    return {
      index,
      status: 'SUCCESS',
      ...input,
      position_value: fixture.position,
      result_value: fixture.result,
      duration_used: '4',
      convexity_used: '20',
      rate_shift_bps: 1,
      cache_hit: false,
      error: null,
    }
  })

  const count = results.filter((row) => row.status === 'SUCCESS').length

  return {
    calculation_id: crypto.randomUUID(),
    metric: 'DV01',
    result_currency: 'RUB',
    status:
      count === 0
        ? 'ERROR'
        : count === inputs.length
          ? 'SUCCESS'
          : 'PARTIAL_SUCCESS',
    results,
    total_value: count === 0 ? null : String(totalUnits / 100000),
  }
}

export async function requestCalculation(
  trades: TradeInput[],
): Promise<CalculationResponse> {
  if (!trades.length) {
    throw new Error('Добавьте хотя бы одну корректную сделку.')
  }

  if (DEMO_MODE) {
    await new Promise((resolve) => setTimeout(resolve, 900))
    return parseCalculation(demoCalculation(trades), trades)
  }

  const response = await fetch(`${API_URL}/api/v1/calculations/dv01`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trades }),
    signal: AbortSignal.timeout(15000),
  })

  if (!response.ok) {
    if (response.status >= 500) {
      throw new Error('Ошибка сервиса расчёта. Повторите позже.')
    }

    const data = record(await response.json())
    throw new Error(errorMessage(parseError(data.error)))
  }

  return parseCalculation(await response.json(), trades)
}