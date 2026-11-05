# Schema

ByteVoice stores one demo clinic, StrategyByte Dental Care. Primary keys are UUIDs. Timestamps are `timestamptz` and the clinic clock is `Asia/Dhaka`.

`calls.status` is the business outcome. `calls.pipeline_status` (`pending`, `running`, `done`, `failed`) is only there so the post-call job can run once. `transcript_turns.language_mix` records Bangla–English code-switching, which the live capture step asked for and the original column list did not name.

Active appointments (`booked`, `rescheduled`) cannot overlap for the same doctor. Postgres enforces that with a `btree_gist` exclusion constraint on `tstzrange(slot_start, slot_end)`.

```mermaid
erDiagram
  clinics ||--o{ doctors : employs
  clinics ||--o{ services : offers
  clinics ||--o{ patients : registers
  clinics ||--o{ calls : receives
  clinics ||--o{ holidays : closes
  clinics ||--o{ appointments : hosts
  patients ||--o{ calls : places
  patients ||--o{ appointments : attends
  patients ||--o{ callbacks : needs
  doctors ||--o{ appointments : sees
  services ||--o{ appointments : covers
  calls ||--o{ transcript_turns : contains
  calls ||--o| call_extractions : yields
  calls ||--o{ appointments : books
  calls ||--o{ callbacks : requests
  doctors ||--o{ call_extractions : requested
  users ||--o{ audit_log : writes

  clinics {
    uuid id PK
    text name_bn
    text name_en
    text address
    text directions_bn
    text directions_en
    text phone
    text timezone
    jsonb opening_hours
  }
  doctors {
    uuid id PK
    uuid clinic_id FK
    text name_bn
    text name_en
    text specialty
    bool active
  }
  services {
    uuid id PK
    uuid clinic_id FK
    int duration_min
    int fee_min_bdt
    int fee_max_bdt
    text prep_notes
  }
  patients {
    uuid id PK
    uuid clinic_id FK
    text full_name_bn
    text full_name_en
    text phone_e164
  }
  calls {
    uuid id PK
    uuid patient_id FK
    text livekit_room
    text status
    text pipeline_status
    text summary_bn
    text summary_en
    text recording_url
  }
  transcript_turns {
    uuid id PK
    uuid call_id FK
    int seq
    text speaker
    text text_bn
    text text_en
    int started_ms
    float stt_confidence
    bool language_mix
  }
  call_extractions {
    uuid call_id PK
    text intent
    text reason_for_visit
    date preferred_date
    text preferred_time_window
    uuid requested_doctor_id FK
    jsonb field_confidence
    bool needs_review
  }
  appointments {
    uuid id PK
    uuid doctor_id FK
    uuid patient_id FK
    timestamptz slot_start
    timestamptz slot_end
    text status
  }
  callbacks {
    uuid id PK
    text urgency
    text status
  }
```

Indexes: `calls(started_at)`, `calls(status)`, `patients(phone_e164)`, `appointments(doctor_id, slot_start)`, plus unique `(clinic_id, phone_e164)` and `(call_id, seq)`.

Phone numbers are stored as E.164 (`+8801XXXXXXXXX`). The spoken form groups the local number as `০১৭১২-৩৪৫-৬৭৮`. Each extracted field in `field_confidence` looks like `{ "confidence": 0.9, "source_turn_seq": 4 }`. Anything under 0.65, or a phone/date that fails validation, sets `needs_review`.
