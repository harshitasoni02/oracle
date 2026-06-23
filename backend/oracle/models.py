from django.db import models


class PriceSnapshot(models.Model):
    """Current price snapshot — one row per metal, updated every 5 minutes."""
    METAL_CHOICES = [('gold', 'Gold'), ('silver', 'Silver')]

    metal = models.CharField(max_length=10, choices=METAL_CHOICES, unique=True)

    # USD prices (per troy oz)
    price_usd = models.FloatField(default=0)
    high_24h_usd = models.FloatField(null=True)
    low_24h_usd = models.FloatField(null=True)
    change_24h_usd = models.FloatField(default=0)
    change_24h_pct = models.FloatField(default=0)

    # INR conversion (international spot equivalent)
    usdinr = models.FloatField(default=86.0)
    price_inr = models.FloatField(default=0)            # per troy oz
    price_per_gram_inr = models.FloatField(default=0)
    price_per_10g_inr = models.FloatField(null=True)    # gold only
    price_per_kg_inr = models.FloatField(null=True)     # silver only

    # MCX India equivalent (spot + import duty/GST premium)
    mcx_price_per_gram = models.FloatField(null=True)
    mcx_price_10g = models.FloatField(null=True)        # gold only
    mcx_price_kg = models.FloatField(null=True)         # silver only

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['metal']

    def __str__(self):
        return f"{self.metal} @ ${self.price_usd:.2f} / ₹{self.price_per_gram_inr:.0f}/g"


class PriceBar(models.Model):
    """OHLCV candlestick data for charts."""
    METAL_CHOICES = [('gold', 'Gold'), ('silver', 'Silver')]
    TIMEFRAME_CHOICES = [
        ('1m', '1 Minute'),
        ('5m', '5 Minutes'),
        ('15m', '15 Minutes'),
        ('1h', '1 Hour'),
        ('1d', '1 Day'),
        ('1wk', '1 Week'),
    ]

    metal = models.CharField(max_length=10, choices=METAL_CHOICES, db_index=True)
    timeframe = models.CharField(max_length=5, choices=TIMEFRAME_CHOICES, db_index=True)
    timestamp = models.DateTimeField(db_index=True)

    open_usd = models.FloatField()
    high_usd = models.FloatField()
    low_usd = models.FloatField()
    close_usd = models.FloatField()
    volume = models.FloatField(default=0)
    usdinr = models.FloatField(default=86.0)
    close_inr = models.FloatField(default=0)

    class Meta:
        unique_together = ['metal', 'timeframe', 'timestamp']
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.metal} {self.timeframe} @ {self.timestamp:%Y-%m-%d %H:%M}"


class IndicatorSnapshot(models.Model):
    """Latest computed technical indicators — one row per (metal, timeframe)."""
    METAL_CHOICES = [('gold', 'Gold'), ('silver', 'Silver')]

    metal = models.CharField(max_length=10, choices=METAL_CHOICES, db_index=True)
    timeframe = models.CharField(max_length=5, db_index=True)

    current_price = models.FloatField(null=True)

    # Trend
    sma20 = models.FloatField(null=True)
    sma50 = models.FloatField(null=True)
    sma200 = models.FloatField(null=True)
    ema12 = models.FloatField(null=True)
    ema26 = models.FloatField(null=True)
    ema50 = models.FloatField(null=True)

    # Momentum
    rsi = models.FloatField(null=True)
    macd = models.FloatField(null=True)
    macd_signal_line = models.FloatField(null=True)
    macd_hist = models.FloatField(null=True)
    stoch_k = models.FloatField(null=True)
    stoch_d = models.FloatField(null=True)
    cci = models.FloatField(null=True)
    williams_r = models.FloatField(null=True)

    # Volatility
    bb_upper = models.FloatField(null=True)
    bb_middle = models.FloatField(null=True)
    bb_lower = models.FloatField(null=True)
    atr = models.FloatField(null=True)

    # Volume
    obv = models.FloatField(null=True)

    # DJI Correlation (Dow Jones — inverse signal for gold/silver)
    dji_price = models.FloatField(null=True)
    dji_change_pct = models.FloatField(null=True)
    dji_rsi = models.FloatField(null=True)
    dji_sma20 = models.FloatField(null=True)
    dji_sma50 = models.FloatField(null=True)

    # Composite signal
    signal_score = models.FloatField(default=0)     # -1.0 to +1.0
    signal_label = models.CharField(max_length=20, default='Neutral')
    individual_signals = models.JSONField(default=dict)  # per-indicator breakdown

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['metal', 'timeframe']

    def __str__(self):
        return f"{self.metal} {self.timeframe}: {self.signal_label} ({self.signal_score:+.2f})"


