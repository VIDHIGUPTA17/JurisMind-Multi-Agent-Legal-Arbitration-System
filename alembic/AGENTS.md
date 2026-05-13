# AGENTS.md — alembic/

## Purpose
Database migration management using Alembic. Tracks schema changes as versioned Python scripts so the PostgreSQL database can be evolved without losing data.

## Files

### `env.py`
Alembic environment configuration. Connects to the PostgreSQL database and imports all SQLAlchemy models.

**Key configuration:**
- Reads `DATABASE_URL` from `alembic.ini` (which references `.env`)
- Imports `Base` from `app.models` to access all model metadata
- Runs in **async mode** (uses `asyncio.run()` to handle async SQLAlchemy engine)
- `target_metadata = Base.metadata` — tells Alembic which tables to manage

### `versions/001_initial_schema.py`
The first migration — creates the initial database schema.

**Tables created:**
- `users`
- `cases`
- `documents`
- `verdicts`
- `document_chunks`
- `pii_mappings`
- `pii_audit_logs`

**Status:** This migration was written for the v1 schema. The v2 upgrade (from CHANGES.md) adds:
- `arbitration_stages` table (new)
- `audit_logs` table (new)
- New columns on `verdicts` (confidence_score, grounding_report, bias_report, etc.)
- New columns on `document_chunks` (section_header, chunk_type, token_count, page_numbers, document_filename)

**A new migration must be generated for these v2 changes.**

## Common Commands

```bash
# Apply all pending migrations (run this before starting the server)
alembic upgrade head

# Generate a new migration from model changes
alembic revision --autogenerate -m "add_arbitration_stages"

# Check current migration state
alembic current

# Roll back one migration
alembic downgrade -1

# Roll back to a specific revision
alembic downgrade 001_initial_schema

# View migration history
alembic history
```

## Generating the v2 Migration

After adding the new models (`ArbitrationStage`, `AuditLog`) and new columns to `Verdict` and `DocumentChunk`, run:

```bash
alembic revision --autogenerate -m "v2_multi_agent_pipeline"
alembic upgrade head
```

Alembic will compare `Base.metadata` (from all imported models) against the live database schema and generate the diff automatically.

## Important Notes

1. **Always run `alembic upgrade head` before starting the server** after pulling new changes — otherwise the app will crash with column-not-found errors.

2. **`document_chunks` embedding dimension:** The v2 upgrade changes the embedding model from 384-dim to 768-dim. Existing chunks stored with 384-dim vectors are incompatible with the new retriever. After the migration:
   - All old `DocumentChunk` rows should be deleted (or re-embedded)
   - Re-process existing documents through the new pipeline

3. **Do not edit migration files after they have been applied to any database.** Instead, generate a new migration.

4. **Enum changes require manual SQL** in the migration — Alembic cannot auto-generate ALTER TYPE for PostgreSQL enums. Add manually:
   ```python
   op.execute("ALTER TYPE stagestatus ADD VALUE 'SKIPPED'")
   ```

## alembic.ini

Located at project root. Key setting:
```ini
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://arbitration:arbitration_secret@localhost:5432/legal_arbitration
```

The `sqlalchemy.url` should match `DATABASE_URL` in `.env`.
