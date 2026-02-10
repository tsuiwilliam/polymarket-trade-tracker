"""
Market slug discovery for Polymarket crypto markets.
Generates event slugs for all time windows in a given day and resolves them via the Gamma API.

Slug format: {coin}-updown-{interval_suffix}-{unix_timestamp}
Example: btc-updown-15m-1770690600

Adapted from https://github.com/tsuiwilliam/polymarket-arbitrage-bot
"""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

GAMMA_API_BASE = "https://gamma-api.polymarket.com"

# Supported coins and their slug prefixes
COIN_SLUGS = {
    "BTC": "btc-updown",
    "ETH": "eth-updown",
    "SOL": "sol-updown",
    "XRP": "xrp-updown",
}

# Interval configurations
INTERVALS = {
    "1min":  {"suffix": "1m",  "seconds": 60},
    "5min":  {"suffix": "5m",  "seconds": 300},
    "15min": {"suffix": "15m", "seconds": 900},
    "30min": {"suffix": "30m", "seconds": 1800},
    "hourly": {"suffix": "1h", "seconds": 3600},
}


def generate_day_slugs(coin, interval, date_str):
    """
    Generate all event slugs for a coin + interval on a specific date.

    Args:
        coin: Coin symbol (BTC, ETH, SOL, XRP)
        interval: Interval key (1min, 5min, 15min, 30min, hourly)
        date_str: Date in YYYY-MM-DD format (UTC)

    Returns:
        List of slug strings ordered chronologically.
    """
    coin = coin.upper()
    if coin not in COIN_SLUGS:
        raise ValueError(f"Unsupported coin: {coin}. Supported: {list(COIN_SLUGS.keys())}")
    if interval not in INTERVALS:
        raise ValueError(f"Unsupported interval: {interval}. Supported: {list(INTERVALS.keys())}")

    prefix = COIN_SLUGS[coin]
    cfg = INTERVALS[interval]
    suffix = cfg["suffix"]
    step = cfg["seconds"]
    cycles = 86400 // step  # number of windows per day

    dt_obj = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start_ts = int(dt_obj.timestamp())

    return [f"{prefix}-{suffix}-{start_ts + i * step}" for i in range(cycles)]


def slug_to_time(slug):
    """Extract the UTC timestamp from a slug and return a formatted time string."""
    try:
        ts = int(slug.rsplit("-", 1)[-1])
        dt_obj = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt_obj.strftime("%H:%M")
    except (ValueError, IndexError):
        return ""


def _fetch_event(slug, session):
    """Fetch a single event by slug from the Gamma API."""
    try:
        resp = session.get(
            f"{GAMMA_API_BASE}/events",
            params={"slug": slug},
            timeout=10,
        )
        if resp.status_code == 200:
            events = resp.json()
            if events:
                return events[0]
    except Exception:
        pass
    return None


def discover_markets(coin, interval, date_str, progress_callback=None, cancel_flag=None, max_workers=15):
    """
    Discover all markets for a coin + interval on a specific date.
    Makes concurrent requests to the Gamma API to resolve slugs.

    Args:
        coin: Coin symbol (BTC, ETH, SOL, XRP)
        interval: Interval key (1min, 5min, 15min, 30min, hourly)
        date_str: Date in YYYY-MM-DD format
        progress_callback: Optional callable(completed, total) for progress updates
        cancel_flag: Optional dict with 'cancelled' key to stop early
        max_workers: Thread pool size for concurrent requests

    Returns:
        List of event dicts sorted chronologically, each containing:
        - slug, title, time_label, markets[]
    """
    slugs = generate_day_slugs(coin, interval, date_str)
    results = []
    completed = 0
    total = len(slugs)

    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_slug = {
            executor.submit(_fetch_event, slug, session): slug
            for slug in slugs
        }

        for future in as_completed(future_to_slug):
            if cancel_flag and cancel_flag.get("cancelled"):
                executor.shutdown(wait=False, cancel_futures=True)
                return results

            slug = future_to_slug[future]
            completed += 1

            if progress_callback:
                progress_callback(completed, total)

            try:
                event = future.result()
                if event:
                    event_data = {
                        "slug": slug,
                        "title": event.get("title", ""),
                        "time_label": slug_to_time(slug),
                        "end_date": event.get("endDate", ""),
                        "markets": [],
                    }
                    for m in event.get("markets", []):
                        event_data["markets"].append({
                            "condition_id": m.get("conditionId", ""),
                            "question": m.get("question", ""),
                            "slug": m.get("slug", ""),
                            "outcomes": m.get("outcomes", '["Yes", "No"]'),
                            "closed": m.get("closed", False),
                        })
                    results.append(event_data)
            except Exception:
                pass

    # Sort by slug to get chronological order
    results.sort(key=lambda x: x["slug"])
    return results
