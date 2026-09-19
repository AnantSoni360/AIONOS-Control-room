import os
import httpx
from fastapi import APIRouter

router = APIRouter(prefix="/api/limits", tags=["Limits"])

@router.get("/")
async def check_limits():
    """
    Check the current API limits for configured LLM providers (Mistral and Groq).
    Returns their rate-limit status so the frontend can display trackers.
    """
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    mistral_status = "ok"
    groq_status = "ok"
    
    # Check Mistral
    async with httpx.AsyncClient() as client:
        if MISTRAL_API_KEY:
            try:
                url = "https://api.mistral.ai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
                data = {"model": "open-mistral-7b", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 1}
                r = await client.post(url, headers=headers, json=data, timeout=5.0)
                if r.status_code == 429:
                    mistral_status = "reached"
                elif r.status_code != 200:
                    mistral_status = "error"
            except Exception:
                mistral_status = "error"
        else:
            mistral_status = "missing"
            
        # Check Groq
        if GROQ_API_KEY:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
                data = {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 1}
                r = await client.post(url, headers=headers, json=data, timeout=5.0)
                if r.status_code == 429:
                    groq_status = "reached"
                elif r.status_code != 200:
                    groq_status = "error"
            except Exception:
                groq_status = "error"
        else:
            groq_status = "missing"

    return {
        "mistral": {"status": mistral_status, "provider": "Mistral AI"},
        "groq": {"status": groq_status, "provider": "Groq"}
    }
