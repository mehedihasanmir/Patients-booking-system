from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import time
from typing import Any

from livekit.agents import Agent, AgentSession, JobContext, RunContext, function_tool, stt

from bytevoice_agent.client import ApiClient, tool_failure
from bytevoice_agent.prompt import SYSTEM_PROMPT

logger = logging.getLogger("bytevoice.agent")
_BN = re.compile(r"[\u0980-\u09FF]")
_LATIN = re.compile(r"[A-Za-z]")


def looks_mixed(text: str) -> bool:
    return bool(_BN.search(text) and _LATIN.search(text))


def _state(value: Any) -> str:
    raw = getattr(value, "value", str(value))
    return str(raw).split(".")[-1].lower()


def _accepts(fn: Any, name: str) -> bool:
    try:
        return name in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


async def _reply(session: AgentSession, instructions: str, interruptions: bool = True) -> None:
    kwargs: dict[str, Any] = {"instructions": instructions}
    if _accepts(session.generate_reply, "allow_interruptions"):
        kwargs["allow_interruptions"] = interruptions
    await session.generate_reply(**kwargs)


def _shutdown(session: AgentSession) -> None:
    try:
        session.shutdown(drain=True)  # type: ignore[call-arg]
    except TypeError:
        session.shutdown()


class Nusrat(Agent):
    def __init__(self, client: ApiClient, call_id: str) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self.client = client
        self.call_id = call_id
        self.confidences: list[tuple[str, float | None]] = []

    async def stt_node(self, audio, model_settings):  # type: ignore[override]
        async for event in Agent.default.stt_node(self, audio, model_settings):
            if getattr(event, "type", None) == stt.SpeechEventType.FINAL_TRANSCRIPT:
                alternatives = getattr(event, "alternatives", None) or []
                if alternatives:
                    alt = alternatives[0]
                    self.confidences.append((getattr(alt, "text", ""), getattr(alt, "confidence", None)))
                    self.confidences = self.confidences[-8:]
            yield event

    async def _tool(self, path: str, payload: dict) -> str:
        try:
            data = await self.client.post(path, payload)
        except Exception:
            return tool_failure("সিস্টেমে একটু সমস্যা হচ্ছে। আমি কি কলব্যাক লিখে রাখব?")
        return json.dumps(data, ensure_ascii=False)

    @function_tool
    async def get_clinic_info(self, topic: str) -> str:
        """Look up clinic facts. topic: hours, location, services, fees, doctors, preparation, about."""
        return await self._tool("/internal/tools/clinic-info", {"topic": topic})

    @function_tool
    async def check_availability(self, date_text: str, time_pref: str = "", doctor: str = "", service: str = "") -> str:
        """Find up to two free slots. Pass the caller's words, not a calculated date."""
        return await self._tool(
            "/internal/tools/availability",
            {"date_text": date_text, "time_pref": time_pref, "doctor": doctor, "service": service},
        )

    @function_tool
    async def book_appointment(
        self,
        full_name_bn: str,
        phone: str,
        slot_start_iso: str,
        doctor_id: str,
        reason: str = "",
        full_name_en: str = "",
        service: str = "",
        service_id: str = "",
    ) -> str:
        """Book only after the caller confirms the summary. Copy slot_start_iso and doctor_id from check_availability."""
        return await self._tool(
            "/internal/tools/book",
            {
                "call_id": self.call_id,
                "full_name_bn": full_name_bn,
                "full_name_en": full_name_en,
                "phone": phone,
                "reason": reason,
                "slot_start_iso": slot_start_iso,
                "doctor_id": doctor_id,
                "service": service,
                "service_id": service_id,
            },
        )

    @function_tool
    async def find_appointments(self, phone: str) -> str:
        """Find upcoming appointments for a mobile number."""
        return await self._tool("/internal/tools/find", {"phone": phone})

    @function_tool
    async def reschedule_appointment(self, appointment_id: str, slot_start_iso: str, doctor_id: str = "") -> str:
        """Move an existing appointment onto a slot copied from check_availability."""
        return await self._tool(
            "/internal/tools/reschedule",
            {
                "call_id": self.call_id,
                "appointment_id": appointment_id,
                "slot_start_iso": slot_start_iso,
                "doctor_id": doctor_id,
            },
        )

    @function_tool
    async def cancel_appointment(self, appointment_id: str, reason: str = "") -> str:
        """Cancel an appointment found with find_appointments."""
        return await self._tool(
            "/internal/tools/cancel",
            {"call_id": self.call_id, "appointment_id": appointment_id, "reason": reason},
        )

    @function_tool
    async def request_callback(self, reason: str, phone: str = "", full_name_bn: str = "", urgency: str = "normal") -> str:
        """Log a human callback. urgency is normal or urgent."""
        return await self._tool(
            "/internal/tools/callback",
            {
                "call_id": self.call_id,
                "reason": reason,
                "phone": phone,
                "full_name_bn": full_name_bn,
                "urgency": "urgent" if urgency == "urgent" else "normal",
            },
        )

    @function_tool
    async def end_call(self, context: RunContext) -> str:
        """End the call after the goodbye has been spoken."""
        _shutdown(context.session)
        return json.dumps({"ok": True, "say_bn": ""}, ensure_ascii=False)


