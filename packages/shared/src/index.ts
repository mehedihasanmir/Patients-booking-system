export type CallStatus =
  | "booked"
  | "rescheduled"
  | "cancelled"
  | "enquiry"
  | "follow_up_needed"
  | "incomplete"
  | "failed"
  | "in_progress";

export type AppointmentStatus = "booked" | "rescheduled" | "cancelled" | "completed";

export type Speaker = "agent" | "caller";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface CallListItem {
  id: string;
  started_at: string;
  ended_at: string | null;
  duration_s: number | null;
  status: CallStatus;
  caller_name: string | null;
  caller_name_en: string | null;
  phone: string | null;
  summary_bn: string | null;
  needs_review: boolean;
}

export interface TranscriptTurn {
  id: string;
  seq: number;
  speaker: Speaker;
  text_bn: string;
  text_en: string | null;
  started_ms: number;
  ended_ms: number;
  stt_confidence: number | null;
  language_mix: boolean;
}

export interface FieldConfidence {
  confidence: number;
  source_turn_seq: number | null;
  source?: string;
}

export interface CallDetail {
  id: string;
  status: CallStatus;
  pipeline_status: string;
  channel: string;
  started_at: string;
  ended_at: string | null;
  duration_s: number | null;
  summary_bn: string | null;
  summary_en: string | null;
  recording_url: string | null;
  error_reason: string | null;
  livekit_room: string;
  patient: {
    id: string;
    full_name_bn: string;
    full_name_en: string;
    phone_e164: string;
  } | null;
  extraction: {
    intent: string | null;
    reason_for_visit: string | null;
    preferred_date: string | null;
    preferred_time_window: string | null;
    doctor_name_bn: string | null;
    doctor_name_en: string | null;
    field_confidence: Record<string, FieldConfidence>;
    needs_review: boolean;
    raw_json: unknown;
    full_name_bn: string;
    full_name_en: string;
    phone: string;
  } | null;
  appointment: {
    id: string;
    status: AppointmentStatus;
    slot_start: string;
    slot_end: string;
    doctor_name_bn: string;
    doctor_name_en: string;
    service_name_bn: string | null;
    service_name_en: string | null;
    label_bn: string;
    label_en: string;
  } | null;
  turns: TranscriptTurn[];
}

export interface Stats {
  total_calls: number;
  booked_percent: number;
  avg_duration_s: number;
  open_callbacks: number;
  status_breakdown: Record<string, number>;
  calls_per_day: { date: string; count: number }[];
}

export interface PortalUser {
  id: string;
  email: string;
  role: "admin" | "staff";
}

export interface LiveKitToken {
  token: string;
  url: string;
  room: string;
  call_id: string;
}
