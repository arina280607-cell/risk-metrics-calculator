import { useState } from 'react'
import { DEMO_MODE, requestCalculation } from './api'
import './App.css'

type FieldErrors = {
  isin?: string
  amount?: string
}

type Trade = {
  id: string
  isin: string
  amount: string
  status: 'idle' | 'loading' | 'success' | 'error' | 'stale'
  result: number | null
  error: string
  fieldErrors: FieldErrors
}

type CalculationResponse = {
  status?: string
  metric?: string
  result_value?: number | string | null
  result_currency?: string
  rate_shift_bps?: number
  error?: { code?: string } | null
}

const money = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
})

const serverErrors: Record<string, string> = {
  INSTRUMENT_NOT_FOUND: 'Инструмент не найден. Проверьте ISIN.',
  PARAMETER_SNAPSHOT_NOT_FOUND:
    'По инструменту пока нет данных для расчёта.',
  MISSING_INSTRUMENT_PARAMETERS:
    'Недостаточно параметров инструмента для расчёта.',
  INVALID_INSTRUMENT_PARAMETERS:
    'Параметры инструмента требуют проверки.',
  VALIDATION_ERROR: 'Проверьте ISIN и размер позиции.',
  DEMO_INPUT_NOT_SUPPORTED:
    'В деморежиме доступны позиции 95000 и -95000 ₽.',
}

const summaryMessages = {
  empty: [
    'Пока нет сделок',
    'Добавьте сделку, чтобы начать расчёт.',
  ],
  idle: [
    'Расчёт не завершён',
    'Рассчитайте все сделки для получения общего результата.',
  ],
  loading: [
    'Выполняем расчёт',
    'Дождитесь завершения расчёта всех сделок.',
  ],
  error: [
    'Не удалось получить общий результат',
    'Проверьте сообщения в карточках и повторите расчёт.',
  ],
  stale: [
    'Результат устарел',
    'Данные изменились. Пересчитайте изменённые сделки.',
  ],
  success: [
    'Расчёт выполнен',
    'Оценка изменения общей стоимости позиций при повышении ставки на 1 б.п.',
  ],
}

