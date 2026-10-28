import { useRef, useState } from 'react'
import { DEMO_MODE, errorMessage, isValidIsin, requestCalculation } from './api'
import type { TradeInput, TradeSuccess } from './api'
import './App.css'

type FieldErrors = { isin?: string; quantity?: string }

type Trade = {
  id: string
  isin: string
  quantity: string
  status: 'idle' | 'loading' | 'success' | 'error' | 'stale'
  result: TradeSuccess | null
  error: string
  fieldErrors: FieldErrors
}

type Summary = {
  state: 'idle' | 'loading' | 'success' | 'partial' | 'error' | 'stale'
  total: number | null
  message: string
}

const initialSummary: Summary = {
  state: 'idle',
  total: null,
  message: 'Добавьте сделки, укажите ISIN и количество облигаций.',
}

const money = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  minimumFractionDigits: 2,
  maximumFractionDigits: 5,
})

const icons = {
  plus: 'M12 5v14M5 12h14',
  trash: 'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7',
  document: 'M14 2H5v20h14V7l-5-5ZM14 2v6h5M8 12h8M8 16h8',
  check: 'm5 12 4 4 10-10',
  warning: 'm12 3 10 18H2L12 3ZM12 9v5M12 17v.5',
}

function Icon({ name }: { name: keyof typeof icons }) {
  return (
    <svg
      className="icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={icons[name]} />
    </svg>
  )
}

function validate(trade: Trade): {
  errors: FieldErrors
  input: TradeInput
} {
  const isin = trade.isin.trim().toUpperCase()
  const text = trade.quantity.trim().replace(/−/g, '-').replace(',', '.')
  const quantity = Number(text)
  const errors: FieldErrors = {}

  if (!isin) {
    errors.isin = 'Введите ISIN.'
  } else if (!isValidIsin(isin)) {
    errors.isin = 'Проверьте 12 символов и контрольную цифру ISIN.'
  }

  if (!text) {
    errors.quantity = 'Введите количество облигаций.'
  } else if (
    !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text) ||
    !Number.isFinite(quantity)
  ) {
    errors.quantity = 'Введите число, например 100 или -10.'
  }

  return { errors, input: { isin, quantity } }
}

