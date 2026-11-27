"""LiveKit Agents entrypoint for the Relay receptionist."""

from __future__ import annotations

import json
import logging
from typing import Any

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RoomInputOptions,
    WorkerOptions,
    cli,
)
from livekit.plugins import deepgram, elevenlabs, noise_cancellation, openai, silero

from receptionist_agent.config import AgentSettings
from receptionist_agent.prompts import build_instructions
from receptionist_agent.tools import CallState, ControlPlaneClient, build_tools

logger = logging.getLogger("receptionist")


class ReceptionistAgent(Agent):
    def __init__(self, instructions: str, tools: list[Any]) -> None:
        super().__init__(instructions=instructions, tools=tools)


async def _load_context(ctx: JobContext, api: ControlPlaneClient) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if ctx.job.metadata:
        try:
            metadata = json.loads(ctx.job.metadata)
        except json.JSONDecodeError:
            metadata = {}
    business_id = str(metadata.get("business_id") or api.business_id)
    api.business_id = business_id
    api.call_id = str(metadata.get("call_id") or api.call_id)
    return await api.context()


async def entrypoint(ctx: JobContext) -> None:
    settings = AgentSettings.from_env()
    settings.require()
    await ctx.connect()

    api = ControlPlaneClient(
        base_url=settings.control_plane_url,
        token=settings.internal_api_token,
        business_id=settings.fallback_business_id,
    )
    context = await _load_context(ctx, api)
    business = context.get("business") or {}
    agent_config = context.get("agent") or {}
    greeting = business.get("greeting") or "Thanks for calling. How can I help you today?"

    state = CallState(call_id=api.call_id)
    session = AgentSession(
        stt=deepgram.STT(model=agent_config.get("stt_model", "nova-3")),
        llm=openai.LLM(model=agent_config.get("llm_model", settings.openai_model)),
        tts=elevenlabs.TTS(
            model=agent_config.get("tts_model", "eleven_turbo_v2_5"),
            voice_id=agent_config.get("voice_id", "21m00Tcm4TlvDq8ikWAM"),
        ),
        vad=silero.VAD.load(),
    )

    agent = ReceptionistAgent(
        instructions=build_instructions(business, agent_config),
        tools=build_tools(api, state, session),
    )
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )
    await session.generate_reply(instructions=greeting)
    logger.info("call.started", extra={"business_id": api.business_id, "call_id": api.call_id})


def main() -> None:
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":  # pragma: no cover
    main()
