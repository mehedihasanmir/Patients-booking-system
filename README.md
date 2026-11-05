# ByteVoice Bangla

A Bangla receptionist for dental clinics and hospital front desks in Bangladesh. The demo clinic is **StrategyByte Dental Care**, House 42, Road 7, Dhanmondi, Dhaka. The caller is **Nusrat**. She books, moves, and cancels appointments, answers clinic questions from the clinic record, and never gives medical advice.

A reviewer opens the landing page, presses the hero button, books a dental appointment in Bangla, hangs up, then signs into the portal and sees that call, its transcript, and the patient.

## Try it

| | |
| --- | --- |
| Landing, Bangla | https://patients-booking-system.vercel.app/bn |
| Landing, English | https://patients-booking-system.vercel.app/en |
| Portal | https://patients-booking-system.vercel.app/bn/portal/login |
| API health | https://perfect-fascination-production-f1f9.up.railway.app/health |
| Repository | https://github.com/mehedihasanmir/Patients-booking-system |

The hero button says **আমাদের বাংলা কলারের সাথে কথা বলুন**. In English it says **Talk to our Bangla caller**. Allow the microphone. The chip on Nusrat turns to **লাইভ** and a timer starts when she has joined the room. Her first line can take a few seconds: OpenAI speech is a whole clip, not a stream. After you hang up, wait about a minute, then open the portal. The new row is that call.

Say something like: your name, `০১৭১২৩৪৫৬৭৮`, a toothache, and next Sunday evening. She should read the number back and ask you to confirm before the seat is saved. Friday, after 8pm, and past times are refused in Bangla.

### Reviewer login

These accounts exist only for this demo. The patients in the portal are fake.

| Role | Email | Password |
| --- | --- | --- |
| admin | `reviewer@strategybyte.demo` | `ReviewerDemo!2026` |
| staff | `staff@strategybyte.demo` | `StaffDemo!2026` |

In the portal, open **Calls** for the list (search, duration, status), a call for the extracted fields and the timestamped transcript, and **Data model** for how a call moves from the browser into Postgres.

## What one call does

```mermaid
flowchart LR
  browser[Browser] --> web[Next.js on Vercel]
  web --> api[FastAPI on Railway]
  browser --> livekit[LiveKit Cloud]
  livekit --> nusrat[Nusrat on Railway]
  nusrat --> api
  api --> neon[(Neon Postgres Singapore)]
  api --> graph[LangGraph after hangup]
  graph --> neon
```

1. The hero button asks for the microphone, then the Next.js server calls `POST /api/livekit/token`. The browser never sees the LiveKit secret. Five token requests per minute per IP.
2. FastAPI inserts a `calls` row, names the room `call-<uuid>`, and returns a token that dispatches the worker `bytevoice` with `{ "call_id" }` in the job metadata.
3. Nusrat greets, asks one question at a time, and uses tools for hours, slots, booking, reschedule, cancel, and callbacks. Clinic facts come from Postgres. She copies `slot_start_iso` from the tool. The API checks that slot again before insert.
4. Each finished turn is posted to `POST /internal/calls/{id}/turns` with `X-Service-Token`.
5. Hangup calls `POST /internal/calls/{id}/end`. LangGraph then extracts, validates, summarises, and translates. A signed LiveKit `room_finished` webhook at `/webhooks/livekit` runs the same job if the worker dies first. A bad signature is rejected.
6. The portal reads the same Postgres rows: status, patient, appointment, Bangla and English transcript.

Statuses you can filter: `booked`, `rescheduled`, `cancelled`, `enquiry`, `follow_up_needed`, `incomplete`, `failed`. An urgent callback (bleeding, trouble breathing) outranks a booking, because she has already told the caller to go to emergency.

## What is stored

One clinic. UUIDs. Timestamps in UTC, clinic clock `Asia/Dhaka`. The picture is in [docs/schema.md](docs/schema.md).

| Table | What it is for |
| --- | --- |
| `calls` | One row per call: start, end, duration, status, room, pipeline state |
| `patients` | The person. Bangla name, English name, phone as `+8801XXXXXXXXX` |
| `call_extractions` | Reason, preferred date and time, intent, per-field confidence, `needs_review` |
| `transcript_turns` | Speaker, Bangla, English, offset in the call |
| `appointments` | Doctor, 30-minute slot, status. Two active bookings on the same doctor and slot cannot both commit |
| `callbacks` | Normal or urgent follow-up for the front desk |

Bangla digits `০-৯` become `0-9`. A mobile number must match `^01[3-9]\d{8}$`. `আগামী রবিবার`, `পরশু সকালে`, `next Sunday evening`, and `রাত ৭টা` resolve in `Asia/Dhaka`. Friday, holidays, past times, and anything outside 10:00–20:00 are rejected with a Bangla sentence she can say. Confidence under 0.65, or a field that fails those rules, flags the call for review. These checks are plain functions in `services/api/app/domain`, with pytest, and they do not import the database.

## Why this shape

