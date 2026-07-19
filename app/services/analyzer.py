"""
Model-driven dynamic topic discovery, classification, and findings.
"""
from __future__ import annotations

import json
from typing import Any

from app.services.llm import chat_json, llm_configured, model_meta


SYSTEM = """You are a product analyst. Analyze App Store reviews for ANY app.
Do NOT use a fixed/predefined issue taxonomy. Discover topics dynamically from the reviews.
Every finding MUST cite real review_id values from the provided input only.
Never invent review IDs, quotes, ratings, or versions.
Always produce non-empty findings when reviews contain complaints or requests.
Return a single JSON object only. No markdown."""


def analyze_reviews(
    reviews: list[dict[str, Any]],
    analysis_goal: str,
    app_id: str,
) -> dict[str, Any]:
    if not reviews:
        return {
            "classifications": [],
            "findings": [],
            "evidence_sufficient": False,
            "data_limitations": ["No reviews available after cleaning/scope."],
            "method": "model_driven",
            "model_meta": model_meta() if llm_configured() else {},
            "used_fallback": False,
        }

    sample = _select_review_sample(reviews, limit=40)
    compact = [
        {
            "review_id": r["review_id"],
            "rating": r.get("rating"),
            "title": (r.get("title") or "")[:80],
            "content": (r.get("content") or "")[:220],
            "version": r.get("version"),
        }
        for r in sample
    ]

    user_prompt = f"""App ID: {app_id}
Analysis goal / constraint: {analysis_goal or "(none — general product issues)"}
Total reviews available: {len(reviews)}; analyzing a stratified sample of {len(compact)}.

Reviews JSON:
{json.dumps(compact, ensure_ascii=False)}

Return JSON with EXACTLY these keys:
{{
  "classifications": [
    {{"review_id":"...", "topics":["..."], "sentiment":"negative|neutral|positive|mixed", "priority_hint":"p0|p1|p2|none", "note":"..."}}
  ],
  "findings": [
    {{
      "finding_key":"F1",
      "title":"...",
      "summary":"...",
      "source_review_ids":["..."],
      "sample_count":2,
      "confidence":0.7,
      "uncertainty":"...",
      "conflicting_evidence":"",
      "evidence_excerpts":[{{"review_id":"...","excerpt":"..."}}],
      "is_assumption":false
    }}
  ],
  "evidence_sufficient": true,
  "data_limitations": ["..."],
  "conflicting_themes": ["..."]
}}

Hard requirements:
- findings MUST contain 3 to 8 items (never empty if any negative/mixed review exists).
- classifications: cover ALL sampled review_ids (one row each).
- Prefer findings aligned with the analysis goal when provided.
- source_review_ids must come from the Reviews JSON above.
- sample_count must equal len(source_review_ids).
"""

    result = chat_json(SYSTEM, user_prompt)
    result = _normalize_analysis_payload(result)

    # Retry once with a tighter prompt if the model returned empty findings
    if not result.get("findings"):
        retry_prompt = f"""The previous answer had empty findings. Try again.
App ID: {app_id}
Goal: {analysis_goal or "general product issues"}
Sample reviews ({len(compact)}):
{json.dumps(compact, ensure_ascii=False)}

Return JSON with non-empty "findings" (3-6) and "classifications" for each review_id.
Cite only review_ids from the sample. JSON only."""
        result = _normalize_analysis_payload(chat_json(SYSTEM, retry_prompt))

    result["method"] = "model_driven"
    result["model_meta"] = model_meta()
    result["used_fallback"] = False
    result["sample_size"] = len(compact)
    result["total_reviews"] = len(reviews)
    if "evidence_sufficient" not in result:
        result["evidence_sufficient"] = len(reviews) >= 15
    if not result.get("findings"):
        result["data_limitations"] = list(result.get("data_limitations") or []) + [
            "Model returned empty findings after retry."
        ]
    return result