class NewsArticle(models.Model):
    """Scored news article from RSS feeds — one row per unique URL."""
    METAL_CHOICES = [('gold', 'Gold'), ('silver', 'Silver'), ('both', 'Both')]
    CATEGORY_CHOICES = [
        ('FED', 'Federal Reserve'),
        ('RBI', 'RBI / India Policy'),
        ('GEOPOLITICAL', 'Geopolitical'),
        ('INDIA', 'India Demand'),
        ('ETF', 'ETF Flows'),
        ('INFLATION', 'Inflation / Rates'),
        ('GENERAL', 'General'),
    ]
    LABEL_CHOICES = [('Bullish', 'Bullish'), ('Neutral', 'Neutral'), ('Bearish', 'Bearish')]

    metal = models.CharField(max_length=10, choices=METAL_CHOICES, db_index=True)
    article_hash = models.CharField(max_length=64, unique=True)  # SHA256(url) — dedup key
    title = models.TextField()
    summary = models.TextField(blank=True)
    source = models.CharField(max_length=200)
    url = models.URLField(max_length=2000)
    published_at = models.DateTimeField(db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='GENERAL')
    sentiment_score = models.FloatField(default=0.0)   # -1.0 to +1.0
    sentiment_label = models.CharField(max_length=10, choices=LABEL_CHOICES, default='Neutral')
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['metal', 'published_at']),
        ]

    def __str__(self):
        return f"[{self.metal}] {self.sentiment_label} ({self.sentiment_score:+.2f}) — {self.title[:60]}"


class SentimentSnapshot(models.Model):
    """Aggregated sentiment snapshot — one row per metal, updated each refresh."""
    METAL_CHOICES = [('gold', 'Gold'), ('silver', 'Silver')]

    metal = models.CharField(max_length=10, choices=METAL_CHOICES, unique=True)

    sentiment_24h = models.FloatField(null=True)    # simple avg of last 24h articles
    sentiment_7d = models.FloatField(null=True)     # decay-weighted, λ=0.1
    sentiment_30d = models.FloatField(null=True)    # decay-weighted, λ=0.035

    count_24h = models.IntegerField(default=0)
    count_7d = models.IntegerField(default=0)

    sentiment_momentum = models.FloatField(null=True)   # (7d − 30d) / max(|30d|, 0.01)
    signal_score = models.FloatField(default=0.0)       # -1.0 to +1.0
    signal_label = models.CharField(max_length=20, default='Neutral')

    category_breakdown = models.JSONField(default=dict)  # {FED: 0.42, RBI: -0.1, ...}
    top_articles = models.JSONField(default=list)        # list of 8 article dicts

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['metal']

    def __str__(self):
        return f"{self.metal} sentiment: {self.signal_label} ({self.signal_score:+.2f})"


class Prediction(models.Model):
    """Price prediction for a given metal + timeframe horizon."""
    METAL_CHOICES = [('gold', 'Gold'), ('silver', 'Silver')]
    TIMEFRAME_CHOICES = [
        ('1d', '1 Day'),
        ('1w', '1 Week'),
        ('2w', '2 Weeks'),
        ('1m', '1 Month'),
        ('3m', '3 Months'),
        ('6m', '6 Months'),
        ('1y', '1 Year'),
    ]
    DIRECTION_CHOICES = [
        ('up', 'Bullish'),
        ('down', 'Bearish'),
        ('sideways', 'Sideways'),
    ]

    metal = models.CharField(max_length=10, choices=METAL_CHOICES, db_index=True)
    timeframe = models.CharField(max_length=5, choices=TIMEFRAME_CHOICES)

    current_price_usd = models.FloatField(default=0)
    current_price_inr = models.FloatField(default=0)

    predicted_usd = models.FloatField(default=0)
    predicted_inr = models.FloatField(default=0)
    predicted_high_usd = models.FloatField(default=0)
    predicted_low_usd = models.FloatField(default=0)
    predicted_high_inr = models.FloatField(default=0)
    predicted_low_inr = models.FloatField(default=0)

    change_pct = models.FloatField(default=0)
    confidence = models.IntegerField(default=50)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default='sideways')
    signal_label = models.CharField(max_length=20, default='Neutral')
    rationale = models.JSONField(default=list)

    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['metal', 'timeframe']
        ordering = ['metal', 'timeframe']

    def __str__(self):
        return f"{self.metal} {self.timeframe}: {self.direction} @ ${self.predicted_usd:.2f}"
    

    # backend/oracle/models.py  (ADD these two classes to your existing models.py)
# ─────────────────────────────────────────────────────────────────────────────
# Append both classes at the bottom of your existing oracle/models.py file.
# Do NOT replace the whole file – just add what is shown here.
# ─────────────────────────────────────────────────────────────────────────────

from django.db import models


