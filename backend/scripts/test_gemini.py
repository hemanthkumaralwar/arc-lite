"""Check the Gemini assist step by step and show the real reason if it fails.

Run from the backend folder:
    venv\\Scripts\\activate
    python scripts\\test_gemini.py "how can I get my cetificate"

It never prints the API key. It makes one call to Google, so it may use part of your free quota.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app import llm_assist  # noqa: E402
from app.config import ENV_FILE, settings  # noqa: E402


def main() -> int:
    question = " ".join(sys.argv[1:]) or "how can I get my cetificate"

    print(f"Settings file: {ENV_FILE} (exists: {ENV_FILE.exists()})")
    print(f"ENABLE_LLM_ASSIST: {settings.enable_llm_assist}")
    print(f"GEMINI_MODEL: {settings.gemini_model}")
    print(f"GEMINI_API_KEY present: {bool(settings.gemini_api_key)}")

    if not settings.enable_llm_assist:
        print("\nStop: set ENABLE_LLM_ASSIST=true in backend\\.env, save, and run this again.")
        return 1
    if not settings.gemini_api_key:
        print("\nStop: add GEMINI_API_KEY to backend\\.env, save, and run this again.")
        return 1

    print(f"\nQuestion: {question}")
    result = llm_assist.rewrite_query(question)

    if result is not None:
        print(f"Rewritten query: {result}")
        print("Result: OK. The assist works. If the chat still shows the wrong answer, "
              "restart uvicorn so it reads the new settings.")
        return 0

    print("Result: FAILED")
    if llm_assist.last_error:
        print(f"Reason: {llm_assist.last_error}")
    elif llm_assist.last_raw is not None:
        print(f"Reason: the model replied, but the reply was not a plain short phrase. Raw reply: {llm_assist.last_raw!r}")
    else:
        print("Reason: unknown. Paste this output to the team.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