class CallRuntime:
    def __init__(self, client: ApiClient, call_id: str, agent: Nusrat) -> None:
        self.client = client
        self.call_id = call_id
        self.agent = agent
        self.origin = time.monotonic()
        self.seq = 0
        self.lock = asyncio.Lock()
        self.ready = False
        self.incomplete = False
        self.silence_hits = 0
        self.closing = False
        self.user_stopped: float | None = None
        self.speech_at = {"caller": 0, "agent": 0}
        self.session: AgentSession | None = None

    def now_ms(self) -> int:
        return int((time.monotonic() - self.origin) * 1000)

    def confidence_for(self, text: str) -> float | None:
        cleaned = text.strip()
        for heard, score in reversed(self.agent.confidences):
            if heard.strip() == cleaned:
                return score
        if self.agent.confidences:
            return self.agent.confidences[-1][1]
        return None

    async def post_turn(self, speaker: str, text: str, confidence: float | None) -> None:
        cleaned = " ".join(text.split())
        if not cleaned:
            return
        async with self.lock:
            self.seq += 1
            seq = self.seq
            end = self.now_ms()
            start = self.speech_at.get(speaker, end)
        try:
            await self.client.post(
                f"/internal/calls/{self.call_id}/turns",
                {
                    "seq": seq,
                    "speaker": speaker,
                    "text": cleaned,
                    "started_ms": min(start, end),
                    "ended_ms": end,
                    "stt_confidence": confidence,
                    "language_mix": looks_mixed(cleaned),
                },
            )
        except Exception:
            logger.exception("failed to store turn %s", seq)

    async def finish(self) -> None:
        try:
            await self.client.post(
                f"/internal/calls/{self.call_id}/end",
                {"incomplete": self.incomplete, "reason": "silence" if self.incomplete else None},
            )
        except Exception:
            logger.exception("failed to end call %s", self.call_id)

    async def on_silence(self) -> None:
        if not self.ready or self.closing or self.session is None:
            return
        async with self.lock:
            if self.closing:
                return
            self.silence_hits += 1
            hit = self.silence_hits
        if hit == 1:
            await _reply(self.session, "শুধু এই বাক্যটি বলুন: আপনি কি আমাকে শুনতে পাচ্ছেন?")
        elif hit == 2:
            await _reply(self.session, "শুধু এই বাক্যটি বলুন: আমি কি আপনাকে শুনতে পাচ্ছি? একটু পরে আবার বলবেন।")
        else:
            self.closing = True
            self.incomplete = True
            await _reply(
                self.session,
                "শুধু এই কথা বলুন: মনে হচ্ছে লাইনটা চুপ হয়ে আছে। আমি এখন শেষ করছি। আল্লাহ হাফেজ।",
                interruptions=False,
            )
            await asyncio.sleep(5)
            _shutdown(self.session)


def bind_session(session: AgentSession, runtime: CallRuntime) -> None:
    @session.on("user_input_transcribed")
    def on_user(ev) -> None:  # type: ignore[no-untyped-def]
        if not getattr(ev, "is_final", False):
            return
        text = getattr(ev, "transcript", "") or ""
        asyncio.create_task(runtime.post_turn("caller", text, runtime.confidence_for(text)))

    @session.on("conversation_item_added")
    def on_item(ev) -> None:  # type: ignore[no-untyped-def]
        item = getattr(ev, "item", None)
        role = getattr(item, "role", "")
        if role not in {"assistant", "agent"}:
            return
        text = getattr(item, "text_content", None) or getattr(item, "text", "") or ""
        asyncio.create_task(runtime.post_turn("agent", text, None))

    @session.on("user_state_changed")
    def on_user_state(ev) -> None:  # type: ignore[no-untyped-def]
        new = _state(getattr(ev, "new_state", ""))
        old = _state(getattr(ev, "old_state", ""))
        if new == "speaking":
            runtime.silence_hits = 0
            runtime.speech_at["caller"] = runtime.now_ms()
        if old == "speaking" and new != "speaking":
            runtime.user_stopped = time.perf_counter()
        if new == "away":
            asyncio.create_task(runtime.on_silence())

    @session.on("agent_state_changed")
    def on_agent_state(ev) -> None:  # type: ignore[no-untyped-def]
        new = _state(getattr(ev, "new_state", ""))
        if new == "speaking":
            runtime.speech_at["agent"] = runtime.now_ms()
            if runtime.user_stopped is not None:
                elapsed = round((time.perf_counter() - runtime.user_stopped) * 1000)
                logger.info("voice_to_voice_ms=%s call_id=%s", elapsed, runtime.call_id)
                runtime.user_stopped = None
