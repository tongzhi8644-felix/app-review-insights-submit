"""
Deterministic review cleaning: normalize fields, detect language heuristically,
deduplicate by content hash, drop empty bodies.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any


WHITESPACE_RE = re.compile(r"\s+")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def clean_reviews(raw_reviews: list[dict[str, Any]]) -> dict[str, Any]:
    cleaned: list[dict[str, Any]] = []
    duplicates: list[str] = []
    seen_hashes: set[str] = set()
    empty_dropped = 0

    for rev in raw_reviews:
        title = _normalize_text(rev.get("title") or "")
        content = _normalize_text(rev.get("content") or "")
        if not content and not title:
            empty_dropped += 1
            continue

        body_for_hash = f"{title}\n{content}".lower()
        content_hash = hashlib.sha256(body_for_hash.encode("utf-8")).hexdigest()
        is_dup = content_hash in seen_hashes
        if is_dup:
            duplicates.append(rev.get("review_id", ""))
        else:
            seen_hashes.add(content_hash)

        cleaned.append(
            {
                "review_id": str(rev.get("review_id")),
                "author": (rev.get("author") or "").strip()[:255],
                "rating": _clamp_rating(rev.get("rating")),
                "title": title,
                "content": content,
                "version": str(rev.get("version") or "")[:64],
                "updated_at": str(rev.get("updated_at") or "")[:64],
                "language": _guess_language(f"{title} {content}"),
                "is_duplicate": is_dup,
                "content_hash": content_hash,
            }
        )

    unique = [c for c in cleaned if not c["is_duplicate"]]
    return {
        "cleaned": cleaned,
        "unique": unique,
        "stats": {
            "input_count": len(raw_reviews),
            "cleaned_count": len(cleaned),
            "unique_count": len(unique),
            "duplicate_count": len(duplicates),
            "empty_dropped": empty_dropped,
            "duplicate_ids": duplicates[:50],
        },
        "method": "deterministic_rules",
        "rationale": (
            "Field normalization, empty-body drop, and SHA-256 content-hash "
            "dedup are rule-based because they are exact and reproducible."
        ),
    }


def filter_by_goal(
    unique_reviews: list[dict[str, Any]], goal: str | None
) -> dict[str, Any]:
    """
    Soft scope filter based on user goal.
    Uses lightweight rules only to narrow candidates; semantic work stays in LLM.
    """
    goal_l = (goal or "").lower().strip()
    if not goal_l:
        return {
            "scoped": unique_reviews,
            "scope_note": "No goal provided; using all unique reviews.",
            "method": "deterministic_rules",
        }

    scoped = unique_reviews
    notes = []

    if any(k in goal_l for k in ("low", "1-star", "1 star", "差评", "低分")):
        scoped = [r for r in unique_reviews if (r.get("rating") or 0) <= 2]
        notes.append("Filtered to rating <= 2 for low-rating focus.")
    elif any(k in goal_l for k in ("high", "5-star", "好评")):
        scoped = [r for r in unique_reviews if (r.get("rating") or 0) >= 4]
        notes.append("Filtered to rating >= 4 for high-rating focus.")

    version_match = re.search(r"version\s*([0-9]+(?:\.[0-9]+)*)", goal_l)
    if not version_match:
        version_match = re.search(r"版本\s*([0-9]+(?:\.[0-9]+)*)", goal or "")
    if version_match:
        ver = version_match.group(1)
        version_scoped = [
            r for r in scoped if ver in str(r.get("version") or "")
        ]
        if version_scoped:
            scoped = version_scoped
            notes.append(f"Filtered to version containing '{ver}'.")
        else:
            notes.append(
                f"Goal mentioned version '{ver}' but no matching reviews; "
                "kept prior scope."
            )

    if not scoped:
        return {
            "scoped": unique_reviews,
            "scope_note": (
                "Goal filters removed all reviews; reverted to full unique set. "
                + " ".join(notes)
            ),
            "method": "deterministic_rules",
        }

    return {
        "scoped": scoped,
        "scope_note": " ".join(notes) or "Goal recorded; no hard filter applied.",
        "method": "deterministic_rules",
    }


def _normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ").strip()
    return WHITESPACE_RE.sub(" ", text)


def _clamp_rating(value: Any) -> int:
    try:
        rating = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(5, rating))


def _guess_language(text: str) -> str:
    if CJK_RE.search(text):
        return "zh"
    # very rough latin default
    return "en"
