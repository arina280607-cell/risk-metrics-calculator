export const DEMO_MODE =
  import.meta.env.DEV &&
  import.meta.env.VITE_DEMO_MODE === 'true'

const API_URL = (
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
).replace(/\/$/, '')

// Учебные ответы для проверки интерфейса.
const demoResults = new Map([
  [95000, -37.9905],
  [-95000, 37.9905],
])

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export async function requestCalculation(
  isin: string,
  positionAmount: number,
): Promise<Response> {
  if (!DEMO_MODE) {
    return fetch(`${API_URL}/api/v1/calculations/dv01`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        isin,
        position_amount: positionAmount,
      }),
      signal: AbortSignal.timeout(15000),
    })
  }

  await new Promise((resolve) => setTimeout(resolve, 900))

  if (isin === 'RU000A000016') {
    return jsonResponse(
      {
        status: 'ERROR',
        error: { code: 'MISSING_INSTRUMENT_PARAMETERS' },
      },
      422,
    )
  }

  if (isin !== 'RU000A000008') {
    return jsonResponse(
      {
        status: 'ERROR',
        error: { code: 'INSTRUMENT_NOT_FOUND' },
      },
      422,
    )
  }

  const result = demoResults.get(positionAmount)

  if (result === undefined) {
    return jsonResponse(
      {
        status: 'ERROR',
        error: { code: 'DEMO_INPUT_NOT_SUPPORTED' },
      },
      422,
    )
  }

  return jsonResponse({
    calculation_id: crypto.randomUUID(),
    status: 'SUCCESS',
    metric: 'DV01',
    isin,
    position_value: positionAmount,
    result_value: result,
    result_currency: 'RUB',
    duration_used: 4,
    convexity_used: 20,
    rate_shift_bps: 1,
    error: null,
  })
}