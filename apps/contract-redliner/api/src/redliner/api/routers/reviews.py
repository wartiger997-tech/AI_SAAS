"""Review lifecycle, findings, and exports."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from redliner.api.deps import Session
from redliner.models import AuditEvent, Document, Finding, Playbook, Review
from redliner.schemas import (
    DocumentOut,
    ExportRequest,
    ExportResponse,
    FindingOut,
    FindingPatch,
    ReviewCreate,
    ReviewDetail,
    ReviewOut,
)
from redliner.security import CurrentUser
from redliner.services.jobs import enqueue_review
from redliner.services.redline import RenderFinding, RenderInput, render
from redliner.services.review import build_export_data

router = APIRouter(tags=["reviews"])


async def _load_review(session: Session, user: CurrentUser, review_id: uuid.UUID) -> Review:
    review = await session.get(Review, review_id)
    if not review or review.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="review not found")
    return review


@router.post(
    "/documents/{document_id}/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_review(
    session: Session,
    user: CurrentUser,
    document_id: uuid.UUID,
    payload: ReviewCreate,
) -> ReviewOut:
    document = await session.get(Document, document_id)
    if not document or document.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="document not found")
    playbook = await session.get(Playbook, payload.playbook_id)
    if not playbook or playbook.tenant_id != user.tenant_id or not playbook.is_active:
        raise HTTPException(status_code=400, detail="playbook not found or inactive")
    review = Review(
        tenant_id=user.tenant_id,
        document_id=document.id,
        playbook_id=playbook.id,
        reviewer_role=payload.reviewer_role,
        status="queued",
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    try:
        await enqueue_review(review.id)
    except Exception as exc:  # noqa: BLE001
        review.status = "failed"
        review.error = f"failed to enqueue: {exc}"
        await session.commit()
        raise HTTPException(status_code=503, detail="queue unavailable") from exc
    out = ReviewOut.model_validate(review)
    out.finding_count = 0
    return out


@router.get("/reviews", response_model=list[ReviewOut])
async def list_reviews(
    session: Session,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ReviewOut]:
    result = await session.execute(
        select(Review, func.count(Finding.id))
        .outerjoin(Finding, Finding.review_id == Review.id)
        .where(Review.tenant_id == user.tenant_id)
        .group_by(Review.id)
        .order_by(Review.created_at.desc())
        .limit(limit)
    )
    out: list[ReviewOut] = []
    for review, count in result.all():
        item = ReviewOut.model_validate(review)
        item.finding_count = int(count)
        out.append(item)
    return out


@router.get("/reviews/{review_id}", response_model=ReviewDetail)
async def get_review(session: Session, user: CurrentUser, review_id: uuid.UUID) -> ReviewDetail:
    review = await _load_review(session, user, review_id)
    document = await session.get(Document, review.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="document not found")
    result = await session.execute(
        select(Finding)
        .where(Finding.review_id == review.id)
        .order_by(Finding.page, Finding.severity)
    )
    findings = result.scalars().all()
    detail = ReviewDetail.model_validate(review)
    detail.document = DocumentOut.model_validate(document)
    detail.findings = [FindingOut.model_validate(f) for f in findings]
    detail.finding_count = len(findings)
    return detail


@router.patch("/findings/{finding_id}", response_model=FindingOut)
async def patch_finding(
    session: Session, user: CurrentUser, finding_id: uuid.UUID, payload: FindingPatch
) -> FindingOut:
    result = await session.execute(
        select(Finding)
        .join(Review, Finding.review_id == Review.id)
        .where(Finding.id == finding_id, Review.tenant_id == user.tenant_id)
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="finding not found")
    if payload.status is not None:
        finding.status = payload.status
    if payload.reviewer_note is not None:
        finding.reviewer_note = payload.reviewer_note
    session.add(
        AuditEvent(
            tenant_id=user.tenant_id,
            actor=user.email,
            action="finding.updated",
            subject=str(finding.id),
            meta={"status": finding.status},
        )
    )
    await session.commit()
    await session.refresh(finding)
    return FindingOut.model_validate(finding)


@router.post("/reviews/{review_id}/export")
async def export_review(
    session: Session,
    user: CurrentUser,
    review_id: uuid.UUID,
    payload: ExportRequest,
) -> Response:
    await _load_review(session, user, review_id)
    data = await build_export_data(session, review_id)
    if not payload.include_dismissed:
        data["findings"] = [f for f in data["findings"] if f["status"] != "dismissed"]
    render_input = RenderInput(
        title=data["title"],
        pages=data["pages"],
        findings=[RenderFinding(**f) for f in data["findings"]],
        reviewer_role=data["reviewer_role"],
    )
    content, content_type = render(payload.format, render_input)
    filename = f"clauseguard-{review_id}.{payload.format}"
    session.add(
        AuditEvent(
            tenant_id=user.tenant_id,
            actor=user.email,
            action="review.exported",
            subject=str(review_id),
            meta={"format": payload.format, "bytes": len(content)},
        )
    )
    await session.commit()
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reviews/{review_id}/export", response_model=ExportResponse)
async def export_meta(session: Session, user: CurrentUser, review_id: uuid.UUID) -> ExportResponse:
    """Return export metadata (the POST endpoint streams bytes)."""
    await _load_review(session, user, review_id)
    return ExportResponse(
        filename=f"clauseguard-{review_id}.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=0,
        url=f"/v1/reviews/{review_id}/export",
    )
