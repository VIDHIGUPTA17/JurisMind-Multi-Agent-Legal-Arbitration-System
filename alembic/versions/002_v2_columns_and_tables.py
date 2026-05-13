"""v2 — add chunk columns, verdict columns, arbitration_stages, audit_logs

Revision ID: 002
Revises: 001
Create Date: 2026-05-13 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── document_chunks: new semantic columns ────────────────────────────────
    op.add_column("document_chunks", sa.Column("section_header", sa.Text(), nullable=True))
    op.add_column("document_chunks", sa.Column("chunk_type", sa.String(50), nullable=True))
    op.add_column("document_chunks", sa.Column("token_count", sa.Integer(), nullable=True))
    op.add_column("document_chunks", sa.Column("page_numbers", JSONB(), nullable=True))
    op.add_column("document_chunks", sa.Column("document_filename", sa.String(500), nullable=True))

    # ── verdicts: v2 enrichment columns ─────────────────────────────────────
    op.add_column("verdicts", sa.Column("confidence_score", sa.Float(), nullable=True))
    op.add_column("verdicts", sa.Column("grounding_report", JSONB(), nullable=True))
    op.add_column("verdicts", sa.Column("bias_report", JSONB(), nullable=True))
    op.add_column("verdicts", sa.Column("settlement_recommendation", JSONB(), nullable=True))
    op.add_column("verdicts", sa.Column("compensation_breakdown", JSONB(), nullable=True))
    op.add_column("verdicts", sa.Column("stage_count", sa.Integer(), nullable=True, server_default="7"))
    op.add_column("verdicts", sa.Column("total_groq_tokens", sa.Integer(), nullable=True))
    op.add_column("verdicts", sa.Column("total_duration_ms", sa.Integer(), nullable=True))

    # ── arbitration_stages ───────────────────────────────────────────────────
    op.create_table(
        "arbitration_stages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_number", sa.Integer(), nullable=False),
        sa.Column("stage_name", sa.String(100), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", "SKIPPED", name="stagestatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("agent_name", sa.String(100), nullable=True),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_json", JSONB(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("citations", JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("groq_tokens_used", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_arbitration_stages_case_id", "arbitration_stages", ["case_id"])

    # ── audit_logs ───────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("case_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("details", JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_case_id", "audit_logs", ["case_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("arbitration_stages")
    op.execute("DROP TYPE IF EXISTS stagestatus")

    for col in ("total_duration_ms", "total_groq_tokens", "stage_count",
                "compensation_breakdown", "settlement_recommendation",
                "bias_report", "grounding_report", "confidence_score"):
        op.drop_column("verdicts", col)

    for col in ("document_filename", "page_numbers", "token_count", "chunk_type", "section_header"):
        op.drop_column("document_chunks", col)
