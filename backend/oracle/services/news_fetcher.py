"""
RSS feed fetcher for gold/silver news.
Fetches articles, applies keyword filter, deduplicates by SHA256(url),
scores new articles via FinBERT, and saves to NewsArticle model.
"""
import hashlib
import logging
from datetime import timezone as dt_timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

logger = logging.getLogger('oracle')

# ---------------------------------------------------------------------------
# Feed definitions
# ---------------------------------------------------------------------------
RSS_FEEDS = [
    {
        'url': 'https://news.google.com/rss/search?q=gold+price+india&hl=en-IN&gl=IN&ceid=IN:en',
        'metal': 'gold',
        'category_hint': 'INDIA',
    },
    {
        'url': 'https://news.google.com/rss/search?q=gold+federal+reserve+inflation&hl=en-US&gl=US&ceid=US:en',
        'metal': 'gold',
        'category_hint': 'FED',
    },
    {
        'url': 'https://news.google.com/rss/search?q=silver+price+market+commodities&hl=en-US&gl=US&ceid=US:en',
        'metal': 'silver',
        'category_hint': 'GENERAL',
    },
    {
        'url': 'https://news.google.com/rss/search?q=geopolitical+gold+safe+haven&hl=en-US&gl=US&ceid=US:en',
        'metal': 'both',
        'category_hint': 'GEOPOLITICAL',
    },
    {
        'url': 'https://news.google.com/rss/search?q=inflation+interest+rate+precious+metals&hl=en-US&gl=US&ceid=US:en',
        'metal': 'both',
        'category_hint': 'INFLATION',
    },
    {
        'url': 'https://economictimes.indiatimes.com/markets/commodities/rss.cms',
        'metal': 'both',
        'category_hint': 'INDIA',
    },
]

KEYWORDS = {
    'gold', 'silver', 'bullion', 'precious metal', 'xau', 'mcx', 'comex',
    'gld', 'slv', 'federal reserve', 'rbi', 'inflation', 'interest rate',
}

FETCH_TIMEOUT = 15  # seconds per feed


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def _passes_keyword_filter(title: str, summary: str) -> bool:
    text = (title + ' ' + summary).lower()
    return any(kw in text for kw in KEYWORDS)


def _parse_published(entry) -> 'datetime':
    """Parse RSS published date → UTC-aware datetime."""
    from django.utils import timezone
    raw = getattr(entry, 'published', None) or getattr(entry, 'updated', None)
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=dt_timezone.utc)
            return dt
        except Exception:
            pass
    return timezone.now()


def fetch_rss_feed(url: str) -> list:
    """Fetch a single RSS feed URL and return list of raw article dicts."""
    try:
        # feedparser supports timeout via requests-style; use requests to fetch
        resp = requests.get(url, timeout=FETCH_TIMEOUT, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; ShizuhaPredict/1.0)'
        })
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as exc:
        logger.warning(f"RSS fetch failed for {url}: {exc}")
        return []

    articles = []
    for entry in feed.entries:
        title = getattr(entry, 'title', '') or ''
        summary = getattr(entry, 'summary', '') or ''
        url_entry = getattr(entry, 'link', '') or ''
        source = feed.feed.get('title', 'Unknown') if hasattr(feed, 'feed') else 'Unknown'

        # Truncate summary to 400 chars
        summary = summary[:400]

        articles.append({
            'title': title.strip(),
            'summary': summary.strip(),
            'url': url_entry.strip(),
            'source': source[:200],
            'published_at': _parse_published(entry),
        })

    return articles


def fetch_all_news(metal: str) -> list:
    """
    Fetch all feeds relevant to `metal` ('gold' or 'silver').
    Applies keyword filter and deduplicates within this batch by URL hash.
    Returns list of dicts with extra keys: article_hash, metal, category_hint.
    """
    seen_hashes = set()
    results = []

    relevant_feeds = [
        f for f in RSS_FEEDS
        if f['metal'] in (metal, 'both')
    ]

    for feed_def in relevant_feeds:
        raw_articles = fetch_rss_feed(feed_def['url'])
        for art in raw_articles:
            if not art['url']:
                continue
            h = _hash_url(art['url'])
            if h in seen_hashes:
                continue
            if not _passes_keyword_filter(art['title'], art['summary']):
                continue
            seen_hashes.add(h)
            art['article_hash'] = h
            art['metal'] = metal
            art['category_hint'] = feed_def['category_hint']
            results.append(art)

    logger.info(f"fetch_all_news({metal}): {len(results)} articles after filter/dedup")
    return results


def save_and_score_articles(raw_articles: list, metal: str, score_fn) -> int:
    """
    Upsert articles into NewsArticle model. Only score NEW articles (not in DB yet).
    Returns count of new articles saved.
    """
    from oracle.models import NewsArticle
    from oracle.services.sentiment import categorize_article

    new_count = 0
    for art in raw_articles:
        h = art['article_hash']
        if NewsArticle.objects.filter(article_hash=h).exists():
            continue  # already scored

        try:
            score, label = score_fn(art['title'], art['summary'])
            category = categorize_article(art['title'], art['summary'])
        except Exception as exc:
            logger.warning(f"Scoring failed for article {h[:8]}: {exc}")
            score, label, category = 0.0, 'Neutral', art.get('category_hint', 'GENERAL')

        NewsArticle.objects.create(
            metal=metal,
            article_hash=h,
            title=art['title'],
            summary=art['summary'],
            source=art['source'],
            url=art['url'],
            published_at=art['published_at'],
            category=category,
            sentiment_score=score,
            sentiment_label=label,
        )
        new_count += 1

    logger.info(f"save_and_score_articles({metal}): {new_count} new articles saved")
    return new_count
