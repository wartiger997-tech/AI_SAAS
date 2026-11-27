"""Control-plane client and LiveKit function tools.

Tools are the only way the model can affect the world. Every tool is scoped to
the current business/call, validates its inputs, and returns a short string the
model can speak. Durable state is written by the API before the agent confirms
anything to the caller.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

import httpx
from livekit.agents import function_tool

from receptionist_agent.outcomes import normalize_outcome
from receptionist_agent.prompts import OUTCOMES
from receptionist_agent.redaction import redact_pii
from receptionist_agent.slots import OfferedSlots


class ControlPlaneError(RuntimeError):
    pass


@dataclass
class CallState:
    call_id: str = ""
    offered: OfferedSlots = field(default_factory=OfferedSlots)
    ended: bool = False
    outcome: str | None = None
    summary: str = ""


class ControlPlaneClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        business_id: str,
        call_id: str = "",
        api_prefix: str = "/v1",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_prefix = "/" + api_prefix.strip("/") if api_prefix.strip("/") else ""
        self.token = token
        self.business_id = business_id
        self.call_id = call_id

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = {"X-Internal-Token": self.token}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(
                method, f"{self.base_url}{path}", headers=headers, **kwargs
            )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail")
            except Exception:  # noqa: BLE001
                detail = response.text[:300]
            raise ControlPlaneError(f"{response.status_code}: {detail}")
        if not response.content:
            return None
        return response.json()

    async def context(self) -> dict[str, Any]:
        data = await self._request(
            "GET", f"{self.api_prefix}/internal/context?business_id={self.business_id}"
        )
        if not self.call_id:
            self.call_id = str(data.get("call", {}).get("id", ""))
        return data

    async def availability(self, date: str, service: str = "") -> list[dict[str, str]]:
        params = {"business_id": self.business_id, "date": date, "days": 3}
        if service:
            params["service"] = service
        data = await self._request("GET", f"{self.api_prefix}/internal/availability", params=params)
        return list(data.get("slots", []))

    async def book(
        self,
        starts_at: str,
        service: str,
        contact_name: str,
        contact_phone: str,
    ) -> dict[str, Any]:
        payload = {
            "business_id": self.business_id,
            "starts_at": starts_at,
            "service": service,
            "contact_name": contact_name,
            "contact_phone": contact_phone,
            "call_id": self.call_id or None,
        }
        return await self._request("POST", f"{self.api_prefix}/internal/bookings", json=payload)

    async def knowledge(self, query: str) -> list[dict[str, Any]]:
        data = await self._request(
            "GET", f"{self.api_prefix}/internal/knowledge", params={"business_id": self.business_id}
        )
        needle = query.lower()
        hits = []
        for doc in data or []:
            haystack = f"{doc.get('title', '')} {doc.get('content', '')}".lower()
            if needle in haystack or any(
                word in haystack for word in needle.split() if len(word) > 3
            ):
                hits.append(doc)
        return hits[:3]

    async def log_turn(self, role: str, content: str) -> None:
        if not self.call_id:
            return
        await self._request(
            "POST",
            f"{self.api_prefix}/internal/calls/{self.call_id}/turns",
            json={"role": role, "content": redact_pii(content)[:4000]},
        )

    async def finish(self, outcome: str, summary: str) -> None:
        if not self.call_id:
            return
        await self._request(
            "POST",
            f"{self.api_prefix}/internal/calls/{self.call_id}/finish",
            json={"outcome": normalize_outcome(outcome), "summary": summary[:4000]},
        )


def build_tools(api: ControlPlaneClient, state: CallState, session: Any) -> list[Any]:
    """Create the tool set for one call. ``session`` is the LiveKit AgentSession."""

    @function_tool
    async def check_availability(date: str, service: str = "") -> str:
        """Check available appointment times.

        Args:
            date: Date in YYYY-MM-DD format.
            service: Optional service name to size the appointment.
        """
        try:
            slots = await api.availability(date, service)
        except ControlPlaneError as exc:
            return f"I couldn't check the calendar right now ({exc}). Try again in a moment."
        offered = state.offered.offer(slots)
        if not offered:
            return "There are no open times that day. Ask if another day works."
        readable = [slot.replace("T", " ")[:16] for slot in offered[:6]]
        return "Available times: " + "; ".join(readable)

    @function_tool
    async def book_appointment(
        starts_at: str,
        service: str,
        contact_name: str,
        contact_phone: str,
    ) -> str:
        """Book an appointment the caller has confirmed.

        Args:
            starts_at: ISO timestamp previously offered by check_availability.
            service: Service name.
            contact_name: Caller's full name.
            contact_phone: Caller's phone number including country code.
        """
        if not state.offered.take(starts_at):
            return "That time was not offered in this call. Check availability again first."
        try:
            booking = await api.book(starts_at, service, contact_name, contact_phone)
        except ControlPlaneError as exc:
            if "409" in str(exc):
                return (
                    "That time was just taken. Offer the next alternatives from check_availability."
                )
            return f"I couldn't complete the booking ({exc}). Take a message instead."
        state.summary = f"Booked {service} at {starts_at} for {contact_name}."
        return (
            f"Booked {service} for {starts_at}. Booking link: {booking.get('booking_url', '')}. "
            "Confirm the date and time with the caller."
        )

    @function_tool
    async def lookup_knowledge(query: str) -> str:
        """Look up business facts such as hours, parking, insurance, or pricing.

        Args:
            query: What the caller asked about.
        """
        try:
            docs = await api.knowledge(query)
        except ControlPlaneError:
            return "I don't have that information. Offer to take a message."
        if not docs:
            return "No matching knowledge. Do not guess; take a message or transfer."
        return " | ".join(f"{doc.get('title')}: {doc.get('content')}" for doc in docs)[:1200]

    @function_tool
    async def take_message(message: str, callback_number: str = "") -> str:
        """Record a message for the team when the request cannot be resolved.

        Args:
            message: Caller's message.
            callback_number: Optional callback number.
        """
        state.summary = f"Message: {message} Callback: {callback_number}"
        state.outcome = "message_taken"
        await api.log_turn("user", message)
        return "Message recorded. The team will follow up during business hours."

    @function_tool
    async def transfer_call(reason: str) -> str:
        """Transfer to a human with a warm summary.

        Args:
            reason: One-line reason for the transfer.
        """
        state.outcome = "transferred"
        state.summary = f"Transferred: {reason}"
        return f"Transferring you to a team member. Reason: {reason}"

    @function_tool
    async def end_call(outcome: str, summary: str = "") -> str:
        """End the call and persist the outcome.

        Args:
            outcome: One of: OUTCOMES.
            summary: Short call summary.
        """
        normalized = normalize_outcome(outcome)
        if not normalized:
            return f"Invalid outcome. Use one of: {', '.join(OUTCOMES)}."
        state.ended = True
        state.outcome = normalized
        state.summary = summary or state.summary
        with suppress(Exception):
            await api.finish(normalized, state.summary)
        shutdown = getattr(session, "shutdown", None) or getattr(session, "aclose", None)
        if shutdown is not None:
            with suppress(Exception):
                await shutdown()
        return "Call complete."

    return [
        check_availability,
        book_appointment,
        lookup_knowledge,
        take_message,
        transfer_call,
        end_call,
    ]