function App() {
  const [trades, setTrades] = useState<Trade[]>([])

  function addTrade() {
    const newTrade: Trade = {
      id: crypto.randomUUID(),
      isin: '',
      amount: '',
      status: 'idle',
      result: null,
      error: '',
      fieldErrors: {},
    }

    setTrades((current) => [...current, newTrade])
  }

  function updateTrade(
    id: string,
    field: 'isin' | 'amount',
    value: string,
  ) {
    setTrades((current) =>
      current.map((trade): Trade => {
        if (trade.id !== id) return trade

        const fieldErrors = {
          ...trade.fieldErrors,
          [field]: undefined,
        }
        const hasErrors = Object.values(fieldErrors).some(Boolean)

        return {
          ...trade,
          [field]: field === 'isin' ? value.toUpperCase() : value,
          fieldErrors,
          status: hasErrors
            ? 'error'
            : trade.result === null
              ? 'idle'
              : 'stale',
          error: hasErrors ? 'Исправьте выделенные поля.' : '',
        }
      }),
    )
  }

  function patchTrade(id: string, changes: Partial<Trade>) {
    setTrades((current) =>
      current.map((trade) =>
        trade.id === id ? { ...trade, ...changes } : trade,
      ),
    )
  }

  async function calculateTrade(trade: Trade) {
    const isin = trade.isin.trim()
    const amountText = trade.amount
      .replace(/\s/g, '')
      .replace(/−/g, '-')
    const amount = Number(amountText.replace(',', '.'))
    const fieldErrors: FieldErrors = {}

    if (!isin) {
      fieldErrors.isin = 'Введите ISIN.'
    } else if (!/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(isin)) {
      fieldErrors.isin =
        'Нужен ISIN из 12 символов: первые две — буквы, последняя — цифра.'
    }

    if (!amountText) {
      fieldErrors.amount = 'Введите сумму позиции в рублях.'
    } else if (
      !/^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)$/.test(amountText) ||
      !Number.isFinite(amount)
    ) {
      fieldErrors.amount =
        'Введите число, например 95000 или -95000.'
    }

    if (Object.keys(fieldErrors).length > 0) {
      patchTrade(trade.id, {
        status: 'error',
        error: 'Исправьте выделенные поля.',
        fieldErrors,
      })

      const firstField = fieldErrors.isin ? 'isin' : 'amount'
      document
        .getElementById(`${firstField}-${trade.id}`)
        ?.focus()

      return
    }

    patchTrade(trade.id, {
      status: 'loading',
      error: '',
      fieldErrors: {},
    })

    try {
      const response = await requestCalculation(isin, amount)
      const data = (await response.json()) as CalculationResponse

      if (!response.ok || data.status !== 'SUCCESS') {
        throw new Error(
          serverErrors[data.error?.code ?? ''] ??
            'Не удалось выполнить расчёт. Попробуйте ещё раз.',
        )
      }

      const rawValue = data.result_value

      if (
        (typeof rawValue !== 'number' &&
          typeof rawValue !== 'string') ||
        (typeof rawValue === 'string' && rawValue.trim() === '') ||
        !Number.isFinite(Number(rawValue)) ||
        data.metric !== 'DV01' ||
        data.result_currency !== 'RUB' ||
        data.rate_shift_bps !== 1
      ) {
        throw new Error(
          'Сервер вернул неподходящий результат расчёта.',
        )
      }

      patchTrade(trade.id, {
        status: 'success',
        result: Number(rawValue),
        error: '',
      })
    } catch (error) {
      const connectionError =
        error instanceof TypeError ||
        error instanceof SyntaxError ||
        (error instanceof Error &&
          ['TimeoutError', 'AbortError'].includes(error.name))

      patchTrade(trade.id, {
        status: 'error',
        error: connectionError
          ? 'Сервис расчёта недоступен. Повторите попытку позже.'
          : error instanceof Error
            ? error.message
            : 'Не удалось выполнить расчёт.',
      })
    }
  }

  const calculatedCount = trades.filter(
    (trade) =>
      trade.status === 'success' && trade.result !== null,
  ).length

  const allCalculated =
    trades.length > 0 && calculatedCount === trades.length

  const total = allCalculated
    ? trades.reduce((sum, trade) => sum + (trade.result ?? 0), 0)
    : null

  const summaryState =
    trades.length === 0
      ? 'empty'
      : trades.some((trade) => trade.status === 'loading')
        ? 'loading'
        : trades.some((trade) => trade.status === 'error')
          ? 'error'
          : trades.some((trade) => trade.status === 'stale')
            ? 'stale'
            : allCalculated
              ? 'success'
              : 'idle'

  const [summaryTitle, summaryDescription] =
    summaryMessages[summaryState]

  return (
    <main className="calculator">
      {DEMO_MODE && (
        <div className="demo-banner" role="status">
          <strong>Демонстрационный режим.</strong>{' '}
          Учебные ответы для проверки интерфейса.
          ISIN RU000A000008: позиции 95000 и -95000 ₽.
          ISIN RU000A000016: пример нехватки данных.
        </div>
      )}

      <header className="page-header">
        <p className="team-name">Капиталисты</p>
        <h1>Расчёт риск-метрики</h1>
        <p className="page-description">
          Оцените риск предполагаемых сделок до их совершения
        </p>
      </header>

      <section aria-labelledby="trades-title">
        <div className="section-heading">
          <h2 id="trades-title">Сделки для расчёта</h2>
          <span className="trade-count">
            Всего: {trades.length}
          </span>
        </div>

        {trades.length === 0 ? (
          <div className="empty-state">
            <span className="empty-symbol" aria-hidden="true">
              ＋
            </span>
            <h3>Пока нет сделок</h3>
            <p>
              Добавьте сделку, чтобы указать ISIN и позицию в рублях
            </p>
          </div>
        ) : (
          <div className="trade-list">
            {trades.map((trade, index) => {
              const loading = trade.status === 'loading'
              const errors = trade.fieldErrors ?? {}

              return (
                <article className="trade-card" key={trade.id}>
                  <div className="trade-heading">
                    <h3>
                      <span className="trade-number">
                        {index + 1}
                      </span>
                      Сделка {index + 1}
                    </h3>

                    <button
                      type="button"
                      className="delete-button"
                      disabled={loading}
                      aria-label={`Удалить сделку ${index + 1}`}
                      onClick={() =>
                        setTrades((current) =>
                          current.filter(
                            (item) => item.id !== trade.id,
                          ),
                        )
                      }
                    >
                      <span aria-hidden="true">×</span>
                      Удалить
                    </button>
                  </div>

                  <form
                    onSubmit={(event) => {
                      event.preventDefault()
                      void calculateTrade(trade)
                    }}
                  >
                    <div className="trade-fields">
                      <label
                        className="field"
                        htmlFor={`isin-${trade.id}`}
                      >
                        ISIN
                        <input
                          id={`isin-${trade.id}`}
                          value={trade.isin}
                          onChange={(event) =>
                            updateTrade(
                              trade.id,
                              'isin',
                              event.target.value,
                            )
                          }
                          placeholder="Введите ISIN"
                          maxLength={12}
                          disabled={loading}
                          spellCheck={false}
                          autoComplete="off"
                          aria-invalid={Boolean(errors.isin)}
                          aria-describedby={
                            errors.isin
                              ? `isin-error-${trade.id}`
                              : undefined
                          }
                        />

                        {errors.isin && (
                          <span
                            className="field-error"
                            id={`isin-error-${trade.id}`}
                          >
                            {errors.isin}
                          </span>
                        )}
                      </label>

                      <label
                        className="field"
                        htmlFor={`amount-${trade.id}`}
                      >
                        Позиция, ₽
                        <input
                          id={`amount-${trade.id}`}
                          value={trade.amount}
                          onChange={(event) =>
                            updateTrade(
                              trade.id,
                              'amount',
                              event.target.value,
                            )
                          }
                          placeholder="Например, 1 000 000"
                          inputMode="text"
                          disabled={loading}
                          autoComplete="off"
                          aria-invalid={Boolean(errors.amount)}
                          aria-describedby={
                            errors.amount
                              ? `amount-error-${trade.id}`
                              : undefined
                          }
                        />

                        {errors.amount && (
                          <span
                            className="field-error"
                            id={`amount-error-${trade.id}`}
                          >
                            {errors.amount}
                          </span>
                        )}
                      </label>
                    </div>

                    <div className="trade-bottom">
                      <div
                        className={`trade-result ${trade.status}`}
                        role="status"
                      >
                        {trade.status === 'idle' &&
                          'Результат появится после расчёта'}

                        {loading &&
                          'Получаем параметры и выполняем расчёт…'}

                        {trade.status === 'success' &&
                          trade.result !== null && (
                            <>
                              DV01:{' '}
                              <strong>
                                {money.format(trade.result)}
                              </strong>
                            </>
                          )}

                        {trade.status === 'stale' && (
                          <div className="stale-notice">
                            <span>
                              Результат устарел.
                              Рассчитайте сделку заново.
                            </span>

                            {trade.result !== null && (
                              <small className="previous-result">
                                Предыдущее значение:{' '}
                                {money.format(trade.result)}
                              </small>
                            )}
                          </div>
                        )}

                        {trade.status === 'error' && trade.error}
                      </div>

                      <button
                        type="submit"
                        className="calculate-button"
                        disabled={loading}
                      >
                        {loading && (
                          <span
                            className="spinner"
                            aria-hidden="true"
                          />
                        )}

                        {loading
                          ? 'Расчёт…'
                          : trade.status === 'stale'
                            ? 'Рассчитать заново'
                            : 'Рассчитать'}
                      </button>
                    </div>
                  </form>
                </article>
              )
            })}
          </div>
        )}

        <p className="position-hint">
          <span aria-hidden="true">ⓘ</span>
          Отрицательная сумма — короткая позиция
        </p>

        <button
          type="button"
          className="add-button"
          onClick={addTrade}
        >
          <span aria-hidden="true">＋</span>
          Добавить сделку
        </button>
      </section>

      <section
        className={`summary ${summaryState}`}
        aria-labelledby="summary-title"
      >
        <div className="summary-heading">
          <h2 id="summary-title">Суммарная DV01</h2>
          <span className="summary-progress">
            Рассчитано: {calculatedCount} из {trades.length}
          </span>
        </div>

        <div
          className="summary-content"
          role="status"
          aria-atomic="true"
        >
          <h3 className="summary-status">{summaryTitle}</h3>

          <div className="summary-value">
            {total === null ? '—' : money.format(total)}
          </div>

          <p className="summary-description">
            {summaryDescription}
          </p>
        </div>
      </section>
    </main>
  )
}

export default App