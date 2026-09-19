import os
from dotenv import load_dotenv
import httpx
import asyncio

load_dotenv(".env")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

async def test_mistral():
    if not MISTRAL_API_KEY:
        return "Mistral: No API Key configured."
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "open-mistral-7b",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 5
    }
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, headers=headers, json=data, timeout=10.0)
            if r.status_code == 200:
                return f"Mistral: OK (Limit not reached)"
            elif r.status_code == 429:
                return f"Mistral: Rate Limit Reached! (429)"
            else:
                return f"Mistral: Error {r.status_code} - {r.text}"
        except Exception as e:
            return f"Mistral: Exception {e}"

async def test_groq():
    if not GROQ_API_KEY:
        return "Groq: No API Key configured."
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 5
    }
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(url, headers=headers, json=data, timeout=10.0)
            if r.status_code == 200:
                return f"Groq: OK (Limit not reached)"
            elif r.status_code == 429:
                return f"Groq: Rate Limit Reached! (429)"
            else:
                return f"Groq: Error {r.status_code} - {r.text}"
        except Exception as e:
            return f"Groq: Exception {e}"

async def main():
    print(await test_mistral())
    print(await test_groq())

if __name__ == "__main__":
    asyncio.run(main())
