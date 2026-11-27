"""Runtime configuration loaded from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSettings:
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    deepgram_api_key: str
    elevenlabs_api_key: str
    openai_api_key: str
    openai_model: str
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_model: str
    control_plane_url: str
    control_plane_prefix: str
    internal_api_token: str
    agent_name: str
    fallback_business_id: str
    log_level: str

    @classmethod
    def from_env(cls) -> AgentSettings:
        return cls(
            livekit_url=os.getenv("LIVEKIT_URL", ""),
            livekit_api_key=os.getenv("LIVEKIT_API_KEY", ""),
            livekit_api_secret=os.getenv("LIVEKIT_API_SECRET", ""),
            deepgram_api_key=os.getenv("DEEPGRAM_API_KEY", ""),
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "baidu/ernie-5.5-flash-preview:free"),
            control_plane_url=(
                os.getenv("RELAY_API_URL")
                or os.getenv("CONTROL_PLANE_URL", "http://localhost:8001")
            ).rstrip("/"),
            control_plane_prefix=os.getenv("RELAY_API_PREFIX", "/v1"),
            internal_api_token=os.getenv("INTERNAL_API_TOKEN", ""),
            agent_name=os.getenv("AGENT_NAME", "relay-receptionist"),
            fallback_business_id=os.getenv("RELAY_BUSINESS_ID", ""),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def require(self) -> None:
        missing = [
            name
            for name in (
                "livekit_url",
                "livekit_api_key",
                "livekit_api_secret",
                "internal_api_token",
            )
            if not getattr(self, name)
        ]
        if missing:
            raise RuntimeError(f"missing required agent settings: {', '.join(missing)}")
