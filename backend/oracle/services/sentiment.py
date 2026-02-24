"""
FinBERT-based sentiment scoring for gold/silver news articles.

Model: ProsusAI/finbert  (97% accuracy on financial news)
Device: CPU only
Load: once per Celery worker process (~10-30s first call, cached thereafter)
Inference: ~50ms/article after load
"""
import logging
import math
from datetime import timedelta

logger = logging.getLogger('oracle')

# ---------------------------------------------------------------------------
# FinBERT singleton — loaded lazily on first call
# ---------------------------------------------------------------------------
_pipeline = None


def _load_finbert():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    try:
        from transformers import pipeline as hf_pipeline
        logger.info("Loading ProsusAI/finbert model (first call)...")
        _pipeline = hf_pipeline(
            'text-classification',
            model='ProsusAI/finbert',
            device=-1,          # CPU
            top_k=None,         # return all 3 class probabilities
        )
        logger.info("FinBERT loaded successfully.")
    except Exception as exc:
        logger.error(f"Failed to load FinBERT: {exc}")
        _pipeline = None
    return _pipeline


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def score_text(title: str, summary: str) -> tuple:
    """
    Score a news article with FinBERT.
    Returns (score: float, label: str) where:
      score = P(positive) - P(negative)  ∈ [-1.0, +1.0]
      label = 'Bullish' | 'Neutral' | 'Bearish'
    Falls back to (0.0, 'Neutral') if model unavailable.
    """
    pipe = _load_finbert()
    if pipe is None:
        return 0.0, 'Neutral'

    text = (title + '. ' + summary[:300]).strip()
    if not text:
        return 0.0, 'Neutral'

    try:
        # Truncate to 512 tokens (rough char limit: 2000 chars)
        results = pipe(text[:2000], truncation=True, max_length=512)
        # results is a list of lists when top_k=None; flatten if needed
        if results and isinstance(results[0], list):
            results = results[0]

        probs = {r['label'].lower(): r['score'] for r in results}
        p_pos = probs.get('positive', 0.0)
        p_neg = probs.get('negative', 0.0)
        score = round(p_pos - p_neg, 4)

        if score > 0.1:
            label = 'Bullish'
        elif score < -0.1:
            label = 'Bearish'
        else:
            label = 'Neutral'

        return score, label
    except Exception as exc:
        logger.warning(f"FinBERT inference error: {exc}")
        return 0.0, 'Neutral'


# ---------------------------------------------------------------------------
# Article categorization (keyword-based, no ML)
# ---------------------------------------------------------------------------
_CATEGORY_KEYWORDS = {
    'FED':          ['federal reserve', 'fed', 'fomc', 'jerome powell', 'rate cut', 'rate hike', 'federal open'],
    'RBI':          ['rbi', 'reserve bank of india', 'monetary policy committee', 'mpc', 'shaktikanta'],
    'GEOPOLITICAL': ['geopolit', 'war', 'conflict', 'sanction', 'middle east', 'ukraine', 'russia', 'iran', 'safe haven'],
    'INDIA':        ['india', 'mcx', 'diwali', 'dhanteras', 'akshaya tritiya', 'import duty', 'gst', 'customs', 'rupee'],
    'ETF':          ['etf', 'gld', 'slv', 'ishares', 'gold fund', 'silver fund', 'inflows', 'outflows'],
    'INFLATION':    ['inflation', 'cpi', 'pce', 'consumer price', 'interest rate', 'yield', 'real rate'],
}


def categorize_article(title: str, summary: str) -> str:
    text = (title + ' ' + summary).lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return 'GENERAL'


# ---------------------------------------------------------------------------
# Decay-weighted aggregation
# ---------------------------------------------------------------------------
def compute_decay_weighted(articles: list, lambda_: float) -> float:
    """
    Exponential decay weighted average.
    weight = exp(-λ * days_old)
    articles: list of dicts with 'sentiment_score' (float) and 'published_at' (datetime)
    """
    from django.utils import timezone
    now = timezone.now()

    total_weight = 0.0
    weighted_sum = 0.0
    for art in articles:
        days_old = (now - art['published_at']).total_seconds() / 86400.0
        weight = math.exp(-lambda_ * days_old)
        weighted_sum += art['sentiment_score'] * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0
    return round(weighted_sum / total_weight, 4)


