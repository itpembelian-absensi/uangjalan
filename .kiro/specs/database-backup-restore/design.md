# Design Document: Database Backup & Restore

## Overview

This feature adds development-only API endpoints for backing up and restoring the PostgreSQL database (`uang_pengiriman`). It is implemented as a pure Python module (`backend/app/db_tools.py`) that uses SQLAlchemy to introspect `information_schema`, generate SQL DDL/INSERT statements, and execute restore operations. The endpoints are conditionally registered in the FastAPI app based on the `ENABLE_DB_TOOLS` environment variable, ensuring they never appear in production.

**Key Design Decisions:**
- **Pure Python approach** — No dependency on `pg_dump`/`psql` CLI tools, making the feature portable across all environments (Windows, Linux, Docker).
- **Background task for backup** — Backup runs as a FastAPI `BackgroundTask` to avoid blocking the HTTP response for large databases.
- **Single-file module** — All backup/restore logic lives in `backend/app/db_tools.py` to minimize footprint and keep the feature self-contained.
- **No auth required** — Since this is a dev-only tool gated by environment variable, authentication is deliberately omitted to simplify usage.

## Architecture

```mermaid
graph TD
    subgraph "FastAPI App (main.py)"
        A[create_app] -->|ENABLE_DB_TOOLS=true| B[Include db_tools router]
        A -->|ENABLE_DB_TOOLS≠true| C[Skip db_tools router]
    end

    subgraph "db_tools.py"
        D[Router /api/db-tools]
        D --> E[GET /status]
        D --> F[POST /backup]
        D --> G[GET /backup/{id}/status]
        D --> H[GET /backup/{id}/download]
        D --> I[POST /restore]
    end

    subgraph "Backup Process"
        F -->|BackgroundTask| J[generate_dump]
        J --> K[Query information_schema]
        K --> L[Topological sort tables by FK]
        L --> M[Generate DDL + INSERTs]
        M --> N[Write .sql file to disk]
    end

    subgraph "Restore Process"
        I --> O[Parse uploaded file]
        O --> P[Drop/Truncate tables]
        P --> Q[Execute SQL in transaction]
    end

    subgraph "Storage"
        N --> R[/tmp/db_backups/ or configurable path]
        H --> R
    end
```

### Conditional Route Registration

In `main.py`, the `create_app()` function checks the `ENABLE_DB_TOOLS` setting. If truthy, it imports and includes the `db_tools` router:

```python
# In create_app() — after existing router includes
if settings.enable_db_tools:
    from app.db_tools import router as db_tools_router
    app.include_router(db_tools_router)
```

This ensures:
- When `ENABLE_DB_TOOLS` is not set or not `"true"`, the routes don't exist (HTTP 404 by FastAPI default).
- No import of `db_tools` happens at all in production, minimizing risk.

## Components and Interfaces

### 1. Settings Extension (`backend/app/core/config.py`)

Add to the `Settings` class:

```python
enable_db_tools: bool = False
db_tools_backup_dir: str = "/tmp/db_backups"
```

The `enable_db_tools` field maps to `ENABLE_DB_TOOLS` env var. Pydantic-settings coerces `"true"` → `True`.

### 2. Database Tools Module (`backend/app/db_tools.py`)

#### Router

```python
router = APIRouter(prefix="/api/db-tools", tags=["db-tools"])
```

#### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/db-tools/status` | Check DB connection health |
| POST | `/api/db-tools/backup` | Trigger background backup |
| GET | `/api/db-tools/backup/{backup_id}/status` | Poll backup progress |
| GET | `/api/db-tools/backup/{backup_id}/download` | Download completed backup |
| POST | `/api/db-tools/restore` | Upload and restore dump file |

#### Core Functions

| Function | Purpose |
|----------|---------|
| `check_connection() → bool` | Execute `SELECT 1` to verify DB health |
| `get_table_order(conn) → list[str]` | Query `information_schema.table_constraints` and `key_column_usage` to build FK dependency graph, then topologically sort |
| `generate_create_table(conn, table_name) → str` | Query `information_schema.columns` to build CREATE TABLE DDL |
| `generate_inserts(conn, table_name) → str` | SELECT all rows, format as INSERT statements with proper escaping |
| `run_backup(backup_id: str)` | Orchestrates full dump generation, writes to file, updates status |
| `cleanup_old_backups()` | Remove files older than 1 hour from backup directory |

