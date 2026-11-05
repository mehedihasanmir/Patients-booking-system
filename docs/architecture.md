# Architecture

```mermaid
flowchart LR
  browser[Browser]
  web[Next.js on Vercel]
  api[FastAPI on Railway]
  livekit[LiveKit Cloud]
  agent[Nusrat worker on Railway]
  graph[LangGraph]
  neon[(Neon Postgres Singapore)]
  r2[Cloudflare R2 optional]

  browser --> web
  web --> api
  browser --> livekit
  livekit --> agent
  agent --> api
  api --> graph
  graph --> neon
  api --> neon
  web --> neon
  livekit --> r2
  api --> r2
```

The browser never holds LiveKit API secrets. It asks `POST /api/livekit/token`. FastAPI creates a `calls` row, names the room `call-<uuid>`, and returns a participant token that dispatches the worker named `bytevoice` with `{ "call_id" }` in the job metadata.

Nusrat stays on the speech path only: OpenAI `gpt-4o-mini-transcribe` for Bangla speech and OpenAI `gpt-4o-mini-tts` (`coral`) for the reply (Google if configured as fallback), gpt-4o-mini, Silero, and the multilingual turn detector. Tools call FastAPI with `X-Service-Token`. The model is not allowed to invent hours, fees, or open slots; those answers come from Postgres.

When the room ends, the worker posts `/internal/calls/{id}/end`. FastAPI answers immediately and runs LangGraph after the response: load, extract, validate, upsert patient, persist, classify, summarise, translate turns. A verified LiveKit `room_finished` webhook runs the same job if the worker died first. The job is idempotent on `call_id`.

The portal is a Next.js route group. It keeps the JWT in an httpOnly cookie and forwards it to FastAPI. Staff edits write `audit_log`.

Recordings are optional. If R2 is off, egress is skipped and the portal simply has no audio player. The transcript still lands.
