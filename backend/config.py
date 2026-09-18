"""
config.py - AIONOS application configuration.

Uses pydantic-settings to validate all required env vars on startup.
Import `settings` anywhere in the app to access typed config values.
"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url:              str
    supabase_anon_key:         str
    supabase_service_role_key: str

    # JWT (Supabase uses HS256 with the service-role key as secret)
    jwt_secret:     str = ""    # falls back to supabase_service_role_key if empty
    jwt_algorithm:  str = "HS256"

    # Google AI
    google_api_key: str

    # Agent limits
    agent_timeout_seconds: int = 120
    agent_max_retries:     int = 2

    # Rate limits (requests per minute)
    rate_limit_agents:     str = "10/minute"
    rate_limit_supervisor: str = "5/minute"
    rate_limit_default:    str = "120/minute"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug:    bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def effective_jwt_secret(self) -> str:
        return self.jwt_secret or self.supabase_service_role_key


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