# ---------------------------------------------------------------------------
# Snapshot computation
# ---------------------------------------------------------------------------
def compute_sentiment_snapshot(metal: str) -> dict:
    """
    Read NewsArticle records from DB, compute rolling windows, build signal.
    Saves/updates SentimentSnapshot. Returns serialized dict for WS broadcast.
    """
    from django.utils import timezone
    from oracle.models import NewsArticle, SentimentSnapshot

    now = timezone.now()
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    # Query once per window
    articles_30d = list(
        NewsArticle.objects
        .filter(metal__in=[metal, 'both'], published_at__gte=cutoff_30d)
        .order_by('-published_at')
        .values('sentiment_score', 'published_at', 'category',
                'title', 'source', 'sentiment_label', 'url')
    )

    articles_7d = [a for a in articles_30d if a['published_at'] >= cutoff_7d]
    articles_24h = [a for a in articles_7d if a['published_at'] >= cutoff_24h]

    # Rolling windows
    sentiment_24h = None
    if articles_24h:
        sentiment_24h = round(
            sum(a['sentiment_score'] for a in articles_24h) / len(articles_24h), 4
        )

    sentiment_7d = compute_decay_weighted(articles_7d, lambda_=0.1) if articles_7d else None
    sentiment_30d = compute_decay_weighted(articles_30d, lambda_=0.035) if articles_30d else None

    # Momentum
    momentum = None
    if sentiment_7d is not None and sentiment_30d is not None:
        denom = max(abs(sentiment_30d), 0.01)
        momentum = round((sentiment_7d - sentiment_30d) / denom, 4)

    # Signal
    level = sentiment_7d if sentiment_7d is not None else 0.0
    mom = momentum if momentum is not None else 0.0
    signal_score, signal_label = _signal_from_level_and_momentum(level, mom)

    # Category breakdown (average score per category, from 7d articles)
    category_scores = {}
    category_counts = {}
    for art in articles_7d:
        cat = art['category']
        category_scores[cat] = category_scores.get(cat, 0.0) + art['sentiment_score']
        category_counts[cat] = category_counts.get(cat, 0) + 1
    category_breakdown = {
        cat: round(category_scores[cat] / category_counts[cat], 3)
        for cat in category_scores
    }

    # Top 8 articles (most recent 7d)
    top_articles = []
    for art in articles_7d[:8]:
        pub = art['published_at']
        top_articles.append({
            'title': art['title'],
            'source': art['source'],
            'score': art['sentiment_score'],
            'label': art['sentiment_label'],
            'category': art['category'],
            'url': art['url'],
            'published_at': pub.isoformat() if pub else None,
        })

    # Save snapshot
    snapshot_data = {
        'sentiment_24h': sentiment_24h,
        'sentiment_7d': sentiment_7d,
        'sentiment_30d': sentiment_30d,
        'count_24h': len(articles_24h),
        'count_7d': len(articles_7d),
        'sentiment_momentum': momentum,
        'signal_score': signal_score,
        'signal_label': signal_label,
        'category_breakdown': category_breakdown,
        'top_articles': top_articles,
    }
    SentimentSnapshot.objects.update_or_create(metal=metal, defaults=snapshot_data)
    logger.info(
        f"Sentiment snapshot {metal}: {signal_label} ({signal_score:+.2f}), "
        f"24h={len(articles_24h)} articles, 7d={len(articles_7d)}"
    )

    return snapshot_data


def _signal_from_level_and_momentum(level: float, momentum: float) -> tuple:
    """
    Map (level, momentum) → (signal_score, signal_label).
    level = sentiment_7d decay-weighted avg
    momentum = (7d - 30d) / max(|30d|, 0.01)
    """
    if momentum > 0.3 and level > 0.2:
        return 0.9, 'Strong Bullish'
    if momentum > 0.1 or level > 0.2:
        return 0.5, 'Bullish'
    if momentum < -0.3 and level < -0.2:
        return -0.9, 'Strong Bearish'
    if momentum < -0.1 or level < -0.2:
        return -0.5, 'Bearish'
    return 0.0, 'Neutral'
