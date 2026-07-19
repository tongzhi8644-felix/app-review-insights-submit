"""
Traceability validation: reviews -> findings -> requirements -> test cases.
Unsupported conclusions are removed, revised, or marked as assumptions.
"""
from __future__ import annotations

from typing import Any


def validate_traceability(
    review_ids: set[str],
    findings: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
    test_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    revisions: list[dict[str, Any]] = []

    revised_findings = []
    for f in findings:
        src = [str(x) for x in (f.get("source_review_ids") or [])]
        valid = [x for x in src if x in review_ids]
        invalid = [x for x in src if x not in review_ids]
        if invalid:
            issues.append(
                {
                    "type": "invalid_review_id",
                    "entity": "finding",
                    "key": f.get("finding_key"),
                    "invalid_ids": invalid,
                }
            )
            revisions.append(
                {
                    "action": "drop_invalid_ids",
                    "entity": "finding",
                    "key": f.get("finding_key"),
                    "dropped": invalid,
                }
            )
        if not valid:
            f = dict(f)
            f["is_assumption"] = True
            f["uncertainty"] = (
                (f.get("uncertainty") or "")
                + " | Marked assumption: no valid source review IDs after validation."
            ).strip(" |")
            f["source_review_ids"] = []
            f["sample_count"] = 0
            f["confidence"] = min(float(f.get("confidence") or 0.2), 0.2)
            revisions.append(
                {
                    "action": "mark_assumption",
                    "entity": "finding",
                    "key": f.get("finding_key"),
                }
            )
            # Drop unsupported finding conclusions entirely if zero evidence
            issues.append(
                {
                    "type": "unsupported_finding_removed",
                    "key": f.get("finding_key"),
                }
            )
            revisions.append(
                {
                    "action": "remove",
                    "entity": "finding",
                    "key": f.get("finding_key"),
                    "reason": "no valid source reviews",
                }
            )
            continue

        f = dict(f)
        f["source_review_ids"] = valid
        f["sample_count"] = len(valid)
        if int(f.get("sample_count") or 0) < 3:
            f["is_assumption"] = True
            revisions.append(
                {
                    "action": "mark_assumption_low_sample",
                    "entity": "finding",
                    "key": f.get("finding_key"),
                    "sample_count": f["sample_count"],
                }
            )
        revised_findings.append(f)

    valid_finding_keys = {f.get("finding_key") for f in revised_findings}
    known_req_review_ids = set()

    revised_requirements = []
    for req in requirements:
        src = [str(x) for x in (req.get("source_review_ids") or [])]
        valid = [x for x in src if x in review_ids]
        invalid = [x for x in src if x not in review_ids]
        if invalid:
            issues.append(
                {
                    "type": "invalid_review_id",
                    "entity": "requirement",
                    "key": req.get("requirement_id"),
                    "invalid_ids": invalid,
                }
            )
            revisions.append(
                {
                    "action": "drop_invalid_ids",
                    "entity": "requirement",
                    "key": req.get("requirement_id"),
                    "dropped": invalid,
                }
            )
        if not valid:
            issues.append(
                {
                    "type": "requirement_removed",
                    "key": req.get("requirement_id"),
                    "reason": "no valid source reviews",
                }
            )
            revisions.append(
                {
                    "action": "remove",
                    "entity": "requirement",
                    "key": req.get("requirement_id"),
                }
            )
            continue
        req = dict(req)
        req["source_review_ids"] = valid
        # prune finding keys that were removed
        sf = [k for k in (req.get("source_finding_keys") or []) if k in valid_finding_keys]
        req["source_finding_keys"] = sf
        known_req_review_ids.update(valid)
        revised_requirements.append(req)

    req_ids = {r.get("requirement_id") for r in revised_requirements}
    revised_cases = []
    for tc in test_cases:
        req_id = tc.get("requirement_id")
        if req_id not in req_ids:
            issues.append(
                {
                    "type": "orphan_test_case",
                    "key": tc.get("case_id"),
                    "requirement_id": req_id,
                }
            )
            revisions.append(
                {
                    "action": "remove",
                    "entity": "test_case",
                    "key": tc.get("case_id"),
                    "reason": "requirement missing after validation",
                }
            )
            continue
        src = [str(x) for x in (tc.get("source_review_ids") or [])]
        valid = [x for x in src if x in review_ids]
        if not valid:
            # inherit from requirement
            parent = next(
                (r for r in revised_requirements if r.get("requirement_id") == req_id),
                None,
            )
            valid = list(parent.get("source_review_ids") or []) if parent else []
            revisions.append(
                {
                    "action": "inherit_review_ids",
                    "entity": "test_case",
                    "key": tc.get("case_id"),
                    "from_requirement": req_id,
                }
            )
        tc = dict(tc)
        tc["source_review_ids"] = valid
        revised_cases.append(tc)

    # requirements without any test coverage
    covered = {c.get("requirement_id") for c in revised_cases}
    for req in revised_requirements:
        if req.get("requirement_id") not in covered:
            issues.append(
                {
                    "type": "requirement_without_test",
                    "key": req.get("requirement_id"),
                }
            )

    is_valid = not any(
        i["type"] in {"unsupported_finding_removed", "requirement_removed"}
        and False  # informational; validity based on remaining chain
        for i in issues
    )
    # Consider valid if we still have at least one full chain
    chain_ok = bool(revised_findings and revised_requirements and revised_cases)
    is_valid = chain_ok

    summary = (
        f"Validation complete: {len(revised_findings)} findings, "
        f"{len(revised_requirements)} requirements, {len(revised_cases)} test cases. "
        f"Issues logged: {len(issues)}; revisions applied: {len(revisions)}."
    )

    return {
        "is_valid": is_valid,
        "issues": issues,
        "revisions": revisions,
        "summary": summary,
        "findings": revised_findings,
        "requirements": revised_requirements,
        "test_cases": revised_cases,
        "method": "deterministic_rules",
        "rationale": (
            "Traceability checks are deterministic: only known review IDs may "
            "appear; unsupported items are removed or marked as assumptions."
        ),
    }
