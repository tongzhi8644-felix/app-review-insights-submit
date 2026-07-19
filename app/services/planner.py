"""
Model-driven PRD + version planning grounded in findings.
"""
from __future__ import annotations

import json
from typing import Any

from app.services.llm import chat_json, model_meta


SYSTEM = """You are a senior product manager. Create an actionable PRD and version plan
from review findings. Every requirement MUST cite source_review_ids from findings.
Do not invent evidence. Prefer clear boundaries, priorities, and measurable outcomes.
Return strict JSON only."""


def build_prd(
    findings: list[dict[str, Any]],
    analysis_goal: str,
    app_id: str,
    stats: dict[str, Any],
) -> dict[str, Any]:
    user_prompt = f"""App ID: {app_id}
Analysis goal: {analysis_goal or "(general)"}
Dataset stats: {json.dumps(stats, ensure_ascii=False)}

Findings JSON:
{json.dumps(findings, ensure_ascii=False)}

Return JSON:
{{
  "version_plan": [
    {{"version": "v1.x", "theme": "...", "goal": "...", "requirement_ids": ["REQ-1"]}}
  ],
  "requirements": [
    {{
      "requirement_id": "REQ-1",
      "title": "...",
      "priority": "P0|P1|P2",
      "user_problem": "...",
      "description": "...",
      "acceptance_criteria": ["..."],
      "source_finding_keys": ["..."],
      "source_review_ids": ["..."],
      "out_of_scope": ["..."]
    }}
  ],
  "prd_markdown": "# PRD ... markdown document with sections Background, Goals, Requirements, Version Plan, Risks, Open Questions"
}}
"""
    result = chat_json(SYSTEM, user_prompt)
    result["model_meta"] = model_meta()
    result["method"] = "model_driven"
    return result


def heuristic_prd(
    findings: list[dict[str, Any]],
    analysis_goal: str,
    app_id: str,
) -> dict[str, Any]:
    requirements = []
    for i, f in enumerate(findings[:8], start=1):
        rid = f"REQ-{i}"
        requirements.append(
            {
                "requirement_id": rid,
                "title": f"Address: {f.get('title')}",
                "priority": "P0" if (f.get("confidence") or 0) >= 0.6 else "P1",
                "user_problem": f.get("summary"),
                "description": (
                    f"Improve the product experience related to '{f.get('title')}' "
                    f"based on {f.get('sample_count')} supporting reviews."
                ),
                "acceptance_criteria": [
                    "Issue mentioned in source reviews is measurably reduced",
                    "Telemetry or support tickets for this theme decline after release",
                ],
                "source_finding_keys": [f.get("finding_key")],
                "source_review_ids": f.get("source_review_ids") or [],
                "out_of_scope": ["Unrelated feature redesign"],
            }
        )

    v1 = [r["requirement_id"] for r in requirements if r["priority"] == "P0"] or [
        r["requirement_id"] for r in requirements[:3]
    ]
    v2 = [r["requirement_id"] for r in requirements if r["requirement_id"] not in v1]

    md_lines = [
        f"# PRD — App {app_id}",
        "",
        f"**Analysis goal:** {analysis_goal or 'General product improvement'}",
        "",
        "## Background",
        "This PRD was generated from cleaned App Store reviews (fallback planner).",
        "",
        "## Requirements",
    ]
    for r in requirements:
        md_lines.append(f"### {r['requirement_id']}: {r['title']}")
        md_lines.append(r["description"])
        md_lines.append(f"- Priority: {r['priority']}")
        md_lines.append(f"- Source reviews: {', '.join(r['source_review_ids'][:10])}")
        md_lines.append("")

    return {
        "version_plan": [
            {
                "version": "vNext.1",
                "theme": "Highest-confidence pain points",
                "goal": analysis_goal or "Reduce top user friction",
                "requirement_ids": v1,
            },
            {
                "version": "vNext.2",
                "theme": "Secondary improvements",
                "goal": "Address remaining grounded findings",
                "requirement_ids": v2,
            },
        ],
        "requirements": requirements,
        "prd_markdown": "\n".join(md_lines),
        "model_meta": {"mode": "heuristic_fallback_labeled"},
        "method": "heuristic_fallback_labeled",
    }