def _select_review_sample(
    reviews: list[dict[str, Any]], limit: int = 40
) -> list[dict[str, Any]]:
    """Prefer low ratings, then mid, then high — keeps evidence dense for analysis."""
    low = [r for r in reviews if (r.get("rating") or 0) <= 2]
    mid = [r for r in reviews if (r.get("rating") or 0) == 3]
    high = [r for r in reviews if (r.get("rating") or 0) >= 4]
    picked: list[dict[str, Any]] = []
    for bucket, quota in (
        (low, max(16, limit // 2)),
        (mid, max(8, limit // 4)),
        (high, max(8, limit // 4)),
    ):
        for r in bucket:
            if len(picked) >= limit:
                break
            if r not in picked:
                picked.append(r)
            if sum(1 for x in picked if x in bucket) >= quota and bucket is low:
                break
        if len(picked) >= limit:
            break
    # fill remaining
    for r in reviews:
        if len(picked) >= limit:
            break
        if r not in picked:
            picked.append(r)
    return picked[:limit]


def _normalize_analysis_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Accept common alternate key spellings from different models."""
    if not isinstance(result, dict):
        return {"classifications": [], "findings": []}

    findings = (
        result.get("findings")
        or result.get("Findings")
        or result.get("issues")
        or result.get("insights")
        or []
    )
    classifications = (
        result.get("classifications")
        or result.get("Classification")
        or result.get("labels")
        or []
    )
    if isinstance(findings, dict):
        findings = list(findings.values())
    if isinstance(classifications, dict):
        classifications = list(classifications.values())

    normalized_findings = []
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            continue
        src = (
            f.get("source_review_ids")
            or f.get("review_ids")
            or f.get("sourceReviews")
            or []
        )
        if isinstance(src, str):
            src = [src]
        normalized_findings.append(
            {
                "finding_key": str(
                    f.get("finding_key") or f.get("id") or f"F{i+1}"
                ),
                "title": f.get("title") or f.get("name") or f"Finding {i+1}",
                "summary": f.get("summary") or f.get("description") or "",
                "source_review_ids": [str(x) for x in src],
                "sample_count": int(f.get("sample_count") or len(src) or 0),
                "confidence": float(f.get("confidence") or 0.5),
                "uncertainty": f.get("uncertainty") or "",
                "conflicting_evidence": f.get("conflicting_evidence") or "",
                "evidence_excerpts": f.get("evidence_excerpts") or [],
                "is_assumption": bool(f.get("is_assumption", False)),
            }
        )

    result = dict(result)
    result["findings"] = normalized_findings
    result["classifications"] = classifications if isinstance(classifications, list) else []
    return result


def heuristic_analyze(
    reviews: list[dict[str, Any]],
    analysis_goal: str,
) -> dict[str, Any]:
    """
    Offline/demo fallback when LLM unavailable.
    Uses light keyword buckets ONLY as emergency fallback — labeled clearly.
    """
    buckets: dict[str, list[dict[str, Any]]] = {}
    keyword_map = [
        ("subscription_billing", ["subscri", "charge", "billing", "refund", "paywall", "trial", "price"]),
        ("workout_usability", ["workout", "exercise", "routine", "plan", "video", "follow"]),
        ("bugs_crashes", ["crash", "bug", "freeze", "error", "broken", "glitch"]),
        ("account_login", ["login", "sign in", "password", "account"]),
        ("ads_ux", ["ad", "ads", "popup", "notification"]),
    ]

    classifications = []
    for r in reviews:
        text = f"{r.get('title','')} {r.get('content','')}".lower()
        topics = []
        for key, kws in keyword_map:
            if any(k in text for k in kws):
                topics.append(key)
        if not topics:
            topics = ["general_feedback"]
        sentiment = "negative" if (r.get("rating") or 0) <= 2 else (
            "positive" if (r.get("rating") or 0) >= 4 else "neutral"
        )
        for t in topics:
            buckets.setdefault(t, []).append(r)
        classifications.append(
            {
                "review_id": r["review_id"],
                "topics": topics,
                "sentiment": sentiment,
                "priority_hint": "p1" if sentiment == "negative" else "none",
                "note": "heuristic_fallback",
            }
        )

    goal_l = (analysis_goal or "").lower()
    findings = []
    for key, items in buckets.items():
        if goal_l and "subscri" in goal_l and "subscri" not in key and "billing" not in key:
            conf = 0.35
        else:
            conf = min(0.75, 0.3 + 0.05 * len(items))
        findings.append(
            {
                "finding_key": key,
                "title": key.replace("_", " ").title(),
                "summary": f"{len(items)} reviews touch on '{key}' (heuristic grouping).",
                "source_review_ids": [i["review_id"] for i in items[:20]],
                "sample_count": min(len(items), 20),
                "confidence": conf,
                "uncertainty": "Generated by keyword heuristic fallback, not LLM topic discovery.",
                "conflicting_evidence": "",
                "evidence_excerpts": [
                    {
                        "review_id": i["review_id"],
                        "excerpt": (i.get("content") or i.get("title") or "")[:180],
                    }
                    for i in items[:3]
                ],
                "is_assumption": True,
            }
        )

    return {
        "classifications": classifications,
        "findings": findings,
        "evidence_sufficient": len(reviews) >= 15,
        "data_limitations": [
            "LLM unavailable; used labeled heuristic fallback.",
            "Topics are not dynamically model-discovered in this mode.",
        ],
        "conflicting_themes": [],
        "method": "heuristic_fallback_labeled",
        "model_meta": {},
        "used_fallback": True,
    }