### 3. Backup State Management

In-memory dict tracking backup jobs:

```python
_backup_jobs: dict[str, BackupJob] = {}
```

Each `BackupJob` stores: `id`, `status` (in_progress/completed/failed), `file_path`, `file_size`, `error`, `created_at`.

### 4. Table Dependency Resolution

Uses a directed graph approach:
1. Query `information_schema.table_constraints` + `information_schema.constraint_column_usage` for foreign key relationships
2. Build adjacency list (table → tables it depends on)
3. Topological sort using Kahn's algorithm
4. Return ordered list for backup (dependency order) and reverse for drop/truncate

## Data Models

### BackupJob (in-memory dataclass)

```python
@dataclass
class BackupJob:
    id: str                          # UUID4 string
    status: str                      # "in_progress" | "completed" | "failed"
    file_path: str | None = None     # Path to generated .sql file
    file_size: int | None = None     # File size in bytes
    error: str | None = None         # Error message if failed
    created_at: datetime = field(default_factory=datetime.now)
    filename: str | None = None      # Generated filename with timestamp
```

### Request/Response Schemas

**POST /backup response (202):**
```json
{
  "backup_id": "uuid-string",
  "status": "in_progress"
}
```

**GET /backup/{id}/status response (200):**
```json
{
  "backup_id": "uuid-string",
  "status": "completed",
  "download_url": "/api/db-tools/backup/{id}/download",
  "file_size": 123456,
  "filename": "uang_pengiriman_2024-01-15T14-30-00.sql"
}
```

**POST /restore form fields:**
- `file`: UploadFile (the .sql dump file, max 100 MB)
- `mode`: str — `"full"` | `"schema_only"` | `"data_only"` (default: `"full"`)
- `confirm`: str — must be `"true"`

**POST /restore response (200):**
```json
{
  "message": "Restore berhasil",
  "mode": "full",
  "restored_at": "2024-01-15T14:30:00"
}
```

### SQL Generation Format

The generated dump file structure:

```sql
-- Uang Pengiriman Database Backup
-- Generated: 2024-01-15T14:30:00
-- Database: uang_pengiriman

BEGIN;

-- Table: vehicle_brands
CREATE TABLE IF NOT EXISTS vehicle_brands (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO vehicle_brands (id, name, created_at) VALUES
(1, 'Hino', '2024-01-01 00:00:00+07'),
(2, 'Mitsubishi', '2024-01-01 00:00:00+07');

-- ... more tables in dependency order ...

COMMIT;
```

### File Naming

Pattern: `uang_pengiriman_YYYY-MM-DDTHH-MM-SS.sql`

Example: `uang_pengiriman_2024-01-15T14-30-00.sql`

### Restore Modes

| Mode | Drop Tables | Execute DDL | Execute INSERTs |
|------|-------------|-------------|-----------------|
| `full` | Yes (reverse order) | Yes | Yes |
| `schema_only` | Yes (reverse order) | Yes | No |
| `data_only` | No (truncate only) | No | Yes |

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Topological sort respects all foreign key dependencies

*For any* valid directed acyclic graph of table dependencies (where an edge from A→B means "A has a foreign key referencing B"), the ordered list produced by `get_table_order` SHALL place every referenced table before the table that references it. In other words, for every FK relationship `table_a → table_b`, `table_b` must appear at an earlier index than `table_a` in the output.

**Validates: Requirements 3.3**

### Property 2: SQL value serialization round-trip

*For any* row of data containing valid PostgreSQL column values (strings with special characters, NULLs, numerics, booleans, timestamps), the INSERT statement produced by `generate_inserts` SHALL, when executed against an equivalent table schema, reproduce the original row values exactly (accounting for type coercion rules).

**Validates: Requirements 3.2**

### Property 3: Backup cleanup removes only expired files

*For any* set of backup files with various creation timestamps and a current time T, calling `cleanup_old_backups()` SHALL delete all and only those files whose creation time is more than 1 hour before T. Files created within the last hour SHALL remain untouched.

