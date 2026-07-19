from flask import Blueprint, current_app, jsonify, request

from app.models import AnalysisRun, ReviewClean, ReviewRaw
from app.services import workflow

api_bp = Blueprint("api", __name__)


@api_bp.get("/health")
def health():
    return jsonify({"ok": True, "service": "app-review-insights"})


@api_bp.post("/analyze")
def analyze():
    """
    Start analysis.
    multipart / form: app_url, analysis_goal, use_sample, file(optional json/csv)
    or JSON body with the same fields (no file).
    """
    import_records = None
    use_sample = False
    app_url = ""
    analysis_goal = ""

    ctype = (request.content_type or "").lower()
    if "multipart/form-data" in ctype or "application/x-www-form-urlencoded" in ctype:
        app_url = (request.form.get("app_url") or "").strip()
        analysis_goal = (request.form.get("analysis_goal") or "").strip()
        use_sample = request.form.get("use_sample") in ("1", "true", "on", "yes")
        upload = request.files.get("file") if request.files else None
        if upload and upload.filename:
            import_records = workflow.parse_import_file(
                upload.filename, upload.read()
            )
    else:
        payload = request.get_json(silent=True) or {}
        app_url = (payload.get("app_url") or "").strip()
        analysis_goal = (payload.get("analysis_goal") or "").strip()
        use_sample = bool(payload.get("use_sample"))
        if payload.get("reviews"):
            import_records = payload["reviews"]

    if not app_url and not import_records and not use_sample:
        return (
            jsonify(
                {
                    "error": "Provide app_url, or upload reviews JSON/CSV, or set use_sample=1"
                }
            ),
            400,
        )

    if app_url:
        try:
            from app.services.collector import parse_app_id

            parse_app_id(app_url)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    run = workflow.start_run(
        app_url=app_url,
        analysis_goal=analysis_goal,
        import_records=import_records,
        use_sample=use_sample,
    )
    return jsonify(workflow.serialize_run(run))


@api_bp.get("/runs/<int:run_id>")
def get_run(run_id: int):
    run = AnalysisRun.query.get_or_404(run_id)
    return jsonify(workflow.serialize_run(run))


@api_bp.get("/runs/<int:run_id>/reviews/raw")
def raw_reviews(run_id: int):
    rows = ReviewRaw.query.filter_by(run_id=run_id).limit(500).all()
    return jsonify(
        [
            {
                "review_id": r.review_id,
                "author": r.author,
                "rating": r.rating,
                "title": r.title,
                "content": r.content,
                "version": r.version,
                "updated_at": r.updated_at,
            }
            for r in rows
        ]
    )


@api_bp.get("/runs/<int:run_id>/reviews/clean")
def clean_reviews(run_id: int):
    rows = ReviewClean.query.filter_by(run_id=run_id).limit(500).all()
    return jsonify(
        [
            {
                "review_id": r.review_id,
                "author": r.author,
                "rating": r.rating,
                "title": r.title,
                "content": r.content,
                "version": r.version,
                "language": r.language,
                "is_duplicate": r.is_duplicate,
            }
            for r in rows
        ]
    )


@api_bp.get("/meta/methods")
def methods_doc():
    return jsonify(
        {
            "collection": {
                "primary": "Apple iTunes Customer Reviews RSS JSON (US storefront)",
                "not_used": "HTML page scraping of visible App Store DOM",
                "import": "Documented JSON/CSV with review_id,rating,title,content,version,...",
                "limitations": [
                    "Recent public reviews only",
                    "Page cap via MAX_REVIEW_PAGES",
                    "Rate-limited client sleep between pages",
                ],
            },
            "model": {
                "provider_env": ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"],
                "tasks": [
                    "dynamic topic discovery / classification",
                    "evidence-grounded findings",
                    "PRD + version plan",
                    "test case generation",
                ],
                "anti_hallucination": [
                    "JSON-only responses",
                    "Must cite provided review_ids",
                    "Deterministic post-validation of traceability",
                ],
            },
            "cache": {
                "path": str(current_app.config["CACHE_DIR"]),
                "note": "Cached outputs are labeled and do not replace live processing when network+model are available.",
            },
        }
    )
