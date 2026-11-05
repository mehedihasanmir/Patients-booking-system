"""Initial ByteVoice schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "clinics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name_bn", sa.String(200), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("directions_bn", sa.Text(), nullable=False, server_default=""),
        sa.Column("directions_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Dhaka"),
        sa.Column("opening_hours", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "doctors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("name_bn", sa.String(200), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=False),
        sa.Column("specialty", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("name_bn", sa.String(200), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("fee_min_bdt", sa.Integer(), nullable=False),
        sa.Column("fee_max_bdt", sa.Integer(), nullable=False),
        sa.Column("prep_notes", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("full_name_bn", sa.String(200), nullable=False, server_default=""),
        sa.Column("full_name_en", sa.String(200), nullable=False, server_default=""),
        sa.Column("phone_e164", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("clinic_id", "phone_e164", name="uq_patients_clinic_phone"),
    )
    op.create_index("ix_patients_phone", "patients", ["phone_e164"])
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role in ('admin', 'staff')", name="ck_users_role"),
    )
    op.create_table(
        "calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=True),
        sa.Column("livekit_room", sa.String(120), nullable=False, unique=True),
        sa.Column("channel", sa.String(16), nullable=False, server_default="web"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="in_progress"),
        sa.Column("pipeline_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("summary_bn", sa.Text(), nullable=True),
        sa.Column("summary_en", sa.Text(), nullable=True),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("error_reason", sa.Text(), nullable=True),
        sa.Column("incomplete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint(
            "status in ('booked','rescheduled','cancelled','enquiry','follow_up_needed','incomplete','failed','in_progress')",
            name="ck_calls_status",
        ),
    )
    op.create_index("ix_calls_started_at", "calls", ["started_at"])
    op.create_index("ix_calls_status", "calls", ["status"])
    op.create_table(
        "transcript_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(16), nullable=False),
        sa.Column("text_bn", sa.Text(), nullable=False),
        sa.Column("text_en", sa.Text(), nullable=True),
        sa.Column("started_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ended_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stt_confidence", sa.Float(), nullable=True),
        sa.Column("language_mix", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("call_id", "seq", name="uq_turns_call_seq"),
        sa.CheckConstraint("speaker in ('agent','caller')", name="ck_turns_speaker"),
    )
    op.create_table(
        "call_extractions",
        sa.Column("call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("intent", sa.String(32), nullable=True),
        sa.Column("reason_for_visit", sa.String(200), nullable=True),
        sa.Column("preferred_date", sa.Date(), nullable=True),
        sa.Column("preferred_time_window", sa.String(32), nullable=True),
        sa.Column("requested_doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctors.id"), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("field_confidence", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("services.id"), nullable=True),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calls.id"), nullable=True),
        sa.Column("slot_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="booked"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('booked','rescheduled','cancelled','completed')", name="ck_appointments_status"),
    )
    op.create_index("ix_appointments_doctor_slot", "appointments", ["doctor_id", "slot_start"])
    op.execute(
        """
        ALTER TABLE appointments
        ADD CONSTRAINT appointments_no_overlap
        EXCLUDE USING gist (
            doctor_id WITH =,
            tstzrange(slot_start, slot_end, '[)') WITH &&
        )
        WHERE (status IN ('booked', 'rescheduled'))
        """
    )
    op.create_table(
        "callbacks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calls.id"), nullable=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("urgency", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("urgency in ('normal','urgent')", name="ck_callbacks_urgency"),
        sa.CheckConstraint("status in ('open','done')", name="ck_callbacks_status"),
    )
    op.create_table(
        "holidays",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.UniqueConstraint("clinic_id", "day", name="uq_holidays_clinic_day"),
    )
    op.create_table(
        "demo_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False, server_default=""),
        sa.Column("clinic_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("entity", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("demo_requests")
    op.drop_table("holidays")
    op.drop_table("callbacks")
    op.execute("ALTER TABLE appointments DROP CONSTRAINT IF EXISTS appointments_no_overlap")
    op.drop_index("ix_appointments_doctor_slot", table_name="appointments")
    op.drop_table("appointments")
    op.drop_table("call_extractions")
    op.drop_table("transcript_turns")
    op.drop_index("ix_calls_status", table_name="calls")
    op.drop_index("ix_calls_started_at", table_name="calls")
    op.drop_table("calls")
    op.drop_table("users")
    op.drop_index("ix_patients_phone", table_name="patients")
    op.drop_table("patients")
    op.drop_table("services")
    op.drop_table("doctors")
    op.drop_table("clinics")
