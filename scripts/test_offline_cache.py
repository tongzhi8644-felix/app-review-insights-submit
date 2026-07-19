import os
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["AI_ENABLED"] = "0"
os.environ["ALLOW_CACHED_FALLBACK"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:9"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:9"
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

from app import create_app


APP_URL = (
    "https://apps.apple.com/us/app/"
    "workout-for-women-home-gym/id839285684"
)


def main():
    app = create_app()
    client = app.test_client()
    response = client.post(
        "/api/analyze",
        json={
            "app_url": APP_URL,
            "analysis_goal": "offline cache verification",
        },
    )
    payload = response.get_json()
    result = payload.get("result") or {}
    analysis = result.get("analysis") or {}
    validation = result.get("validation") or {}
    collect_logs = [
        row
        for row in payload.get("stage_logs") or []
        if row.get("stage") == "collect"
    ]

    checks = {
        "http_200": response.status_code == 200,
        "completed": payload.get("status") == "completed",
        "cached_source": payload.get("data_source") == "cached_rss_labeled",
        "network_failed_then_cached": any(
            row.get("status") == "warning"
            and "using labeled cache" in (row.get("message") or "")
            for row in collect_logs
        ),
        "fallback_labeled": analysis.get("used_fallback") is True,
        "cached_method": analysis.get("method")
        == "cached_model_output_labeled",
        "real_review_count": (result.get("clean_stats") or {}).get("input_count")
        == 500,
        "real_findings": len(result.get("findings") or []) == 7,
        "real_requirements": len((result.get("prd") or {}).get("requirements") or [])
        == 10,
        "real_test_cases": len(result.get("test_cases") or []) == 4,
        "validation_valid": validation.get("is_valid") is True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    print("OFFLINE_CACHE_CHECKS", checks)
    print("DATA_SOURCE", payload.get("data_source"))
    print("ANALYSIS_METHOD", analysis.get("method"))
    print("USED_FALLBACK", analysis.get("used_fallback"))
    print("CACHE_NOTE", analysis.get("cache_note"))
    print("FINDINGS", len(result.get("findings") or []))
    print(
        "REQUIREMENTS",
        len((result.get("prd") or {}).get("requirements") or []),
    )
    print("TEST_CASES", len(result.get("test_cases") or []))
    print("VALIDATION", validation.get("is_valid"))
    if failed:
        raise SystemExit(f"Offline cache verification failed: {failed}")


if __name__ == "__main__":
    main()
