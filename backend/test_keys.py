import os, httpx
from dotenv import load_dotenv

load_dotenv(".env")

M_KEY = os.getenv("MISTRAL_API_KEY")
G_KEY = os.getenv("GROQ_API_KEY")

print("Keys loaded:")
print(f"  Mistral: {M_KEY[:12]}...")
print(f"  Groq:    {G_KEY[:15]}...")
print()

# Test Mistral
print("--- Testing Mistral ---")
try:
    r = httpx.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {M_KEY}", "Content-Type": "application/json"},
        json={"model": "mistral-small-latest", "messages": [{"role": "user", "content": "Reply only: ok"}], "max_tokens": 5},
        timeout=10.0
    )
    if r.status_code == 200:
        reply = r.json()["choices"][0]["message"]["content"]
        print("  STATUS: WORKING OK")
        print(f"  Model: mistral-small-latest")
        print(f"  Response: {reply}")
    elif r.status_code == 429:
        print("  STATUS: RATE LIMITED - 429")
    else:
        print(f"  STATUS: ERROR {r.status_code} - {r.text[:100]}")
except Exception as e:
    print(f"  STATUS: EXCEPTION - {e}")

print()

# Test Groq with multiple models
print("--- Testing Groq ---")
groq_models = [
    "llama-3.3-70b-versatile",
    "llama3-70b-8192",
    "llama-3.1-70b-versatile",
    "llama3-groq-70b-8192-tool-use-preview",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]
for model in groq_models:
    try:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {G_KEY}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": "Reply only: ok"}], "max_tokens": 5},
            timeout=10.0
        )
        if r.status_code == 200:
            reply = r.json()["choices"][0]["message"]["content"]
            print(f"  STATUS: WORKING OK  Model: {model}")
            print(f"  Response: {reply}")
            break
        elif r.status_code == 429:
            print(f"  Model {model}: RATE LIMITED - 429")
        else:
            print(f"  Model {model}: {r.status_code} - {r.text[:70]}")
    except Exception as e:
        print(f"  Model {model}: EXCEPTION - {e}")
