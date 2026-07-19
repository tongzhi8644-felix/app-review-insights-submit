import os
import sys
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["AI_ENABLED"] = "1"
os.environ["OPENAI_API_KEY"] = "offline-sample-test-key"
os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:9/v1"
os.environ["ALLOW_CACHED_FALLBACK"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app import create_app
from app.services import analyzer, planner, testgen


def main():
    app = create_app()
    client = app.test_client()
    with (
        patch.object(
            analyzer,
            "analyze_reviews",
            side_effect=AssertionError("offline sample called analyzer model"),
        ) as analyze_mock,
        patch.object(
            planner,
            "build_prd",
            side_effect=AssertionError("offline sample called planner model"),
        ) as prd_mock,
        patch.object(
            testgen,
            "generate_test_cases",
            side_effect=AssertionError("offline sample called test model"),
        ) as tests_mock,
    ):
        response = client.post(
            "/api/analyze",
            json={
                "use_sample": True,
                "analysis_goal": "offline sample verification",
            },
        )

    payload = response.get_json()
    result = payload.get("result") or {}
    analysis = result.get("analysis") or {}
    validation = result.get("validation") or {}
    classify_logs = [
        row
        for row in payload.get("stage_logs") or []
        if row.get("stage") == "classify_analyze"
    ]
    checks = {
        "http_200": response.status_code == 200,
        "completed": payload.get("status") == "completed",
        "sample_source": payload.get("data_source") == "sample_file_labeled",
        "no_analyzer_model_call": analyze_mock.call_count == 0,
        "no_prd_model_call": prd_mock.call_count == 0,
        "no_test_model_call": tests_mock.call_count == 0,
        "offline_reason_logged": any(
            "offline sample mode disables model calls"
            in (row.get("message") or "")
            for row in classify_logs
        ),
        "cached_method": analysis.get("method")
        == "cached_model_output_labeled",
        "validation_valid": validation.get("is_valid") is True,
    }
    print("OFFLINE_SAMPLE_CHECKS", checks)
    print("DATA_SOURCE", payload.get("data_source"))
    print("ANALYSIS_METHOD", analysis.get("method"))
    print("FINDINGS", len(result.get("findings") or []))
    print(
        "REQUIREMENTS",
        len((result.get("prd") or {}).get("requirements") or []),
    )
    print("TEST_CASES", len(result.get("test_cases") or []))
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise SystemExit(f"Offline sample verification failed: {failed}")


if __name__ == "__main__":
    main()