class BacktestResult(models.Model):
    """
    Stores the aggregate performance of a single backtesting run.

    One row = one (metal, timeframe, strategy, horizon) combination.
    The engine overwrites the row on every run so the table stays small.
    """

    METAL_CHOICES = [("gold", "Gold"), ("silver", "Silver")]

    TIMEFRAME_CHOICES = [
        ("1d", "1 Day"),
        ("1w", "1 Week"),
        ("1mo", "1 Month"),
    ]

    STRATEGY_CHOICES = [
        ("rsi", "RSI"),
        ("macd", "MACD"),
        ("composite", "Composite Signal"),
        ("sentiment", "Sentiment Signal"),
    ]

    HORIZON_CHOICES = [
        ("1d", "Next Day"),
        ("1w", "Next Week"),
        ("1mo", "Next Month"),
    ]

    # ── Identity ──────────────────────────────────────────────────────────────
    metal = models.CharField(max_length=10, choices=METAL_CHOICES)
    timeframe = models.CharField(max_length=5, choices=TIMEFRAME_CHOICES)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES)
    horizon = models.CharField(max_length=5, choices=HORIZON_CHOICES)

    # ── Core metrics ──────────────────────────────────────────────────────────
    accuracy = models.FloatField(
        help_text="Percentage of predictions that matched the actual direction (0–100)"
    )
    win_rate = models.FloatField(
        help_text="Percentage of trades that were profitable (0–100)"
    )
    total_trades = models.IntegerField(
        help_text="Number of trade signals evaluated"
    )

    # ── P&L metrics ───────────────────────────────────────────────────────────
    avg_gain = models.FloatField(
        help_text="Average percentage gain on winning trades"
    )
    avg_loss = models.FloatField(
        help_text="Average percentage loss on losing trades (stored as positive number)"
    )
    profit_factor = models.FloatField(
        help_text="Gross profit / Gross loss  (>1 is profitable)"
    )

    # ── Extra stats ───────────────────────────────────────────────────────────
    max_drawdown = models.FloatField(
        default=0.0,
        help_text="Maximum peak-to-trough decline as a percentage"
    )
    sharpe_ratio = models.FloatField(
        default=0.0,
        help_text="Risk-adjusted return (annualised, assuming 0 risk-free rate)"
    )
    total_return = models.FloatField(
        default=0.0,
        help_text="Total percentage return over the backtested period"
    )

    # ── Meta ──────────────────────────────────────────────────────────────────
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("metal", "timeframe", "strategy", "horizon")
        ordering = ["-created_at"]
        verbose_name = "Backtest Result"
        verbose_name_plural = "Backtest Results"

    def __str__(self):
        return (
            f"{self.metal.upper()} | {self.strategy} | "
            f"tf={self.timeframe} | horizon={self.horizon} | "
            f"acc={self.accuracy:.1f}%"
        )


class PredictionVerification(models.Model):
    """
    One row per individual prediction that has been verified against reality.

    The engine populates this after actual prices become available for a
    previously stored Prediction record.
    """

    METAL_CHOICES = [("gold", "Gold"), ("silver", "Silver")]

    TIMEFRAME_CHOICES = [
        ("1m", "1 Minute"),
        ("5m", "5 Minutes"),
        ("15m", "15 Minutes"),
        ("1h", "1 Hour"),
        ("1d", "1 Day"),
        ("1w", "1 Week"),
        ("1mo", "1 Month"),
    ]

    # ── Identity ──────────────────────────────────────────────────────────────
    metal = models.CharField(max_length=10, choices=METAL_CHOICES)
    timeframe = models.CharField(max_length=5, choices=TIMEFRAME_CHOICES)
    prediction_date = models.DateTimeField(
        help_text="When the prediction was originally made"
    )
    target_date = models.DateTimeField(
        help_text="The date/time the prediction was for"
    )

    # ── Prices ────────────────────────────────────────────────────────────────
    predicted_price = models.FloatField()
    actual_price = models.FloatField()
    predicted_direction = models.CharField(
        max_length=5,
        choices=[("up", "Up"), ("down", "Down")],
        default="up",
    )
    actual_direction = models.CharField(
        max_length=5,
        choices=[("up", "Up"), ("down", "Down")],
        default="up",
    )

    # ── Error metrics (computed on save) ──────────────────────────────────────
    absolute_error = models.FloatField(
        help_text="|predicted - actual|"
    )
    percentage_error = models.FloatField(
        help_text="|predicted - actual| / actual  * 100"
    )
    direction_correct = models.BooleanField(
        default=False,
        help_text="True when the predicted direction matched the actual direction"
    )

    # ── Meta ──────────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-prediction_date"]
        indexes = [
            models.Index(fields=["metal", "timeframe"]),
            models.Index(fields=["prediction_date"]),
        ]
        verbose_name = "Prediction Verification"
        verbose_name_plural = "Prediction Verifications"

    def save(self, *args, **kwargs):
        # Auto-compute derived fields before every save
        self.absolute_error = abs(self.predicted_price - self.actual_price)
        if self.actual_price:
            self.percentage_error = (
                self.absolute_error / abs(self.actual_price)
            ) * 100
        self.direction_correct = self.predicted_direction == self.actual_direction
        super().save(*args, **kwargs)

    def __str__(self):
        status = "✓" if self.direction_correct else "✗"
        return (
            f"{status} {self.metal.upper()} | {self.timeframe} | "
            f"{self.prediction_date:%Y-%m-%d} → {self.target_date:%Y-%m-%d} | "
            f"err={self.percentage_error:.2f}%"
        )