function App() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [summary, setSummary] = useState<Summary>(initialSummary)
  const [busy, setBusy] = useState(false)
  const requestLock = useRef(false)

  function invalidateSummary() {
    setSummary((current) =>
      current.state === 'idle'
        ? current
        : {
            state: 'stale',
            total: null,
            message: 'Данные изменились. Выполните расчёт заново.',
          },
    )
  }

  function addTrade() {
    if (requestLock.current) return

    const trade: Trade = {
      id: crypto.randomUUID(),
      isin: '',
      quantity: '',
      status: 'idle',
      result: null,
      error: '',
      fieldErrors: {},
    }

    setTrades((current) => [...current, trade])
    invalidateSummary()
  }

  function removeTrade(id: string) {
    if (requestLock.current) return

    setTrades((current) => current.filter((trade) => trade.id !== id))

    if (trades.length === 1) setSummary(initialSummary)
    else invalidateSummary()
  }

  function updateTrade(
    id: string,
    field: 'isin' | 'quantity',
    value: string,
  ) {
    if (requestLock.current) return

    setTrades((current) =>
      current.map((trade): Trade => {
        if (trade.id !== id) return trade

        const fieldErrors = { ...trade.fieldErrors, [field]: undefined }
        const hasErrors = Object.values(fieldErrors).some(Boolean)

        return {
          ...trade,
          [field]: field === 'isin' ? value.toUpperCase() : value,
          fieldErrors,
          error: hasErrors ? 'Исправьте выделенные поля.' : '',
          status: hasErrors
            ? 'error'
            : trade.result !== null
              ? 'stale'
              : 'idle',
        }
      }),
    )

    invalidateSummary()
  }

  async function calculate() {
    if (requestLock.current || trades.length === 0) return

    const prepared = trades.map((trade) => ({
      trade,
      ...validate(trade),
    }))

    const valid = prepared.filter(
      (item) => Object.keys(item.errors).length === 0,
    )

    setTrades(
      prepared.map(({ trade, errors, input }): Trade => ({
        ...trade,
        isin: input.isin,
        result: null,
        fieldErrors: errors,
        status: Object.keys(errors).length ? 'error' : 'loading',
        error: Object.keys(errors).length
          ? 'Исправьте выделенные поля.'
          : '',
      })),
    )

    if (valid.length === 0) {
      setSummary({
        state: 'error',
        total: null,
        message: 'Нет корректных сделок. Исправьте выделенные поля.',
      })

      const first = prepared[0]
      const field = first.errors.isin ? 'isin' : 'quantity'

      document
        .getElementById(`${field}-${first.trade.id}`)
        ?.focus()

      return
    }

    requestLock.current = true
    setBusy(true)

    setSummary({
      state: 'loading',
      total: null,
      message: 'Получаем данные и рассчитываем сделки…',
    })

    try {
      const response = await requestCalculation(
        valid.map((item) => item.input),
      )

      // index в ответе относится к отправленному массиву.
      const byId = new Map(
        response.results.map((row) => [
          valid[row.index].trade.id,
          row,
        ]),
      )

      setTrades((current) =>
        current.map((trade): Trade => {
          const row = byId.get(trade.id)
          if (!row) return trade

          if (row.status === 'SUCCESS') {
            return {
              ...trade,
              status: 'success',
              result: row,
              error: '',
              fieldErrors: {},
            }
          }

          const fieldErrors: FieldErrors = {}

          for (const detail of row.error.details) {
            if (detail.field === 'isin') {
              fieldErrors.isin = detail.message
            }
            if (detail.field === 'quantity') {
              fieldErrors.quantity = detail.message
            }
          }

          return {
            ...trade,
            status: 'error',
            result: null,
            error: errorMessage(row.error),
            fieldErrors,
          }
        }),
      )

      const successful = response.results.filter(
        (row) => row.status === 'SUCCESS',
      ).length

      setSummary({
        state:
          successful === 0
            ? 'error'
            : successful === trades.length
              ? 'success'
              : 'partial',
        total: response.total_value,
        message:
          successful === 0
            ? 'Не удалось рассчитать сделки. Причины указаны в карточках.'
            : successful === trades.length
              ? 'Оценка изменения стоимости всех позиций при повышении ставки на 1 б.п.'
              : `Учтено ${successful} из ${trades.length} сделок. Сделки с ошибками в сумму не вошли.`,
      })
    } catch (error) {
      const unavailable =
        error instanceof TypeError ||
        error instanceof SyntaxError ||
        (error instanceof Error &&
          ['AbortError', 'TimeoutError'].includes(error.name))

      const message = unavailable
        ? 'Сервис расчёта недоступен. Проверьте запуск бэкенда и повторите попытку.'
        : error instanceof Error
          ? error.message
          : 'Не удалось выполнить расчёт.'

      const ids = new Set(valid.map((item) => item.trade.id))

      setTrades((current) =>
        current.map((trade): Trade =>
          ids.has(trade.id)
            ? {
                ...trade,
                status: 'error',
                result: null,
                error: message,
              }
            : trade,
        ),
      )

      setSummary({ state: 'error', total: null, message })
    } finally {
      requestLock.current = false
      setBusy(false)
    }
  }

  const successful = trades.filter(
    (trade) => trade.status === 'success',
  ).length

  const titles = {
    idle: 'Ожидаем расчёт',
    loading: 'Выполняем расчёт',
    success: 'Расчёт выполнен',
    partial: 'Частичный результат',
    error: 'Расчёт не завершён',
    stale: 'Результат устарел',
  }

  return (
    <main className="calculator">
      {DEMO_MODE && (
        <div className="demo-banner" role="status">
          <strong>Демонстрационный режим.</strong>{' '}
          Учебные ответы, без обращения к API.
          ISIN RU000A000008: количество 100, -100 или -10.
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

      <form
        onSubmit={(event) => {
          event.preventDefault()
          void calculate()
        }}
        noValidate
      >
        <section
          aria-labelledby="trades-title"
          aria-busy={busy}
        >
          <div className="section-heading">
            <h2 id="trades-title">Сделки для расчёта</h2>
            <span className="trade-count">
              Всего: {trades.length}
            </span>
          </div>

          {trades.length === 0 ? (
            <div className="empty-state">
              <span className="empty-symbol">
                <Icon name="document" />
              </span>
              <h3>Пока нет сделок</h3>
              <p>
                Добавьте сделку, чтобы указать ISIN
                и количество облигаций
              </p>
            </div>
          ) : (
            <div className="trade-list">
              {trades.map((trade, index) => (
                <article
                  className="trade-card"
                  key={trade.id}
                  aria-labelledby={`trade-title-${trade.id}`}
                >
                  <div className="trade-editor">
                    <span
                      className="trade-number"
                      aria-hidden="true"
                    >
                      {index + 1}
                    </span>

                    <div className="trade-inputs">
                      <h3 id={`trade-title-${trade.id}`}>
                        Сделка {index + 1}
                      </h3>

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
                            disabled={busy}
                            spellCheck={false}
                            autoComplete="off"
                            aria-invalid={Boolean(
                              trade.fieldErrors.isin,
                            )}
                            aria-describedby={
                              trade.fieldErrors.isin
                                ? `isin-error-${trade.id}`
                                : undefined
                            }
                          />

                          {trade.fieldErrors.isin && (
                            <span
                              className="field-error"
                              id={`isin-error-${trade.id}`}
                            >
                              {trade.fieldErrors.isin}
                            </span>
                          )}
                        </label>

                        <label
                          className="field"
                          htmlFor={`quantity-${trade.id}`}
                        >
                          Количество облигаций, шт.
                          <input
                            id={`quantity-${trade.id}`}
                            value={trade.quantity}
                            onChange={(event) =>
                              updateTrade(
                                trade.id,
                                'quantity',
                                event.target.value,
                              )
                            }
                            placeholder="Например, 100"
                            disabled={busy}
                            inputMode="text"
                            autoComplete="off"
                            aria-invalid={Boolean(
                              trade.fieldErrors.quantity,
                            )}
                            aria-describedby={
                              trade.fieldErrors.quantity
                                ? `quantity-error-${trade.id}`
                                : undefined
                            }
                          />

                          {trade.fieldErrors.quantity && (
                            <span
                              className="field-error"
                              id={`quantity-error-${trade.id}`}
                            >
                              {trade.fieldErrors.quantity}
                            </span>
                          )}
                        </label>
                      </div>
                    </div>

                    <button
                      type="button"
                      className="delete-button"
                      disabled={busy}
                      aria-label={`Удалить сделку ${index + 1}`}
                      onClick={() => removeTrade(trade.id)}
                    >
                      <Icon name="trash" />
                      Удалить
                    </button>
                  </div>

                  <div
                    className={`trade-result ${trade.status}`}
                    role="status"
                  >
                    {trade.status === 'idle' &&
                      'Параметры инструмента подтянутся автоматически'}

                    {trade.status === 'loading' && (
                      <span className="inline-status">
                        <span className="spinner" />
                        Получаем параметры и выполняем расчёт…
                      </span>
                    )}

                    {trade.status === 'error' && (
                      <span className="inline-status">
                        <Icon name="warning" />
                        {trade.error}
                      </span>
                    )}

                    {trade.status === 'stale' && (
                      <div className="stale-notice">
                        <span>
                          Данные изменились.
                          Предыдущий результат устарел.
                        </span>

                        {trade.result && (
                          <small className="previous-result">
                            Предыдущее значение DV01:{' '}
                            {money.format(
                              trade.result.result_value,
                            )}
                          </small>
                        )}
                      </div>
                    )}

                    {trade.status === 'success' &&
                      trade.result && (
                        <div className="result-details">
                          <span className="inline-status">
                            <Icon name="check" />
                            Расчёт выполнен
                          </span>

                          <span>
                            Стоимость позиции:{' '}
                            <b>
                              {money.format(
                                trade.result.position_value,
                              )}
                            </b>
                          </span>

                          <span>
                            DV01:{' '}
                            <strong>
                              {money.format(
                                trade.result.result_value,
                              )}
                            </strong>
                          </span>
                        </div>
                      )}
                  </div>
                </article>
              ))}
            </div>
          )}

          <p className="position-hint">
            ⓘ Отрицательное количество — короткая позиция.
            Стоимость позиции в рублях вычисляется автоматически.
          </p>

          <div className="action-bar">
            <button
              type="button"
              className="add-button"
              disabled={busy}
              onClick={addTrade}
            >
              <Icon name="plus" />
              Добавить сделку
            </button>

            <button
              type="submit"
              className="calculate-button"
              disabled={busy || trades.length === 0}
            >
              {busy && <span className="spinner" />}

              {busy
                ? 'Расчёт…'
                : summary.state === 'stale'
                  ? 'Рассчитать заново'
                  : 'Рассчитать'}
            </button>
          </div>
        </section>
      </form>

      <section
        className={`summary ${summary.state}`}
        aria-labelledby="summary-title"
      >
        <div className="summary-heading">
          <h2 id="summary-title">Суммарная DV01</h2>
          <span className="summary-progress">
            Успешно: {successful} из {trades.length}
          </span>
        </div>

        <div
          className="summary-content"
          role="status"
          aria-atomic="true"
        >
          <h3 className="summary-status">
            {titles[summary.state]}
          </h3>

          <div className="summary-value">
            {summary.total === null
              ? '—'
              : money.format(summary.total)}
          </div>

          {summary.state === 'partial' && (
            <p className="partial-label">
              По успешно рассчитанным сделкам
            </p>
          )}

          <p className="summary-description">
            {summary.message}
          </p>

          {summary.total !== null && (
            <p className="metric-hint">
              DV01 показывает чувствительность стоимости
              к изменению ставки, а не прибыль от сделок.
            </p>
          )}
        </div>
      </section>
    </main>
  )
}

export default App