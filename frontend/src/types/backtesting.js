// frontend/src/types/backtesting.js
// All TypeScript interfaces removed — replaced with JSDoc comments for IDE hints.
// ─────────────────────────────────────────────────────────────────────────────

// ── Display helpers ───────────────────────────────────────────────────────────

export const STRATEGY_LABELS = {
  rsi: "RSI",
  macd: "MACD",
  composite: "Composite",
};

export const TIMEFRAME_LABELS = {
  "1d": "Daily",
  "1w": "Weekly",
  "1mo": "Monthly",
};

export const HORIZON_LABELS = {
  "1d": "Next Day",
  "1w": "Next Week",
  "1mo": "Next Month",
};

// ── JSDoc shapes (no runtime cost — purely for editor autocompletion) ─────────

/**
 * @typedef {"gold"|"silver"} Metal
 * @typedef {"1d"|"1w"} Timeframe
 * @typedef {"1d"|"1w"} Horizon
 * @typedef {"rsi"|"macd"|"composite"} Strategy
 * @typedef {"up"|"down"} Direction
 */

/**
 * @typedef {Object} BacktestResult
 * @property {number}   id
 * @property {Metal}    metal
 * @property {Timeframe} timeframe
 * @property {Strategy} strategy
 * @property {Horizon}  horizon
 * @property {number}   accuracy
 * @property {number}   win_rate
 * @property {number}   total_trades
 * @property {number}   avg_gain
 * @property {number}   avg_loss
 * @property {number}   profit_factor
 * @property {number}   max_drawdown
 * @property {number}   sharpe_ratio
 * @property {number}   total_return
 * @property {string|null} start_date
 * @property {string|null} end_date
 * @property {string}   created_at
 */

/**
 * @typedef {Object} BacktestSummary
 * @property {Metal}    metal
 * @property {Timeframe} timeframe
 * @property {Strategy} best_strategy
 * @property {number}   best_accuracy
 * @property {number}   best_profit_factor
 * @property {number}   total_runs
 * @property {BacktestResult[]} strategies
 */

/**
 * @typedef {Object} PredictionVerification
 * @property {number}    id
 * @property {Metal}     metal
 * @property {Timeframe} timeframe
 * @property {string}    prediction_date
 * @property {string}    target_date
 * @property {number}    previous_price
 * @property {number}    predicted_price
 * @property {number}    actual_price
 * @property {Direction} predicted_direction
 * @property {Direction} actual_direction
 * @property {number}    absolute_error
 * @property {number}    percentage_error
 * @property {boolean}   direction_correct
 * @property {string}    created_at
 */

/**
 * @typedef {Object} PaginatedVerifications
 * @property {number} count
 * @property {number} page
 * @property {number} page_size
 * @property {PredictionVerification[]} results
 */

/**
 * @typedef {Object} VerificationStats
 * @property {Metal}     metal
 * @property {Timeframe} timeframe
 * @property {number}    total_verified
 * @property {number}    mae
 * @property {number}    rmse
 * @property {number}    mape
 * @property {number}    directional_accuracy
 * @property {number}    avg_overestimate
 * @property {number}    recent_mae
 */
