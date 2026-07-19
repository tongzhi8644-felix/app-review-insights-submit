"""
Model-driven test case generation linked to requirements and source reviews.
"""
from __future__ import annotations

import json
from typing import Any

from app.services.llm import chat_json, model_meta


SYSTEM = """You write QA test cases from a PRD.
Each test case must link to a requirement_id and source_review_ids.
Test steps must verify that the requirement solves the problems in those reviews.
Do not invent review IDs. Return strict JSON only."""


def generate_test_cases(
    requirements: list[dict[str, Any]],
    analysis_goal: str,
) -> dict[str, Any]:
    user_prompt = f"""Analysis goal: {analysis_goal or "(general)"}
Requirements JSON:
{json.dumps(requirements, ensure_ascii=False)}

Return JSON:
{{
  "test_cases": [
    {{
      "case_id": "TC-1",
      "requirement_id": "REQ-1",
      "title": "...",
      "steps": ["step1", "step2"],
      "expected_result": "...",
      "source_review_ids": ["..."]
    }}
  ]
}}
At least one test case per requirement when possible.
"""
    result = chat_json(SYSTEM, user_prompt)
    result["model_meta"] = model_meta()
    result["method"] = "model_driven"
    return result


def heuristic_test_cases(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    cases = []
    for i, req in enumerate(requirements, start=1):
        cases.append(
            {
                "case_id": f"TC-{i}",
                "requirement_id": req.get("requirement_id"),
                "title": f"Verify {req.get('requirement_id')}: {req.get('title')}",
                "steps": [
                    "Identify the user journey described in source reviews",
                    "Execute the updated product flow for this requirement",
                    "Compare outcome against acceptance criteria",
                ],
                "expected_result": "; ".join(req.get("acceptance_criteria") or [])
                or "Requirement acceptance criteria are met",
                "source_review_ids": req.get("source_review_ids") or [],
            }
        )
    return {
        "test_cases": cases,
        "model_meta": {"mode": "heuristic_fallback_labeled"},
        "method": "heuristic_fallback_labeled",
    }
