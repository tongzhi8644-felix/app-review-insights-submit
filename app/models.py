from datetime import datetime

from app.extensions import db


class AnalysisRun(db.Model):
    __tablename__ = "analysis_runs"

    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.String(32), nullable=False, index=True)
    app_url = db.Column(db.String(512), nullable=False)
    analysis_goal = db.Column(db.Text)
    status = db.Column(db.String(32), nullable=False, default="pending", index=True)
    current_stage = db.Column(db.String(64))
    progress_pct = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text)
    data_source = db.Column(db.String(64))
    evidence_sufficient = db.Column(db.Boolean)
    result_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    stage_logs = db.relationship(
        "StageLog", backref="run", lazy="dynamic", cascade="all, delete-orphan"
    )


class StageLog(db.Model):
    __tablename__ = "stage_logs"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("analysis_runs.id"), nullable=False)
    stage = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(32), nullable=False)
    message = db.Column(db.Text)
    detail_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ReviewRaw(db.Model):
    __tablename__ = "reviews_raw"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("analysis_runs.id"), nullable=False)
    review_id = db.Column(db.String(64), nullable=False, index=True)
    author = db.Column(db.String(255))
    rating = db.Column(db.Integer)
    title = db.Column(db.Text)
    content = db.Column(db.Text)
    version = db.Column(db.String(64))
    updated_at = db.Column(db.String(64))
    vote_sum = db.Column(db.Integer, default=0)
    vote_count = db.Column(db.Integer, default=0)
    raw_json = db.Column(db.JSON)


class ReviewClean(db.Model):
    __tablename__ = "reviews_clean"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("analysis_runs.id"), nullable=False)
    review_id = db.Column(db.String(64), nullable=False, index=True)
    author = db.Column(db.String(255))
    rating = db.Column(db.Integer)
    title = db.Column(db.Text)
    content = db.Column(db.Text)
    version = db.Column(db.String(64))
    updated_at = db.Column(db.String(64))
    language = db.Column(db.String(16))
    is_duplicate = db.Column(db.Boolean, default=False)
    content_hash = db.Column(db.String(64))


class Classification(db.Model):
    __tablename__ = "classifications"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("analysis_runs.id"), nullable=False)
    review_id = db.Column(db.String(64), nullable=False)
    topics_json = db.Column(db.JSON)
    sentiment = db.Column(db.String(32))
    priority_hint = db.Column(db.String(32))
    model_note = db.Column(db.Text)


class Finding(db.Model):
    __tablename__ = "findings"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("analysis_runs.id"), nullable=False)
    finding_key = db.Column(db.String(64), nullable=False)
    title = db.Column(db.String(512), nullable=False)
    summary = db.Column(db.Text)
    source_review_ids_json = db.Column(db.JSON)
    sample_count = db.Column(db.Integer, default=0)
    confidence = db.Column(db.Float)
    uncertainty = db.Column(db.Text)
    conflicting_evidence = db.Column(db.Text)
    is_model_generated = db.Column(db.Boolean, default=True)
    is_assumption = db.Column(db.Boolean, default=False)
    evidence_excerpts_json = db.Column(db.JSON)


class PrdDocument(db.Model):
    __tablename__ = "prd_documents"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("analysis_runs.id"), nullable=False)
    version_plan_json = db.Column(db.JSON)
    prd_markdown = db.Column(db.Text)
    requirements_json = db.Column(db.JSON)
    model_meta_json = db.Column(db.JSON)


class TestCase(db.Model):
    __tablename__ = "test_cases"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("analysis_runs.id"), nullable=False)
    case_id = db.Column(db.String(64), nullable=False)
    requirement_id = db.Column(db.String(64))
    title = db.Column(db.String(512))
    steps_json = db.Column(db.JSON)
    expected_result = db.Column(db.Text)
    source_review_ids_json = db.Column(db.JSON)


class ValidationResult(db.Model):
    __tablename__ = "validation_results"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("analysis_runs.id"), nullable=False)
    is_valid = db.Column(db.Boolean, default=False)
    issues_json = db.Column(db.JSON)
    revisions_json = db.Column(db.JSON)
    summary = db.Column(db.Text)
