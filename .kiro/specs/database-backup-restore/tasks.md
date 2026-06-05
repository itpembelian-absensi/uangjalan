# Implementation Plan: Database Backup & Restore

## Overview

Implement dev-only API endpoints for backing up and restoring the PostgreSQL database using pure Python (SQLAlchemy). The feature is gated by an `ENABLE_DB_TOOLS` environment variable and lives entirely in `backend/app/db_tools.py` with minimal changes to existing files.

## Tasks

- [x] 1. Extend Settings and wire conditional router registration
  - [x] 1.1 Add `enable_db_tools` and `db_tools_backup_dir` fields to Settings class
    - Add `enable_db_tools: bool = False` and `db_tools_backup_dir: str = "/tmp/db_backups"` to `backend/app/core/config.py`
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 Add conditional db_tools router registration in `create_app()`
    - In `backend/app/main.py`, after existing router includes, add: `if settings.enable_db_tools: from app.db_tools import router as db_tools_router; app.include_router(db_tools_router)`
    - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Implement core utility functions in `backend/app/db_tools.py`
  - [x] 2.1 Create module skeleton with router, imports, logger, and BackupJob dataclass
    - Create `backend/app/db_tools.py` with `APIRouter(prefix="/api/db-tools", tags=["db-tools"])`
    - Define `BackupJob` dataclass with fields: id, status, file_path, file_size, error, created_at, filename
    - Define in-memory `_backup_jobs: dict[str, BackupJob] = {}`
    - Add module-level connection test (`SELECT 1`) with info/warning logging
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 2.2 Implement `get_table_order(conn) -> list[str]` function
    - Query `information_schema.table_constraints` and `information_schema.constraint_column_usage` for FK relationships
    - Build directed graph (adjacency list) of table dependencies
    - Implement topological sort using Kahn's algorithm
    - Return ordered list (referenced tables first)
    - _Requirements: 3.3_

  - [ ]* 2.3 Write property test for topological sort (Property 1)
    - **Property 1: Topological sort respects all foreign key dependencies**
    - Generate random DAGs (1–30 nodes, varying edge density) using `hypothesis`
    - Assert all edges are satisfied in output order
    - Use `@settings(max_examples=100)`
    - **Validates: Requirements 3.3**

  - [x] 2.4 Implement `generate_create_table(conn, table_name) -> str` function
    - Query `information_schema.columns` for column definitions (name, type, nullable, defaults)
    - Query constraints (PRIMARY KEY, UNIQUE, FOREIGN KEY) from `information_schema`
    - Build proper CREATE TABLE DDL string
    - _Requirements: 3.2_

  - [x] 2.5 Implement `generate_inserts(conn, table_name) -> str` function
    - SELECT all rows from the table
    - Format as INSERT statements with proper value escaping (strings with quotes, NULLs, numerics, booleans, timestamps)
    - Handle special characters (`'`, `\`, newlines, unicode)
    - _Requirements: 3.2_

  - [ ]* 2.6 Write property test for SQL value serialization (Property 2)
    - **Property 2: SQL value serialization round-trip**
    - Generate random row data (strings with special chars, NULLs, numbers, booleans, timestamps) using `hypothesis`
    - Call value escaping logic, verify output can be parsed back to original values
    - Use `@settings(max_examples=100)`
    - **Validates: Requirements 3.2**

  - [x] 2.7 Implement `cleanup_old_backups()` function
    - Read files from backup directory
    - Delete files older than 1 hour based on file modification time
    - Handle missing directory gracefully
    - _Requirements: 7.2, 7.3_

  - [ ]* 2.8 Write property test for backup cleanup (Property 3)
    - **Property 3: Backup cleanup removes only expired files**
    - Generate random file sets with timestamps spread across 0–120 minutes ago using `hypothesis`
    - Mock filesystem, call cleanup, verify exactly the right files remain
    - Use `@settings(max_examples=100)`
    - **Validates: Requirements 7.2**

- [x] 3. Checkpoint - Verify core utilities
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement backup endpoints
  - [x] 4.1 Implement `POST /api/db-tools/backup` endpoint
    - Generate UUID4 backup_id
    - Call `cleanup_old_backups()` before starting
    - Create `BackupJob` with status `"in_progress"`
    - Start `run_backup(backup_id)` as FastAPI `BackgroundTask`
    - Return HTTP 202 with `{"backup_id": ..., "status": "in_progress"}`
    - _Requirements: 3.1, 7.3_

  - [x] 4.2 Implement `run_backup(backup_id)` orchestration function
    - Create backup directory with `os.makedirs(..., exist_ok=True)`
    - Generate filename using pattern `uang_pengiriman_YYYY-MM-DDTHH-MM-SS.sql`
    - Call `get_table_order` → iterate tables → call `generate_create_table` + `generate_inserts` for each
    - Wrap output in `BEGIN;` ... `COMMIT;` with header comments
    - Write to file, update BackupJob with completed status, file_path, file_size
    - On error: update BackupJob with failed status and error message
    - _Requirements: 3.1, 3.2, 3.3, 4.1_

  - [x] 4.3 Implement `GET /api/db-tools/backup/{backup_id}/status` endpoint
    - Look up backup_id in `_backup_jobs`
    - Return 404 if not found
    - Return status JSON with download_url and file_size when completed
    - _Requirements: 3.4, 3.5, 3.8_

  - [x] 4.4 Implement `GET /api/db-tools/backup/{backup_id}/download` endpoint
    - Look up backup_id, verify status is completed
    - Return 404 if not found or not completed
    - Stream file as response with `Content-Type: application/sql` and `Content-Disposition` header with filename
    - _Requirements: 3.6, 4.2_

  - [x] 4.5 Implement `GET /api/db-tools/status` endpoint
    - Execute `SELECT 1` to check connection health
    - Return JSON with connected status, database name, and host
    - _Requirements: 2.4_

- [x] 5. Checkpoint - Verify backup endpoints
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement restore endpoint
  - [x] 6.1 Implement `POST /api/db-tools/restore` endpoint
    - Accept multipart form with fields: `file` (UploadFile), `mode` (str, default "full"), `confirm` (str)
    - Validate `confirm == "true"` → 400 if missing/wrong
    - Validate file is not empty → 400 if zero bytes
    - Validate file size ≤ 100 MB → 413 if exceeded
    - _Requirements: 5.7, 5.9, 5.10, 6.1, 6.2_

  - [x] 6.2 Implement restore execution logic within a single transaction
    - Read uploaded file content
    - For mode `"full"`: drop all tables in reverse dependency order, then execute all SQL
    - For mode `"schema_only"`: drop all tables in reverse dependency order, execute only DDL statements
    - For mode `"data_only"`: truncate all tables in reverse dependency order, execute only INSERT statements
    - Wrap in `engine.begin()` context manager for automatic rollback on error
    - Return 200 with success message, mode, and timestamp on success
    - Return 500 with error message on SQL execution failure
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.8, 5.11_

  - [ ]* 6.3 Write unit tests for restore input validation
    - Test missing confirm field returns 400
    - Test empty file returns 400
    - Test oversized file returns 413
    - Test valid modes accepted, invalid mode rejected
    - _Requirements: 5.7, 5.9, 5.10, 6.1, 6.2_

- [x] 7. Checkpoint - Verify all endpoints work together
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Integration wiring and final verification
  - [x] 8.1 Add `hypothesis` and `pytest` to `backend/requirements.txt`
    - Add `hypothesis` and `pytest` as test dependencies
    - _Requirements: (testing infrastructure)_

  - [ ]* 8.2 Write integration test for route gating
    - Test that endpoints return 404 when `ENABLE_DB_TOOLS` is not set
    - Test that endpoints are available when `ENABLE_DB_TOOLS=true`
    - _Requirements: 1.1, 1.2_

  - [ ]* 8.3 Write integration test for full backup-restore cycle
    - Trigger backup → poll status → download file → restore with mode "full" → verify data
    - _Requirements: 3.1, 3.4, 3.6, 5.1, 5.3_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The project uses synchronous SQLAlchemy (not async) with `pg8000` driver — `db_tools.py` should follow same pattern
- No authentication is needed for these endpoints (dev-only, gated by env var)
- All backup/restore logic lives in a single file (`backend/app/db_tools.py`) to keep the feature self-contained

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.4", "2.5", "2.7"] },
    { "id": 3, "tasks": ["2.3", "2.6", "2.8", "4.5"] },
    { "id": 4, "tasks": ["4.1", "4.2"] },
    { "id": 5, "tasks": ["4.3", "4.4"] },
    { "id": 6, "tasks": ["6.1"] },
    { "id": 7, "tasks": ["6.2"] },
    { "id": 8, "tasks": ["6.3", "8.1"] },
    { "id": 9, "tasks": ["8.2", "8.3"] }
  ]
}
```
