"""Initial schema (plain PostgreSQL, no pgvector)

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email_encrypted", sa.LargeBinary, nullable=False),
        sa.Column("email_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name_encrypted", sa.LargeBinary, nullable=False),
        sa.Column("role", sa.Enum("PARTY_A", "PARTY_B", name="userrole"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email_hash", "users", ["email_hash"])

    # cases
    op.create_table(
        "cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "case_type",
            sa.Enum("CONTRACT", "CONSUMER", "PROPERTY", "COMPANY", name="casetype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "OPEN", "PARTY_A_FILED", "PARTY_B_RESPONDED",
                "IN_ARBITRATION", "VERDICT_DELIVERED",
                name="casestatus",
            ),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("party_a_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("party_b_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("party_b_invite_email_hash", sa.String(64), nullable=True),
        sa.Column("party_b_invite_token", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # documents
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("uploader_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("content_anonymized", sa.Text, nullable=True),
        sa.Column("original_size_bytes", sa.Integer, nullable=True),
        sa.Column(
            "processing_status",
            sa.Enum("PENDING", "PROCESSING", "DONE", "FAILED", name="documentprocessingstatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_case_id", "documents", ["case_id"])

    # pii_mappings
    op.create_table(
        "pii_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("token", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("encrypted_value", sa.LargeBinary, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pii_mappings_document_id", "pii_mappings", ["document_id"])

    # pii_audit_logs
    op.create_table(
        "pii_audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("count_found", sa.Integer, nullable=False, server_default="0"),
        sa.Column("processing_time_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pii_audit_logs_document_id", "pii_audit_logs", ["document_id"])

    # document_chunks (with vector column)
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("chunk_text", sa.Text, nullable=False),
        sa.Column("embedding", JSONB, nullable=True),  # stored as JSON array
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_case_id", "document_chunks", ["case_id"])

    # verdicts
    op.create_table(
        "verdicts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id"), nullable=False, unique=True),
        sa.Column("agent_a_summary", sa.Text, nullable=True),
        sa.Column("agent_b_summary", sa.Text, nullable=True),
        sa.Column("judge_reasoning", sa.Text, nullable=True),
        sa.Column("verdict_text", sa.Text, nullable=True),
        sa.Column("applicable_laws", JSONB, nullable=False, server_default="[]"),
        sa.Column("relief_awarded", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verdicts_case_id", "verdicts", ["case_id"])


def downgrade() -> None:
    op.drop_table("verdicts")
    op.drop_table("document_chunks")
    op.drop_table("pii_audit_logs")
    op.drop_table("pii_mappings")
    op.drop_table("documents")
    op.drop_table("cases")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS documentprocessingstatus")
    op.execute("DROP TYPE IF EXISTS casestatus")
    op.execute("DROP TYPE IF EXISTS casetype")
    op.execute("DROP TYPE IF EXISTS userrole")
