"""Standalone Gemini key + quota check.

Isolates auth / model-access / quota from the full RAG pipeline.
Run with: python test_gemini_key.py
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import errors as genai_errors


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    print("=" * 60)
    print(" GEMINI KEY TEST")
    print("=" * 60)
    print(f"Key loaded from .env  : {'Yes' if api_key else 'NO — set GEMINI_API_KEY in .env'}")
    if not api_key:
        sys.exit(1)
    print(f"Key length            : {len(api_key)} chars")
    print(f"Key prefix            : {api_key[:6]}...{api_key[-4:]}")
    print()

    client = genai.Client(api_key=api_key)

    # Test 1: can we list models? (auth check)
    print("-" * 60)
    print(" Test 1: List available models (auth check)")
    print("-" * 60)
    try:
        models = list(client.models.list())
        gen_models = [m for m in models if "generateContent" in (m.supported_actions or [])]
        print(f"AUTH OK. {len(models)} total models visible, {len(gen_models)} support generateContent:")
        for m in gen_models[:10]:
            print(f"  - {m.name}")
        if len(gen_models) > 10:
            print(f"  ... and {len(gen_models) - 10} more")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        sys.exit(2)
    print()

    # Test 2: minimal generation on gemini-2.0-flash
    test_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]
    for model_name in test_models:
        print("-" * 60)
        print(f" Test: minimal generation on '{model_name}'")
        print("-" * 60)
        try:
            response = client.models.generate_content(
                model=model_name,
                contents="Respond with exactly: PASS",
            )
            print(f"SUCCESS. Response: {response.text!r}")
        except genai_errors.ClientError as e:
            status = getattr(e, "code", None) or getattr(e, "status_code", "?")
            print(f"CLIENT ERROR (status {status}): {e}")
            if status == 429:
                print("    -> RATE LIMIT or QUOTA = 0")
            elif status == 404:
                print("    -> Model not available on your key/region")
            elif status == 403:
                print("    -> Permission denied (key invalid or API not enabled)")
        except genai_errors.ServerError as e:
            print(f"SERVER ERROR: {e}")
        except Exception as e:
            print(f"OTHER: {type(e).__name__}: {e}")
        print()

    print("=" * 60)
    print(" Done. If all three Test failed with 429 limit:0,")
    print(" the project linked to your key has no free quota.")
    print(" Fix: generate a NEW key at https://aistudio.google.com/app/apikey")
    print("      and make sure you're signed in to the same Google account")
    print("      where you accepted the API terms.")
    print("=" * 60)


if __name__ == "__main__":
    main()
