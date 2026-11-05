from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select

from app.db import SessionLocal
from app.domain.outcomes import PROTECTED_STATUSES
from app.models import Call
from app.pipeline.nodes import (
    node_classify,
    node_done,
    node_extract,
    node_load,
    node_persist,
    node_summarise,
    node_translate,
    node_upsert_patient,
    node_validate,
)

logger = logging.getLogger(__name__)


class PipelineState(TypedDict, total=False):
    call_id: str


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("load_call", node_load)
    graph.add_node("extract", node_extract)
    graph.add_node("validate_normalise", node_validate)
    graph.add_node("upsert_patient", node_upsert_patient)
    graph.add_node("persist_extraction", node_persist)
    graph.add_node("classify_status", node_classify)
    graph.add_node("summarise", node_summarise)
    graph.add_node("translate_turns", node_translate)
    graph.add_node("done", node_done)
    graph.set_entry_point("load_call")
    graph.add_edge("load_call", "extract")
    graph.add_edge("extract", "validate_normalise")
    graph.add_edge("validate_normalise", "upsert_patient")
    graph.add_edge("upsert_patient", "persist_extraction")
    graph.add_edge("persist_extraction", "classify_status")
    graph.add_edge("classify_status", "summarise")
    graph.add_edge("summarise", "translate_turns")
    graph.add_edge("translate_turns", "done")
    graph.add_edge("done", END)
    return graph.compile()


async def _claim(call_id: uuid.UUID) -> bool:
    async with SessionLocal() as session:
        call = await session.scalar(select(Call).where(Call.id == call_id).with_for_update())
        if call is None:
            return False
        if call.pipeline_status == "done":
            return False
        if call.pipeline_status == "running":
            ended = call.ended_at
            if ended is not None and datetime.now(UTC) - ended < timedelta(minutes=3):
                return False
        call.pipeline_status = "running"
        await session.commit()
        return True


async def _release_failure(call_id: uuid.UUID, reason: str, *, final: bool) -> None:
    async with SessionLocal() as session:
        call = await session.get(Call, call_id)
        if call is None or call.pipeline_status == "done":
            return
        call.pipeline_status = "failed"
        call.error_reason = reason[:500]
        if final and call.status not in PROTECTED_STATUSES:
            call.status = "failed"
        await session.commit()


async def run_pipeline(call_id: uuid.UUID) -> None:
    if not await _claim(call_id):
        logger.info("pipeline skip call %s", call_id)
        return
    graph = build_graph()
    delay = 1.0
    last_error = "pipeline_failed"
    for attempt in range(3):
        try:
            await graph.ainvoke({"call_id": str(call_id)})
            logger.info("pipeline done call %s", call_id)
            return
        except Exception as exc:
            last_error = f"pipeline: {exc}"
            logger.exception("pipeline attempt %s failed for %s", attempt + 1, call_id)
            await _release_failure(call_id, last_error, final=False)
            await asyncio.sleep(delay)
            delay *= 2
            await _claim(call_id)
    await _release_failure(call_id, last_error, final=True)