| Piece | Choice | Why |
| --- | --- | --- |
| Media | LiveKit Cloud | A reviewer can talk from the browser. Barge-in and agent dispatch are included. No Bangladesh number is required for the demo. |
| Speech to text | OpenAI `gpt-4o-mini-transcribe`, `language=bn` | Deepgram cannot be created from this region. The transcriber is not given an instruction prompt: on a quiet line it was repeating that prompt as the caller's words. |
| Speech | OpenAI `gpt-4o-mini-tts`, voice `coral` | Same API key. She is instructed to sound like a woman speaking Dhaka Bangla, and to keep words such as scaling and root canal in English. The clip is not streamed, so the first syllable is later than a streaming voice. |
| Live replies | gpt-4o-mini, temperature 0.4, about 180 tokens | Short enough for a phone turn. Tool descriptions stay in English so the tool call is reliable. She speaks Bangla. |
| After hangup | LangGraph inside the API | Extraction and translation are slow. They must not sit in front of her reply. If the summary later fails, a booking already saved stays `booked`. |
| Database | Neon Postgres, AWS Singapore | Closest managed region to Dhaka. |
| API and worker | Two Railway services, one replica each | Both are long-running Python. The worker has no public site. If it sleeps, the hero call ends at 10 seconds. |
| Site | Vercel, root `apps/web` | Landing and portal are one Next.js app. `API_URL` is server-only. |

Longer notes are in [docs/decisions.md](docs/decisions.md) and [docs/architecture.md](docs/architecture.md).

Silence is handled in the worker, not by asking the transcriber to ignore noise. Silero requires about a quarter-second of speech and a higher activation threshold (`0.6`) before a clip is sent. The worker logs `voice_to_voice_ms` from the moment the caller stops to the moment Nusrat starts. That number is a measurement, not a promise. Cold start and the non-streaming voice can miss a 1.2 second target.

## Repository

```
apps/web            Next.js landing and portal, Bangla and English
services/api        FastAPI, Alembic, LangGraph
services/agent      LiveKit worker, Nusrat
packages/shared     TypeScript types for the portal
docs                architecture, schema, decisions
```

The voice worker does not import FastAPI. It calls it. The portal does not open Postgres. It sends the reviewer's httpOnly cookie through the Next.js server.

## Local setup

Python 3.11+, Node 20+, and Docker for Postgres only.

```bash
docker compose up -d db
cp services/api/.env.example services/api/.env
cp services/agent/.env.example services/agent/.env
cp apps/web/.env.example apps/web/.env.local

cd services/api
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000

cd apps/web
npm install
npm run dev

cd services/agent
python -m venv .venv
pip install -e .
python main.py download-files
python main.py dev
```

`python main.py dev` must be stopped before you judge the deployed caller. LiveKit will otherwise hand some calls to the laptop. Tests that do not need Postgres:

```bash
cd services/api && python -m pytest
```

Local landing: `http://localhost:3000/bn`. If port 3000 is taken, Next prints the port it actually bound. The browser still talks to the Next server, not to port 8000 directly.

## Environment

Filled `.env` files are gitignored. Production refuses a `JWT_SECRET` or `SERVICE_TOKEN` that starts with `dev-`.

The API on Railway needs `APP_ENV=production`, a Neon `DATABASE_URL` beginning `postgresql+asyncpg://` and ending `?ssl=require`, the LiveKit URL, key, and secret, `LIVEKIT_AGENT_NAME=bytevoice`, `OPENAI_API_KEY`, and `CORS_ORIGINS` set to `https://patients-booking-system.vercel.app`. `SEED_ON_START=true` loads the clinic, the two users above, and sample calls only when the calls table is empty. `R2_ENABLED=false`. There is no recording until a bucket is configured. The transcript is the record.

The worker needs the same LiveKit project, `API_BASE_URL=https://perfect-fascination-production-f1f9.up.railway.app` with no trailing slash, the same `SERVICE_TOKEN`, and `OPENAI_API_KEY`. `STT_PROVIDER` and `TTS_PROVIDER` are `openai`. `GOOGLE_APPLICATION_CREDENTIALS` is unset. Setting it without a real service-account file crashes the job before she can speak.

Vercel has one variable, `API_URL`, the same Railway origin with no trailing slash. Changing it requires a redeploy. The value is read when the site is built.

LiveKit's webhook is `https://perfect-fascination-production-f1f9.up.railway.app/webhooks/livekit`, signed with the same API key the Railway API holds.

## Known limits

- The call is in the browser. There is no Bangladesh phone number and no SIP trunk.
- No call recording in this deployment. `recording_url` stays empty.
- OpenAI speech is not streamed, so the first reply is slower than a streaming voice.
- A cough can still be transcribed. The threshold reduces that. It does not make the transcriber a person.
- The rate limit is in the API process. A second replica would not share it.
- LangGraph runs inside the API process. A job left in `running` can be retried after a few minutes.
- One clinic. No clinic switcher.
- English transcript lines depend on gpt-4o-mini. The Bangla line is what she and the caller said.
- Seeded patients are fake. Do not put a real patient in this demo.
- An in-call emergency is a script and an urgent callback, not a clinical protocol.

## Not in this demo

A PSTN number, a WhatsApp confirmation, a reminder call the day before, a real patient-record system, and a separate queue for the post-call graph.
