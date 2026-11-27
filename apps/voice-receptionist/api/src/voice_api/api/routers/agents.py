"""Agent persona configuration."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from voice_api.api.deps import Session, UserDep
from voice_api.models import AgentConfig, Business
from voice_api.schemas import AgentCreate, AgentOut

router = APIRouter(prefix="/agents", tags=["agents"])


async def _business(session: Session, user: UserDep, business_id: uuid.UUID) -> Business:
    business = await session.get(Business, business_id)
    if not business or business.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="business not found")
    return business


@router.get("", response_model=list[AgentOut])
async def list_agents(
    session: Session, user: UserDep, business_id: uuid.UUID | None = None
) -> list[AgentOut]:
    query = select(AgentConfig).where(AgentConfig.tenant_id == user.tenant_id)
    if business_id:
        query = query.where(AgentConfig.business_id == business_id)
    result = await session.execute(query.order_by(AgentConfig.created_at))
    return [AgentOut.model_validate(agent) for agent in result.scalars()]


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(session: Session, user: UserDep, payload: AgentCreate) -> AgentOut:
    await _business(session, user, payload.business_id)
    agent = AgentConfig(
        tenant_id=user.tenant_id,
        business_id=payload.business_id,
        name=payload.name,
        voice_id=payload.voice_id,
        stt_model=payload.stt_model,
        tts_model=payload.tts_model,
        llm_model=payload.llm_model,
        prompt=payload.prompt,
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return AgentOut.model_validate(agent)


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(session: Session, user: UserDep, agent_id: uuid.UUID) -> AgentOut:
    agent = await session.get(AgentConfig, agent_id)
    if not agent or agent.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="agent not found")
    return AgentOut.model_validate(agent)
