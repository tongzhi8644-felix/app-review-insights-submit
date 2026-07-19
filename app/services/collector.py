"""
App Store review collection.

Primary source: Apple public iTunes Customer Reviews RSS JSON feed
(US storefront), NOT HTML page scraping.

Endpoint pattern:
  https://itunes.apple.com/{country}/rss/customerreviews/page={n}/id={app_id}/sortby=mostrecent/json

Limitations:
  - Typically up to ~500 recent reviews (10 pages × ~50)
  - Only public feed fields; no private developer reply metadata beyond feed
  - Rate limits: keep pages modest and reuse cache when appropriate
"""
from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urlparse

import requests

APP_ID_RE = re.compile(r"/id(\d+)", re.IGNORECASE)
USER_AGENT = (
    "AppReviewInsights/1.0 (+local assessment; respectful rate-limited client)"
)


def parse_app_id(app_url: str) -> str:
    match = APP_ID_RE.search(app_url or "")
    if not match:
        raise ValueError(
            "Invalid App Store URL: expected pattern .../id{numericId}"
        )
    return match.group(1)


def normalize_storefront(app_url: str) -> str:
    """Force US storefront for data collection as required by the brief."""
    parsed = urlparse(app_url)
    # keep path/query but force /us/ for RSS country
    return "us"


def fetch_reviews_rss(
    app_id: str,
    country: str = "us",
    max_pages: int = 10,
    sleep_seconds: float = 0.35,
) -> list[dict[str, Any]]:
    """Fetch reviews from Apple RSS JSON. Deterministic HTTP collection."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})

    reviews: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for page in range(1, max_pages + 1):
        url = (
            f"https://itunes.apple.com/{country}/rss/customerreviews/"
            f"page={page}/id={app_id}/sortby=mostrecent/json"
        )
        resp = session.get(url, timeout=30)
        if resp.status_code == 400:
            # Apple often returns 400 when page exceeds available data
            break
        resp.raise_for_status()
        payload = resp.json()
        entries = payload.get("feed", {}).get("entry", [])
        if not entries:
            break

        # First entry on page 1 is often the app metadata, not a review
        for entry in entries:
            if "im:rating" not in entry:
                continue
            review = _normalize_rss_entry(entry)
            if review["review_id"] in seen_ids:
                continue
            seen_ids.add(review["review_id"])
            reviews.append(review)

        time.sleep(sleep_seconds)

    return reviews


def _normalize_rss_entry(entry: dict[str, Any]) -> dict[str, Any]:
    def _label(obj, default=""):
        if isinstance(obj, dict):
            return obj.get("label", default)
        return default

    review_id = _label(entry.get("id")) or str(entry.get("id", {}).get("label", ""))
    author = ""
    author_obj = entry.get("author") or {}
    if isinstance(author_obj, dict):
        author = _label(author_obj.get("name"))

    return {
        "review_id": str(review_id),
        "author": author,
        "rating": int(_label(entry.get("im:rating"), "0") or 0),
        "title": _label(entry.get("title")),
        "content": _label(entry.get("content")),
        "version": _label(entry.get("im:version")),
        "updated_at": _label(entry.get("updated")),
        "vote_sum": int(_label(entry.get("im:voteSum"), "0") or 0),
        "vote_count": int(_label(entry.get("im:voteCount"), "0") or 0),
        "raw_json": entry,
    }


def load_reviews_from_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize imported JSON/CSV row dicts into internal review shape."""
    out = []
    for i, row in enumerate(records):
        rid = str(
            row.get("review_id")
            or row.get("id")
            or row.get("ReviewId")
            or f"import-{i+1}"
        )
        out.append(
            {
                "review_id": rid,
                "author": row.get("author") or row.get("Author") or "",
                "rating": int(row.get("rating") or row.get("Rating") or 0),
                "title": row.get("title") or row.get("Title") or "",
                "content": row.get("content")
                or row.get("Content")
                or row.get("body")
                or "",
                "version": str(row.get("version") or row.get("Version") or ""),
                "updated_at": str(row.get("updated_at") or row.get("date") or ""),
                "vote_sum": int(row.get("vote_sum") or 0),
                "vote_count": int(row.get("vote_count") or 0),
                "raw_json": row,
            }
        )
    return out