**Validates: Requirements 7.2**

## Error Handling

### Backup Errors

| Error Condition | Behavior |
|----------------|----------|
| Database unreachable during backup | Set job status to `"failed"`, store error message |
| Permission denied on table | Set job status to `"failed"`, include table name in error |
| Disk full / write error | Set job status to `"failed"`, log and store IOError message |
| Backup directory doesn't exist | Create it automatically (`os.makedirs(..., exist_ok=True)`) |

### Restore Errors

| Error Condition | HTTP Status | Response |
|----------------|-------------|----------|
| Missing `confirm=true` | 400 | `"Konfirmasi restore diperlukan. Kirim field 'confirm' dengan nilai 'true'"` |
| Empty/zero-byte file | 400 | `"File backup kosong atau tidak valid"` |
| File exceeds 100 MB | 413 | `"Ukuran file melebihi batas maksimum 100 MB"` |
| Invalid SQL in dump file | 500 | Descriptive error message, transaction rolled back |
| Database connection lost during restore | 500 | Connection error message, transaction rolled back |

### Transaction Safety

The restore operation wraps all SQL execution in a single transaction:

```python
with engine.begin() as conn:
    # All DDL/DML here — auto-rollback on exception
    ...
```

If any statement fails, SQLAlchemy's context manager performs an automatic rollback, ensuring no partial state is left behind.

### Connection Test on Module Load

When `db_tools.py` is imported (only happens when `ENABLE_DB_TOOLS=true`), it attempts `SELECT 1`:
- Success → `logger.info("Database tools ready — connected to %s", db_name)`
- Failure → `logger.warning("Database tools: connection failed — %s", error_msg)`

This is non-fatal; the module still loads, but individual operations will fail with descriptive errors if the DB remains unreachable.

## Testing Strategy

### Unit Tests

Focus on pure logic functions that don't require a real database:

1. **Topological sort** — Test with various graph shapes (linear chain, diamond, multiple roots, single table with no FKs)
2. **Filename generation** — Verify format matches `uang_pengiriman_YYYY-MM-DDTHH-MM-SS.sql`
3. **SQL value escaping** — Test strings with quotes, backslashes, NULL values, unicode
4. **File cleanup logic** — Test age-based deletion with mocked filesystem
5. **Restore mode parsing** — Verify valid/invalid mode values
6. **Input validation** — Empty file detection, size limit check, missing confirm field
7. **Backup job state transitions** — Verify in_progress → completed/failed

### Property-Based Tests

Using `hypothesis` (Python PBT library, already compatible with the project's Python 3.11 stack):

- **Property 1**: Generate random DAGs (varying node count 1–30, varying edge density), run `get_table_order`, assert all edges are satisfied in output order. Minimum 100 iterations.
  - Tag: `Feature: database-backup-restore, Property 1: Topological sort respects all foreign key dependencies`

- **Property 2**: Generate random row data (strings with special chars including `'`, `\`, `\n`, NULL, numbers, booleans, timestamps), call `generate_inserts`, parse/execute against in-memory SQLite or verify by re-parsing. Minimum 100 iterations.
  - Tag: `Feature: database-backup-restore, Property 2: SQL value serialization round-trip`

- **Property 3**: Generate random file sets with timestamps spread across 0–120 minutes ago, call cleanup, verify exactly the right files remain. Minimum 100 iterations.
  - Tag: `Feature: database-backup-restore, Property 3: Backup cleanup removes only expired files`

### Integration Tests

Require a running PostgreSQL instance (use Docker test container or the existing `uangjalan-db`):

1. **Full backup and restore cycle** — Seed data → backup → modify data → restore (full) → verify original data
2. **Schema-only restore** — Backup → drop tables → restore schema_only → verify tables exist but empty
3. **Data-only restore** — Backup → truncate → restore data_only → verify data present
4. **Status endpoint** — Verify JSON response with connection health
5. **Route gating** — Verify endpoints return 404 when `ENABLE_DB_TOOLS` is not set

### Test Configuration

- Property tests: `hypothesis` with `@settings(max_examples=100)`
- Unit tests: `pytest` with standard fixtures
- Integration tests: `pytest` with database fixtures (setup/teardown via transaction rollback)

