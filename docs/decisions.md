# Decisions

## LiveKit for the call, not a telephone gateway

The demo has to be a browser call a reviewer can start from the landing page. LiveKit Cloud gives a room, a dispatched Python worker, barge-in, and a transcription stream without buying a Bangladesh number. SIP can be added later on the same worker.

## OpenAI STT for Bangla, Google bn-BD behind it

Deepgram is not available in every region, so the live transcript uses OpenAI `gpt-4o-mini-transcribe` with `language=bn` and the same `OPENAI_API_KEY` as the receptionist model. A short prompt tells it to keep English clinic words (scaling, root canal, appointment) in English. Google `bn-BD` is the fallback when a key exists, via LiveKit's `FallbackAdapter` when that class is present. It is not silently pretended to be on if `GOOGLE_APPLICATION_CREDENTIALS` is empty. `STT_PROVIDER=deepgram` still selects Nova-3, but that plugin is not installed by default.

## OpenAI TTS for the voice

The spoken reply uses OpenAI `gpt-4o-mini-tts` with the voice `coral` and the same `OPENAI_API_KEY` as the receptionist model. A short instruction asks for a warm female Dhaka accent and keeps English clinic words in English. OpenAI returns the whole clip before playback, so the first sound is a little later than a streaming voice. Google `bn-IN-Wavenet-A` is the fallback when Google credentials are present.

## gpt-4o-mini on the live path, with a short cap

The live model is gpt-4o-mini at temperature 0.4. When the plugin accepts it, `max_completion_tokens` is 180. The prompt tells Nusrat to stay inside two short sentences and one question. Tool descriptions stay in English so tool calling stays reliable. The spoken policy is Bangla.

## LangGraph only after hangup

A graph inside the call would add a round trip before she can speak. Booking, cancel, and callback already write rows during the call through tools. LangGraph's job is the slower one: structured extraction, Bangla digit and date checks, summaries, and English lines for the transcript toggle. If the model key is missing, a deterministic fallback still classifies the call from the rows the tools wrote, and marks low confidence for review.

## Neon in Singapore, Railway for Python, Vercel for Next

`ap-southeast-1` is the closest Neon region to Dhaka. Railway runs two processes that both need Python and long-lived connections: the API and the agent worker. Vercel runs the Next.js app. The pipeline runs inside the API process. That is a demo choice, not a queue.

## Validation before the model is trusted

Bangla digits, the `^01[3-9]\d{8}$` mobile rule, Friday, holidays, opening hours, and past times are Python functions with tests. The model proposes a phrase ("আগামী রবিবার সন্ধ্যায়"). The API resolves it in `Asia/Dhaka` and returns `say_bn` plus a `slot_start_iso`. Nusrat is told to copy that timestamp, not invent one.

## A successful booking is not overwritten by a summary failure

If the tool already booked and the summary model later fails, the call stays `booked` and `error_reason` explains the partial failure. An urgent callback (bleeding, swelling with fever, trauma, trouble breathing) does outrank a booking, because the caller was told to go to emergency.
