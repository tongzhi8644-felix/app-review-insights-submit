from app import create_app
from app.services.llm import chat_json, llm_configured, model_meta

app = create_app()
with app.app_context():
    print("configured", llm_configured())
    print("meta", model_meta())
    r = chat_json(
        "Return JSON only.",
        'Return {"ok": true, "model_check": "pass"}',
    )
    print("reply", r)
