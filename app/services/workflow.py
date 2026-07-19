"""
End-to-end analysis workflow with stage logging and persistence.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

from flask import current_app

from app.extensions import db
from app.models import (
    AnalysisRun,
    Classification,
    Finding,
    PrdDocument,
    ReviewClean,
    ReviewRaw,
    StageLog,
    TestCase,
    ValidationResult,
)
from app.services import analyzer, cleaner, collector, planner, testgen, validator
from app.services.llm import LLMError, llm_configured


STAGES = [
    "scope",
    "collect",
    "clean",
    "classify_analyze",
    "plan_prd",
    "test_cases",
    "validate",
    "persist_finalize",
]


def _log(run: AnalysisRun, stage: str, status: str, message: str, detail: Any = None):
    run.current_stage = stage
    db.session.add(
        StageLog(
            run_id=run.id,
            stage=stage,
            status=status,
            message=message,
            detail_json=detail if isinstance(detail, (dict, list)) else {"info": detail},
        )
    )
    db.session.commit()


def _set_progress(run: AnalysisRun, stage: str, pct: int, status: str = "running"):
    run.current_stage = stage
    run.progress_pct = pct
    run.status = status
    db.session.commit()


def start_run(
    app_url: str,
    analysis_goal: str = "",
    import_records: list[dict[str, Any]] | None = None,
    use_sample: bool = False,
) -> AnalysisRun:
    app_id = collector.parse_app_id(app_url) if app_url else "imported"
    if use_sample and not app_url:
        app_url = (
            "https://apps.apple.com/us/app/workout-for-women-home-gym/id839285684"
        )
        app_id = "839285684"

    run = AnalysisRun(
        app_id=app_id,
        app_url=app_url
        or "https://apps.apple.com/us/app/imported/id000000000",
        analysis_goal=analysis_goal or "",
        status="running",
        current_stage="queued",
        progress_pct=0,
    )
    db.session.add(run)
    db.session.commit()

    try:
        _execute(run, import_records=import_records, use_sample=use_sample)
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        _log(run, run.current_stage or "error", "error", str(exc))
        db.session.commit()
    return run


def _execute(
    run: AnalysisRun,
    import_records: list[dict[str, Any]] | None = None,
    use_sample: bool = False,
):
    goal = run.analysis_goal or ""
    offline_demo = bool(use_sample)

    # 1) Scope
    _set_progress(run, "scope", 5)
    _log(
        run,
        "scope",
        "ok",
        "Determined analysis scope from goal and upcoming data availability.",
        {
            "app_id": run.app_id,
            "storefront": "us",
            "goal": goal,
            "method": "deterministic_rules",
        },
    )

    # 2) Collect
    _set_progress(run, "collect", 15)
    raw_reviews: list[dict[str, Any]] = []
    data_source = "itunes_rss_us"

    if import_records:
        raw_reviews = collector.load_reviews_from_records(import_records)
        data_source = "import_json_csv"
        _log(
            run,
            "collect",
            "ok",
            f"Imported {len(raw_reviews)} reviews from upload.",
            {"source": data_source},
        )
    elif use_sample:
        raw_reviews = _load_sample_reviews()
        data_source = "sample_file_labeled"
        _log(
            run,
            "collect",
            "ok",
            f"Loaded {len(raw_reviews)} labeled sample reviews.",
            {"source": data_source, "path": str(current_app.config["SAMPLE_REVIEWS_PATH"])},
        )
    else:
        try:
            max_pages = current_app.config.get("MAX_REVIEW_PAGES", 10)
            raw_reviews = collector.fetch_reviews_rss(
                run.app_id, country="us", max_pages=max_pages
            )
            _log(
                run,
                "collect",
                "ok",
                f"Fetched {len(raw_reviews)} reviews from Apple US RSS.",
                {
                    "source": data_source,
                    "limitations": [
                        "RSS exposes recent public reviews only (~50/page, capped by MAX_REVIEW_PAGES)",
                        "Not a full historical dump",
                    ],
                },
            )
        except Exception as exc:
            if current_app.config.get("ALLOW_CACHED_FALLBACK"):
                cached = _try_load_cached_raw(run.app_id)
                if cached:
                    raw_reviews = cached
                    data_source = "cached_rss_labeled"
                    _log(
                        run,
                        "collect",
                        "warning",
                        f"Live fetch failed ({exc}); using labeled cache.",
                        {"source": data_source},
                    )
                else:
                    raise
            else:
                raise

    if not raw_reviews and current_app.config.get("ALLOW_CACHED_FALLBACK"):
        cached = _try_load_cached_raw(run.app_id)
        if cached:
            raw_reviews = cached
            data_source = "cached_rss_labeled"
            _log(
                run,
                "collect",
                "warning",
                "Empty live result; using labeled cache.",
                {"source": data_source},
            )

    run.data_source = data_source
    for rev in raw_reviews:
        db.session.add(
            ReviewRaw(
                run_id=run.id,
                review_id=rev["review_id"],
                author=rev.get("author"),
                rating=rev.get("rating"),
                title=rev.get("title"),
                content=rev.get("content"),
                version=rev.get("version"),
                updated_at=rev.get("updated_at"),
                vote_sum=rev.get("vote_sum") or 0,
                vote_count=rev.get("vote_count") or 0,
                raw_json=rev.get("raw_json"),
            )
        )
    db.session.commit()

    # 3) Clean
    _set_progress(run, "clean", 30)
    cleaned_pack = cleaner.clean_reviews(raw_reviews)
    scope_pack = cleaner.filter_by_goal(cleaned_pack["unique"], goal)
    scoped = scope_pack["scoped"]
    for rev in cleaned_pack["cleaned"]:
        db.session.add(
            ReviewClean(
                run_id=run.id,
                review_id=rev["review_id"],
                author=rev.get("author"),
                rating=rev.get("rating"),
                title=rev.get("title"),
                content=rev.get("content"),
                version=rev.get("version"),
                updated_at=rev.get("updated_at"),
                language=rev.get("language"),
                is_duplicate=rev.get("is_duplicate", False),
                content_hash=rev.get("content_hash"),
            )
        )
    db.session.commit()
    _log(
        run,
        "clean",
        "ok",
        "Cleaned, deduplicated, and scoped reviews.",
        {
            "stats": cleaned_pack["stats"],
            "scope_note": scope_pack["scope_note"],
            "scoped_count": len(scoped),
            "method": cleaned_pack["method"],
            "rationale": cleaned_pack["rationale"],
        },
    )

    # 4) Classify + analyze (model-driven preferred)
    _set_progress(run, "classify_analyze", 50)
    analysis = None
    try:
        if offline_demo:
            raise LLMError("offline sample mode disables model calls")
        if llm_configured():
            analysis = analyzer.analyze_reviews(scoped, goal, run.app_id)
            # If model returned empty findings, fall back to heuristic on real IDs
            # so the UI is never blank after a "successful" call.
            if not (analysis.get("findings") or []):
                heuristic = analyzer.heuristic_analyze(scoped, goal)
                analysis["findings"] = heuristic.get("findings") or []
                if not analysis.get("classifications"):
                    analysis["classifications"] = heuristic.get("classifications") or []
                analysis["used_fallback"] = True
                analysis["data_limitations"] = list(
                    analysis.get("data_limitations") or []
                ) + [
                    "Model returned empty findings; filled with labeled heuristic "
                    "grounded in the same live review IDs."
                ]
                _log(
                    run,
                    "classify_analyze",
                    "warning",
                    "Model call succeeded but findings were empty; applied heuristic fill.",
                    {
                        "finding_count": len(analysis.get("findings") or []),
                        "method": "model_then_heuristic_fill",
                    },
                )
            else:
                _log(
                    run,
                    "classify_analyze",
                    "ok",
                    "Completed model-driven topic discovery and findings.",
                    {
                        "finding_count": len(analysis.get("findings") or []),
                        "method": analysis.get("method"),
                        "model_meta": analysis.get("model_meta"),
                        "evidence_sufficient": analysis.get("evidence_sufficient"),
                        "data_limitations": analysis.get("data_limitations"),
                        "sample_size": analysis.get("sample_size"),
                    },
                )
        else:
            raise LLMError("OPENAI_API_KEY missing")
    except Exception as exc:
        cached_analysis = _try_load_matching_cached_bundle(
            run.app_id, data_source
        )
        if cached_analysis and current_app.config.get("ALLOW_CACHED_FALLBACK"):
            analysis = cached_analysis.get("analysis") or analyzer.heuristic_analyze(
                scoped, goal
            )
            source_method = analysis.get("method")
            if source_method != "cached_model_output_labeled":
                analysis["source_method"] = source_method
            analysis["method"] = "cached_model_output_labeled"
            analysis["used_fallback"] = True
            analysis["cache_note"] = (
                f"Live model failed/unavailable ({exc}); "
                "using labeled cache/heuristic — not a substitute for live runs when configured."
            )
            _log(
                run,
                "classify_analyze",
                "warning",
                analysis["cache_note"],
                {"method": analysis.get("method")},
            )
        else:
            analysis = analyzer.heuristic_analyze(scoped, goal)
            _log(
                run,
                "classify_analyze",
                "warning",
                f"Model unavailable ({exc}); labeled heuristic fallback used.",
                {"method": analysis.get("method")},
            )

    for c in analysis.get("classifications") or []:
        db.session.add(
            Classification(
                run_id=run.id,
                review_id=str(c.get("review_id")),
                topics_json=c.get("topics"),
                sentiment=c.get("sentiment"),
                priority_hint=c.get("priority_hint"),
                model_note=c.get("note"),
            )
        )
    db.session.commit()

    findings = analysis.get("findings") or []
    run.evidence_sufficient = bool(analysis.get("evidence_sufficient"))

    # 5) PRD
    _set_progress(run, "plan_prd", 70)
    try:
        if not offline_demo and llm_configured() and findings:
            prd = planner.build_prd(
                findings, goal, run.app_id, cleaned_pack["stats"]
            )
        else:
            raise LLMError("skip live prd")
    except Exception:
        cached_bundle = _try_load_matching_cached_bundle(
            run.app_id, data_source
        )
        if cached_bundle and cached_bundle.get("prd") and current_app.config.get(
            "ALLOW_CACHED_FALLBACK"
        ):
            prd = cached_bundle["prd"]
            source_method = prd.get("method")
            if source_method != "cached_model_output_labeled":
                prd["source_method"] = source_method
            prd["method"] = "cached_model_output_labeled"
            prd["cache_note"] = "Labeled cached PRD used due to model unavailability."
        else:
            prd = planner.heuristic_prd(findings, goal, run.app_id)

    _log(
        run,
        "plan_prd",
        "ok",
        "Produced version plan and PRD draft.",
        {
            "requirement_count": len(prd.get("requirements") or []),
            "method": prd.get("method"),
            "model_meta": prd.get("model_meta"),
        },
    )

    # 6) Test cases
    _set_progress(run, "test_cases", 85)
    requirements = prd.get("requirements") or []
    try:
        if not offline_demo and llm_configured() and requirements:
            tc_pack = testgen.generate_test_cases(requirements, goal)
        else:
            raise LLMError("skip live tc")
    except Exception:
        cached_bundle = _try_load_matching_cached_bundle(
            run.app_id, data_source
        )
        if cached_bundle and cached_bundle.get("test_cases") and current_app.config.get(
            "ALLOW_CACHED_FALLBACK"
        ):
            tc_pack = {
                "test_cases": cached_bundle["test_cases"],
                "method": "cached_labeled",
                "model_meta": {},
            }
        else:
            tc_pack = testgen.heuristic_test_cases(requirements)

    _log(
        run,
        "test_cases",
        "ok",
        "Generated test case drafts linked to requirements/reviews.",
        {
            "test_case_count": len(tc_pack.get("test_cases") or []),
            "method": tc_pack.get("method"),
        },
    )

    # 7) Validate traceability
    _set_progress(run, "validate", 92)
    review_id_set = {r["review_id"] for r in scoped}
    validation = validator.validate_traceability(
        review_id_set,
        findings,
        requirements,
        tc_pack.get("test_cases") or [],
    )
    findings = validation["findings"]
    requirements = validation["requirements"]
    test_cases = validation["test_cases"]
    prd["requirements"] = requirements

    db.session.add(
        ValidationResult(
            run_id=run.id,
            is_valid=validation["is_valid"],
            issues_json=validation["issues"],
            revisions_json=validation["revisions"],
            summary=validation["summary"],
        )
    )
    _log(
        run,
        "validate",
        "ok" if validation["is_valid"] else "warning",
        validation["summary"],
        {
            "issues": validation["issues"][:30],
            "revisions": validation["revisions"][:30],
            "method": validation["method"],
        },
    )

    # Persist findings / prd / tests
    for f in findings:
        db.session.add(
            Finding(
                run_id=run.id,
                finding_key=str(f.get("finding_key") or "")[:64],
                title=str(f.get("title") or "")[:512],
                summary=f.get("summary"),
                source_review_ids_json=f.get("source_review_ids"),
                sample_count=f.get("sample_count") or 0,
                confidence=f.get("confidence"),
                uncertainty=f.get("uncertainty"),
                conflicting_evidence=f.get("conflicting_evidence"),
                is_model_generated=not analysis.get("used_fallback", False),
                is_assumption=bool(f.get("is_assumption")),
                evidence_excerpts_json=f.get("evidence_excerpts"),
            )
        )

    db.session.add(
        PrdDocument(
            run_id=run.id,
            version_plan_json=prd.get("version_plan"),
            prd_markdown=prd.get("prd_markdown"),
            requirements_json=requirements,
            model_meta_json=prd.get("model_meta"),
        )
    )
    for tc in test_cases:
        db.session.add(
            TestCase(
                run_id=run.id,
                case_id=str(tc.get("case_id") or "")[:64],
                requirement_id=str(tc.get("requirement_id") or "")[:64],
                title=str(tc.get("title") or "")[:512],
                steps_json=tc.get("steps"),
                expected_result=tc.get("expected_result"),
                source_review_ids_json=tc.get("source_review_ids"),
            )
        )

    result_payload = {
        "data_source": data_source,
        "clean_stats": cleaned_pack["stats"],
        "scope_note": scope_pack["scope_note"],
        "analysis": {
            "method": analysis.get("method"),
            "evidence_sufficient": analysis.get("evidence_sufficient"),
            "data_limitations": analysis.get("data_limitations"),
            "conflicting_themes": analysis.get("conflicting_themes"),
            "model_meta": analysis.get("model_meta"),
            "used_fallback": analysis.get("used_fallback"),
            "cache_note": analysis.get("cache_note"),
        },
        "classifications": analysis.get("classifications"),
        "findings": findings,
        "prd": {
            "version_plan": prd.get("version_plan"),
            "requirements": requirements,
            "prd_markdown": prd.get("prd_markdown"),
            "method": prd.get("method"),
            "model_meta": prd.get("model_meta"),
        },
        "test_cases": test_cases,
        "validation": {
            "is_valid": validation["is_valid"],
            "summary": validation["summary"],
            "issues": validation["issues"],
            "revisions": validation["revisions"],
        },
        "method_choices": {
            "collect": "HTTP Apple RSS (deterministic) or import/cache",
            "clean": "rules (normalize/dedup)",
            "semantic": "LLM JSON topic discovery + PRD + tests when configured",
            "validate": "deterministic ID/traceability checks",
        },
    }
    run.result_json = result_payload
    run.status = "completed"
    run.progress_pct = 100
    run.current_stage = "done"
    db.session.commit()
    _log(run, "persist_finalize", "ok", "Final deliverables ready.", {"run_id": run.id})


def parse_import_file(filename: str, raw_bytes: bytes) -> list[dict[str, Any]]:
    name = (filename or "").lower()
    text = raw_bytes.decode("utf-8-sig")
    if name.endswith(".json"):
        data = json.loads(text)
        if isinstance(data, dict) and "reviews" in data:
            data = data["reviews"]
        if not isinstance(data, list):
            raise ValueError("JSON must be a list of reviews or {reviews: [...]}")
        return data
    if name.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)
    raise ValueError("Only .json or .csv imports are supported")


def serialize_run(run: AnalysisRun) -> dict[str, Any]:
    logs = (
        StageLog.query.filter_by(run_id=run.id)
        .order_by(StageLog.id.asc())
        .all()
    )
    return {
        "id": run.id,
        "app_id": run.app_id,
        "app_url": run.app_url,
        "analysis_goal": run.analysis_goal,
        "status": run.status,
        "current_stage": run.current_stage,
        "progress_pct": run.progress_pct,
        "error_message": run.error_message,
        "data_source": run.data_source,
        "evidence_sufficient": run.evidence_sufficient,
        "created_at": run.created_at.isoformat() + "Z" if run.created_at else None,
        "updated_at": run.updated_at.isoformat() + "Z" if run.updated_at else None,
        "stage_logs": [
            {
                "stage": l.stage,
                "status": l.status,
                "message": l.message,
                "detail": l.detail_json,
                "created_at": l.created_at.isoformat() + "Z" if l.created_at else None,
            }
            for l in logs
        ],
        "result": run.result_json,
    }


def _load_sample_reviews() -> list[dict[str, Any]]:
    path: Path = current_app.config["SAMPLE_REVIEWS_PATH"]
    data = json.loads(path.read_text(encoding="utf-8"))
    reviews = data["reviews"] if isinstance(data, dict) else data
    return collector.load_reviews_from_records(reviews)


def _try_load_cached_raw(app_id: str) -> list[dict[str, Any]] | None:
    cache_dir = Path(current_app.config["CACHE_DIR"])
    paths = [raw_path for _, raw_path, _ in _real_rss_cache_pairs(app_id)]
    paths.append(cache_dir / f"{app_id}_reviews.json")
    for path in paths:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        reviews = data["reviews"] if isinstance(data, dict) else data
        if reviews:
            return collector.load_reviews_from_records(reviews)
    # fall back to sample for demo app
    sample = current_app.config["SAMPLE_REVIEWS_PATH"]
    if sample.exists() and app_id == "839285684":
        return _load_sample_reviews()
    return None


def _try_load_cached_bundle(
    app_id: str, prefer_real: bool = False
) -> dict[str, Any] | None:
    cache_dir = Path(current_app.config["CACHE_DIR"])
    paths = []
    if prefer_real:
        paths.extend(
            bundle_path
            for _, _, bundle_path in _real_rss_cache_pairs(app_id)
        )
    paths.append(cache_dir / f"{app_id}_bundle.json")
    for path in paths:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def _try_load_matching_cached_bundle(
    app_id: str, data_source: str
) -> dict[str, Any] | None:
    if data_source == "cached_rss_labeled":
        return _try_load_cached_bundle(app_id, prefer_real=True)
    if data_source == "sample_file_labeled":
        return _try_load_cached_bundle(app_id)
    return None


def _real_rss_cache_pairs(
    app_id: str,
) -> list[tuple[int, Path, Path]]:
    cache_dir = Path(current_app.config["CACHE_DIR"])
    pattern = re.compile(
        rf"^{re.escape(app_id)}_reviews_real_rss_run(\d+)\.json$"
    )
    pairs: list[tuple[int, Path, Path]] = []
    for raw_path in cache_dir.glob(f"{app_id}_reviews_real_rss_run*.json"):
        match = pattern.fullmatch(raw_path.name)
        if not match:
            continue
        run_number = int(match.group(1))
        bundle_path = cache_dir / (
            f"{app_id}_bundle_real_rss_run{run_number}.json"
        )
        if bundle_path.exists() and _real_cache_pair_is_valid(
            raw_path, bundle_path
        ):
            pairs.append((run_number, raw_path, bundle_path))
    return sorted(pairs, key=lambda pair: pair[0], reverse=True)


def _real_cache_pair_is_valid(raw_path: Path, bundle_path: Path) -> bool:
    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        if bundle.get("source_data_file") != raw_path.name:
            return False
        expected_hash = str(bundle.get("source_data_sha256") or "").lower()
        if not expected_hash:
            return False
        actual_hash = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        return actual_hash == expected_hash
    except (OSError, ValueError, json.JSONDecodeError):
        return False
