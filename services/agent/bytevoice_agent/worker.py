from __future__ import annotations

import inspect
import json
import logging
from typing import Any

from livekit import agents
from livekit.agents import AgentSession, JobContext, JobProcess, WorkerOptions, cli
from livekit.plugins import openai, silero

from bytevoice_agent.client import ApiClient
from bytevoice_agent.config import get_settings
from bytevoice_agent.nusrat import CallRuntime, Nusrat, bind_session

logger = logging.getLogger("bytevoice.agent")


def _load_vad():
    wanted = {
        "min_speech_duration": 0.25,
        "min_silence_duration": 0.55,
        "activation_threshold": 0.6,
    }
    params = inspect.signature(silero.VAD.load).parameters
    return silero.VAD.load(**{key: value for key, value in wanted.items() if key in params})


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = _load_vad()


def _try(factory, variants: list[dict[str, Any]]):
    last: Exception | None = None
    for kwargs in variants:
        try:
            return factory(**{key: value for key, value in kwargs.items() if value is not None})
        except TypeError as exc:
            last = exc
    if last:
        raise last
    raise RuntimeError("no constructor variant")


def _build_stt(settings):
    providers = []
    if settings.stt_provider in {"auto", "openai"}:
        model = settings.openai_stt_model or "gpt-4o-mini-transcribe"
        language = settings.openai_stt_language or "bn"
        providers.append(
            _try(
                openai.STT,
                [
                    {"model": model, "language": language},
                    {"model": "whisper-1", "language": language},
                ],
            )
        )
    if settings.stt_provider == "deepgram":
        from livekit.plugins import deepgram

        providers.append(deepgram.STT(model="nova-3", language="multi"))
    if settings.google_ready and settings.stt_provider in {"auto", "google"}:
        from livekit.plugins import google

        providers.append(_try(google.STT, [{"languages": ["bn-BD"]}, {"language": "bn-BD"}]))
    if not providers:
        raise RuntimeError("No STT provider configured")
    if len(providers) == 1:
        return providers[0]
    fallback = getattr(agents.stt, "FallbackAdapter", None)
    return fallback(providers) if fallback else providers[0]


_TTS_INSTRUCTIONS = (
    "Speak Bangla as spoken in Dhaka, Bangladesh. You are a warm female clinic receptionist. "
    "Clear, polite, and unhurried. Use natural Bangladeshi pronunciation, not Indian Hindi. "
    "Keep these English words in English: appointment, scaling, root canal, filling, braces, extraction, doctor, check-up."
)


def _build_tts(settings):
    providers = []
    if settings.tts_provider in {"auto", "openai"}:
        model = settings.openai_tts_model or "gpt-4o-mini-tts"
        voice = settings.openai_tts_voice or "coral"
        providers.append(
            _try(
                openai.TTS,
                [
                    {"model": model, "voice": voice, "instructions": _TTS_INSTRUCTIONS},
                    {"model": model, "voice": voice},
                ],
            )
        )
    if settings.google_ready and settings.tts_provider in {"auto", "google"}:
        from livekit.plugins import google

        providers.append(
            _try(
                google.TTS,
                [
                    {"language": "bn-BD", "voice_name": settings.google_tts_voice},
                    {"voice": settings.google_tts_voice},
                ],
            )
        )
    if not providers:
        raise RuntimeError("Set OPENAI_API_KEY or GOOGLE_APPLICATION_CREDENTIALS for Bangla TTS")
    if len(providers) == 1:
        return providers[0]
    fallback = getattr(agents.tts, "FallbackAdapter", None)
    return fallback(providers) if fallback else providers[0]


def _build_llm():
    kwargs: dict[str, Any] = {"model": "gpt-4o-mini", "temperature": 0.4}
    if "max_completion_tokens" in inspect.signature(openai.LLM.__init__).parameters:
        kwargs["max_completion_tokens"] = 180
    return openai.LLM(**kwargs)


def _session_kwargs(settings, proc: JobProcess) -> dict[str, Any]:
    wanted: dict[str, Any] = {
        "stt": _build_stt(settings),
        "llm": _build_llm(),
        "tts": _build_tts(settings),
        "vad": proc.userdata.get("vad") or _load_vad(),
        "allow_interruptions": True,
        "min_endpointing_delay": 0.35,
        "max_endpointing_delay": 1.2,
        "user_away_timeout": 6.0,
    }
    try:
        from livekit.plugins.turn_detector.multilingual import MultilingualModel

        wanted["turn_detection"] = MultilingualModel()
    except Exception:
        logger.warning("multilingual turn detector unavailable; using VAD endpointing")
    params = inspect.signature(AgentSession.__init__).parameters
    return {key: value for key, value in wanted.items() if key in params}


async def _ensure_call(ctx: JobContext, client: ApiClient) -> str:
    raw = getattr(ctx.job, "metadata", "") or ""
    if raw:
        try:
            parsed = json.loads(raw)
            if parsed.get("call_id"):
                return str(parsed["call_id"])
        except json.JSONDecodeError:
            logger.warning("bad job metadata")
    created = await client.post("/internal/calls", {"room": ctx.room.name or "console", "channel": "web"})
    return str(created["call_id"])


async def entrypoint(ctx: JobContext) -> None:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    await ctx.connect()
    client = ApiClient(settings.api_base_url, settings.service_token)
    call_id = await _ensure_call(ctx, client)
    agent = Nusrat(client, call_id)
    runtime = CallRuntime(client, call_id, agent)
    session = AgentSession(**_session_kwargs(settings, ctx.proc))
    runtime.session = session
    bind_session(session, runtime)

    async def shutdown() -> None:
        await runtime.finish()
        await client.aclose()

    ctx.add_shutdown_callback(shutdown)
    await session.start(room=ctx.room, agent=agent)
    try:
        await session.generate_reply(
            instructions="শুরুর সম্ভাষণ বলুন, সিস্টেম প্রম্পটের ঠিক সেই বাক্যটি। এর বেশি কিছু বলবেন না।"
        )
    finally:
        runtime.ready = True


def run() -> None:
    settings = get_settings()
    options = {
        "entrypoint_fnc": entrypoint,
        "prewarm_fnc": prewarm,
        "agent_name": settings.livekit_agent_name,
    }
    params = inspect.signature(WorkerOptions).parameters
    cli.run_app(WorkerOptions(**{key: value for key, value in options.items() if key in params}))


if __name__ == "__main__":
    run()
