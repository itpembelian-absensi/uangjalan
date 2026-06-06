"""Database backup & restore tools (dev-only).

This module provides API endpoints for backing up and restoring the PostgreSQL
database. It is only loaded when ENABLE_DB_TOOLS=true.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from starlette.responses import JSONResponse
from sqlalchemy import create_engine, text

from app.core.config import settings

# Separate engine for db-tools to avoid starving the API connection pool
_tools_engine = create_engine(
    settings.database_url,
    pool_size=2,
    max_overflow=0,
    pool_pre_ping=True,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/db-tools", tags=["db-tools"])

# ---------------------------------------------------------------------------
# BackupJob dataclass
# ---------------------------------------------------------------------------


@dataclass
class BackupJob:
    """Tracks the state of a background backup job."""

    id: str
    status: str  # "in_progress" | "completed" | "failed"
    file_path: str | None = None
    file_size: int | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    filename: str | None = None


# In-memory store for backup jobs
_backup_jobs: dict[str, BackupJob] = {}

# ---------------------------------------------------------------------------
# Module-level connection test
# ---------------------------------------------------------------------------

try:
    with _tools_engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
        _conn.commit()
    logger.info("Database tools ready — connected to %s", settings.database_url.split("/")[-1])
except Exception as exc:
    logger.warning("Database tools: connection failed — %s", exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status")
def get_status():
    """Check database connection health.

    Executes SELECT 1 to verify the database is reachable and returns
    connection metadata extracted from the DATABASE_URL.
    """
    # Extract database name and host from the database URL
    db_url = settings.database_url
    # Typical format: postgresql+driver://user:pass@host:port/dbname
    # or: postgresql://user:pass@host:port/dbname
    try:
        # Parse after the @ sign for host, and after the last / for db name
        after_scheme = db_url.split("://", 1)[-1]  # user:pass@host:port/dbname
        at_split = after_scheme.rsplit("@", 1)
        if len(at_split) == 2:
            host_port_db = at_split[1]  # host:port/dbname
        else:
            host_port_db = at_split[0]

        if "/" in host_port_db:
            host_port, database = host_port_db.split("/", 1)
            # Remove query params from database name if present
            database = database.split("?")[0]
        else:
            host_port = host_port_db
            database = ""

        # Extract just the host (remove port)
        host = host_port.split(":")[0]
    except Exception:
        database = ""
        host = ""

    # Test the connection
    try:
        with _tools_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
        return {"connected": True, "database": database, "host": host}
    except Exception as exc:
        return {"connected": False, "database": database, "host": host, "error": str(exc)}


@router.post("/backup", status_code=202)
def trigger_backup(background_tasks: BackgroundTasks):
    """Trigger a background database backup.

    Cleans up old backups, creates a new BackupJob in "in_progress" state,
    schedules the backup to run in the background, and immediately returns
    HTTP 202 with the backup_id.
    """
    cleanup_old_backups()

    backup_id = str(uuid.uuid4())
    job = BackupJob(id=backup_id, status="in_progress")
    _backup_jobs[backup_id] = job

    background_tasks.add_task(run_backup, backup_id)

    return JSONResponse(
        status_code=202,
        content={"backup_id": backup_id, "status": "in_progress"},
    )


@router.get("/backup/{backup_id}/status")
def get_backup_status(backup_id: str):
    """Poll the status of a background backup job.

    Returns the current status of the backup job. When completed, includes
    the download URL, file size, and filename. When failed, includes the
    error message.
    """
    job = _backup_jobs.get(backup_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Backup job not found")

    response = {
        "backup_id": job.id,
        "status": job.status,
    }

    if job.status == "completed":
        response["download_url"] = f"/api/db-tools/backup/{job.id}/download"
        response["file_size"] = job.file_size
        response["filename"] = job.filename

    if job.status == "failed":
        response["error"] = job.error

    return response


@router.get("/backup/{backup_id}/download")
def download_backup(backup_id: str):
    """Download a completed backup file.

    Streams the .sql backup file with appropriate content headers.
    Returns 404 if the backup job doesn't exist or hasn't completed.
    """
    job = _backup_jobs.get(backup_id)
    if job is None or job.status != "completed":
        raise HTTPException(status_code=404, detail="Backup not found or not completed")

    return FileResponse(
        path=job.file_path,
        media_type="application/sql",
        filename=job.filename,
        headers={"Content-Disposition": f'attachment; filename="{job.filename}"'},
    )


@router.post("/restore")
def restore_database(
    file: UploadFile = File(...),
    mode: str = Form("full"),
    confirm: str = Form(""),
):
    """Restore the database from an uploaded SQL dump file.

    Accepts a multipart form with the SQL dump file, restore mode, and
    confirmation field. Validates inputs, then executes the restore within
    a single transaction for atomicity.

    Modes:
    - full: drop all tables, execute all SQL from the dump
    - schema_only: drop all tables, execute only DDL statements (CREATE, DROP, ALTER)
    - data_only: truncate all tables, execute only INSERT statements
    """
    # Validate confirmation
    if confirm != "true":
        return JSONResponse(
            status_code=400,
            content={"detail": "Konfirmasi restore diperlukan. Kirim field 'confirm' dengan nilai 'true'"},
        )

    # Read file content
    file_content = file.file.read()

    # Validate file is not empty
    if len(file_content) == 0:
        return JSONResponse(
            status_code=400,
            content={"detail": "File backup kosong atau tidak valid"},
        )

    # Validate file size (max 100 MB)
    max_size = 100 * 1024 * 1024  # 100 MB
    if len(file_content) > max_size:
        return JSONResponse(
            status_code=413,
            content={"detail": "Ukuran file melebihi batas maksimum 100 MB"},
        )

    # Decode file content as UTF-8
    try:
        sql_content = file_content.decode("utf-8")
    except UnicodeDecodeError:
        return JSONResponse(
            status_code=400,
            content={"detail": "File backup kosong atau tidak valid"},
        )

    # Execute restore within a single transaction
    try:
        with _tools_engine.begin() as conn:
            # Get table order and reverse it for drop/truncate operations
            tables = get_table_order(conn)
            reversed_tables = list(reversed(tables))

            if mode == "full":
                # Drop all tables in reverse dependency order
                for table_name in reversed_tables:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))

                # Execute all SQL statements from the dump
                _execute_sql_statements(conn, sql_content, mode="full")

            elif mode == "schema_only":
                # Drop all tables in reverse dependency order
                for table_name in reversed_tables:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))

                # Execute only DDL statements (CREATE, DROP, ALTER)
                _execute_sql_statements(conn, sql_content, mode="schema_only")

            elif mode == "data_only":
                # Truncate all tables in reverse dependency order
                for table_name in reversed_tables:
                    conn.execute(text(f'TRUNCATE TABLE "{table_name}" CASCADE'))

                # Execute only INSERT statements
                _execute_sql_statements(conn, sql_content, mode="data_only")

            else:
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"Mode restore tidak valid: {mode}"},
                )

        # Return success
        restored_at = datetime.now().isoformat()
        return {
            "message": "Restore berhasil",
            "mode": mode,
            "restored_at": restored_at,
        }

    except Exception as exc:
        logger.error("Restore failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Restore gagal: {str(exc)}"},
        )


def _execute_sql_statements(conn, sql_content: str, mode: str) -> None:
    """Parse and execute SQL statements from the dump content.

    Splits the SQL content by semicolons, filters statements based on restore
    mode, and executes each valid statement. Skips empty statements, comments,
    and BEGIN/COMMIT lines (since we wrap in our own transaction).

    Args:
        conn: Active SQLAlchemy connection within a transaction.
        sql_content: The full SQL dump file content as a string.
        mode: One of "full", "schema_only", or "data_only".
    """
    # Split by semicolons, but ignore semicolons inside string literals
    raw_statements = []
    current_statement = []
    in_string = False
    
    i = 0
    while i < len(sql_content):
        char = sql_content[i]
        
        if in_string:
            if char == '\\':
                current_statement.append(char)
                i += 1
                if i < len(sql_content):
                    current_statement.append(sql_content[i])
            elif char == "'":
                in_string = False
                current_statement.append(char)
            else:
                current_statement.append(char)
        else:
            if char == "'":
                in_string = True
                current_statement.append(char)
            elif char == ';':
                raw_statements.append("".join(current_statement))
                current_statement = []
            else:
                current_statement.append(char)
        i += 1

    if current_statement:
        raw_statements.append("".join(current_statement))

    for raw_stmt in raw_statements:
        # Clean up the statement
        stmt = raw_stmt.strip()

        if not stmt:
            continue

        # Skip pure comment blocks
        lines = stmt.splitlines()
        non_comment_lines = [
            line for line in lines
            if line.strip() and not line.strip().startswith("--")
        ]

        if not non_comment_lines:
            continue

        # Get the first meaningful line (non-comment, non-empty)
        first_meaningful = non_comment_lines[0].strip().upper()

        # Skip BEGIN/COMMIT lines (we manage our own transaction)
        if first_meaningful in ("BEGIN", "COMMIT"):
            continue

        # Filter based on mode
        if mode == "schema_only":
            # Only execute DDL: CREATE, DROP, ALTER statements
            if not (
                first_meaningful.startswith("CREATE")
                or first_meaningful.startswith("DROP")
                or first_meaningful.startswith("ALTER")
            ):
                continue

        elif mode == "data_only":
            # Only execute INSERT statements
            if not first_meaningful.startswith("INSERT"):
                continue

        # mode == "full": execute everything (DDL + DML)

        # Execute the statement
        conn.execute(text(stmt))


def run_backup(backup_id: str) -> None:
    """Orchestrate the full database backup process.

    Creates the backup directory, connects to the database, generates DDL
    and INSERT statements for all tables in dependency order, wraps them
    in a transaction block, and writes the result to a .sql file. Updates
    the BackupJob with completion status or error details.
    """
    job = _backup_jobs[backup_id]

    try:
        # Ensure backup directory exists
        backup_dir = settings.db_tools_backup_dir
        os.makedirs(backup_dir, exist_ok=True)

        # Generate filename with timestamp
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%dT%H-%M-%S")
        filename = f"uang_pengiriman_{timestamp}.sql"
        file_path = os.path.join(backup_dir, filename)

        # Connect and generate the dump (REPEATABLE READ for consistent snapshot)
        with _tools_engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
            tables = get_table_order(conn)

            # Extract database name from settings
            db_url = settings.database_url
            try:
                db_name = db_url.split("/")[-1].split("?")[0]
            except Exception:
                db_name = "uang_pengiriman"

            # Build the SQL dump content
            parts: list[str] = []
            parts.append(f"-- Uang Pengiriman Database Backup")
            parts.append(f"-- Generated: {now.isoformat()}")
            parts.append(f"-- Database: {db_name}")
            parts.append("")
            parts.append("BEGIN;")
            parts.append("")

            for table_name in tables:
                parts.append(f"-- Table: {table_name}")
                ddl = generate_create_table(conn, table_name)
                parts.append(ddl)
                parts.append("")

                inserts = generate_inserts(conn, table_name)
                if inserts:
                    parts.append(inserts)
                    parts.append("")

            parts.append("COMMIT;")

            content = "\n".join(parts)

        # Write to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Update job with success
        file_size = os.path.getsize(file_path)
        job.status = "completed"
        job.file_path = file_path
        job.file_size = file_size
        job.filename = filename

        logger.info("Backup completed: %s (%d bytes)", filename, file_size)

    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        logger.error("Backup failed for job %s: %s", backup_id, exc)


def generate_create_table(conn, table_name: str) -> str:
    """Generate a CREATE TABLE IF NOT EXISTS DDL statement for the given table.

    Queries information_schema to build column definitions and constraints.
    Handles SERIAL/BIGSERIAL detection, NUMERIC precision/scale, and all
    common PostgreSQL types used in this project.
    """
    # --- Query column definitions ---
    cols_query = text("""
        SELECT
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default,
            udt_name,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :table_name
        ORDER BY ordinal_position
    """)
    columns = conn.execute(cols_query, {"table_name": table_name}).fetchall()

    # --- Query PRIMARY KEY columns ---
    pk_query = text("""
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = 'public'
            AND tc.table_name = :table_name
            AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
    """)
    pk_columns = [row[0] for row in conn.execute(pk_query, {"table_name": table_name}).fetchall()]

    # --- Query UNIQUE constraints ---
    uq_query = text("""
        SELECT tc.constraint_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = 'public'
            AND tc.table_name = :table_name
            AND tc.constraint_type = 'UNIQUE'
        ORDER BY tc.constraint_name, kcu.ordinal_position
    """)
    uq_rows = conn.execute(uq_query, {"table_name": table_name}).fetchall()
    # Group unique constraints by constraint name
    unique_constraints: dict[str, list[str]] = {}
    for row in uq_rows:
        constraint_name, col_name = row[0], row[1]
        unique_constraints.setdefault(constraint_name, []).append(col_name)

    # --- Query FOREIGN KEY constraints ---
    fk_query = text("""
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.update_rule,
            rc.delete_rule
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON tc.constraint_name = ccu.constraint_name
            AND tc.table_schema = ccu.table_schema
        JOIN information_schema.referential_constraints rc
            ON tc.constraint_name = rc.constraint_name
            AND tc.table_schema = rc.constraint_schema
        WHERE tc.table_schema = 'public'
            AND tc.table_name = :table_name
            AND tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.constraint_name, kcu.ordinal_position
    """)
    fk_rows = conn.execute(fk_query, {"table_name": table_name}).fetchall()
    # Group FK constraints: {constraint_name: {columns, ref_table, ref_columns, on_update, on_delete}}
    fk_constraints: dict[str, dict] = {}
    for row in fk_rows:
        cname, col, ref_table, ref_col, update_rule, delete_rule = (
            row[0], row[1], row[2], row[3], row[4], row[5]
        )
        if cname not in fk_constraints:
            fk_constraints[cname] = {
                "columns": [],
                "ref_table": ref_table,
                "ref_columns": [],
                "on_update": update_rule,
                "on_delete": delete_rule,
            }
        fk_constraints[cname]["columns"].append(col)
        fk_constraints[cname]["ref_columns"].append(ref_col)

    # --- Query CHECK constraints ---
    ck_query = text("""
        SELECT
            tc.constraint_name,
            cc.check_clause
        FROM information_schema.table_constraints tc
        JOIN information_schema.check_constraints cc
            ON tc.constraint_name = cc.constraint_name
            AND tc.constraint_schema = cc.constraint_schema
        WHERE tc.table_schema = 'public'
            AND tc.table_name = :table_name
            AND tc.constraint_type = 'CHECK'
            AND tc.constraint_name NOT LIKE '%_not_null'
    """)
    ck_rows = conn.execute(ck_query, {"table_name": table_name}).fetchall()

    check_constraints: dict[str, str] = {}
    for row in ck_rows:
        check_constraints[row[0]] = row[1]

    # --- Build column definitions ---
    col_defs = []
    # Track single-column unique constraints for inline UNIQUE
    single_col_uniques = set()
    for cols in unique_constraints.values():
        if len(cols) == 1:
            single_col_uniques.add(cols[0])

    for col_row in columns:
        col_name = col_row[0]
        data_type = col_row[1]
        char_max_len = col_row[2]
        is_nullable = col_row[3]
        col_default = col_row[4]
        udt_name = col_row[5]
        numeric_precision = col_row[6]
        numeric_scale = col_row[7]

        # Detect SERIAL/BIGSERIAL via nextval in default
        is_serial = False
        if col_default and "nextval" in str(col_default):
            is_serial = True

        # Determine SQL type
        if is_serial:
            if udt_name == "int4" or data_type == "integer":
                type_str = "SERIAL"
            else:
                type_str = "BIGSERIAL"
        elif udt_name == "int4" or data_type == "integer":
            type_str = "INTEGER"
        elif udt_name == "int8" or data_type == "bigint":
            type_str = "BIGINT"
        elif udt_name == "int2" or data_type == "smallint":
            type_str = "SMALLINT"
        elif udt_name == "bool" or data_type == "boolean":
            type_str = "BOOLEAN"
        elif udt_name == "text" or data_type == "text":
            type_str = "TEXT"
        elif udt_name == "date" or data_type == "date":
            type_str = "DATE"
        elif udt_name == "timestamptz" or data_type == "timestamp with time zone":
            type_str = "TIMESTAMPTZ"
        elif udt_name == "timestamp" or data_type == "timestamp without time zone":
            type_str = "TIMESTAMP"
        elif udt_name == "numeric" or data_type == "numeric":
            if numeric_precision is not None and numeric_scale is not None:
                type_str = f"NUMERIC({numeric_precision},{numeric_scale})"
            elif numeric_precision is not None:
                type_str = f"NUMERIC({numeric_precision})"
            else:
                type_str = "NUMERIC"
        elif data_type == "character varying" or udt_name == "varchar":
            if char_max_len:
                type_str = f"VARCHAR({char_max_len})"
            else:
                type_str = "VARCHAR"
        elif data_type == "character" or udt_name == "bpchar":
            if char_max_len:
                type_str = f"CHAR({char_max_len})"
            else:
                type_str = "CHAR"
        elif udt_name == "jsonb":
            type_str = "JSONB"
        elif udt_name == "json":
            type_str = "JSON"
        elif udt_name == "uuid":
            type_str = "UUID"
        elif udt_name == "float4":
            type_str = "REAL"
        elif udt_name == "float8" or data_type == "double precision":
            type_str = "DOUBLE PRECISION"
        else:
            # Fallback: use the udt_name uppercased
            type_str = udt_name.upper() if udt_name else data_type.upper()

        # Build column definition
        parts = [f"  {col_name}", type_str]

        # NOT NULL
        if is_nullable == "NO" and col_name not in pk_columns:
            parts.append("NOT NULL")

        # PRIMARY KEY (inline for single-column PK)
        if len(pk_columns) == 1 and col_name == pk_columns[0]:
            parts.append("PRIMARY KEY")

        # UNIQUE (inline for single-column unique constraints)
        if col_name in single_col_uniques:
            parts.append("UNIQUE")

        # DEFAULT (skip for serial columns since SERIAL implies the sequence)
        if col_default and not is_serial:
            parts.append(f"DEFAULT {col_default}")

        col_defs.append(" ".join(parts))

    # --- Build table-level constraints ---
    constraints = []

    # Composite PRIMARY KEY (more than one column)
    if len(pk_columns) > 1:
        pk_str = ", ".join(pk_columns)
        constraints.append(f"  PRIMARY KEY ({pk_str})")

    # Multi-column UNIQUE constraints
    for cname, cols in unique_constraints.items():
        if len(cols) > 1:
            cols_str = ", ".join(cols)
            constraints.append(f"  UNIQUE({cols_str})")

    # FOREIGN KEY constraints
    for cname, fk_info in fk_constraints.items():
        fk_cols = ", ".join(fk_info["columns"])
        ref_cols = ", ".join(fk_info["ref_columns"])
        ref_table = fk_info["ref_table"]
        fk_def = f"  FOREIGN KEY ({fk_cols}) REFERENCES {ref_table}({ref_cols})"
        if fk_info["on_delete"] and fk_info["on_delete"] != "NO ACTION":
            fk_def += f" ON DELETE {fk_info['on_delete']}"
        if fk_info["on_update"] and fk_info["on_update"] != "NO ACTION":
            fk_def += f" ON UPDATE {fk_info['on_update']}"
        constraints.append(fk_def)

    # CHECK constraints
    for cname, check_clause in check_constraints.items():
        constraints.append(f"  CHECK ({check_clause})")

    # --- Assemble CREATE TABLE ---
    all_parts = col_defs + constraints
    body = ",\n".join(all_parts)
    ddl = f"CREATE TABLE IF NOT EXISTS {table_name} (\n{body}\n);"

    return ddl


def _escape_sql_value(value) -> str:
    """Escape a Python value for inclusion in a SQL INSERT statement.

    Handles:
    - None -> NULL
    - bool -> TRUE/FALSE
    - int, float, Decimal -> unquoted numeric literal
    - datetime, date -> quoted string representation
    - str -> quoted with single-quote escaping (''), backslash escaping,
             newline/carriage-return escaping, and unicode preserved as-is
    - bytes -> hex literal
    - All other types -> quoted via str() with escaping
    """
    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    if isinstance(value, (int, float, Decimal)):
        return str(value)

    if isinstance(value, datetime):
        return f"'{value.isoformat()}'"

    if isinstance(value, date):
        return f"'{value.isoformat()}'"

    if isinstance(value, bytes):
        return f"'\\x{value.hex()}'"

    # Default: treat as string
    s = str(value)
    # Escape backslashes first (before other escape sequences)
    s = s.replace("\\", "\\\\")
    # Escape single quotes by doubling them
    s = s.replace("'", "''")
    # Escape newlines and carriage returns
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    # Use E'' syntax if we have escape sequences
    if "\\\\" in s or "\\n" in s or "\\r" in s:
        return f"E'{s}'"
    return f"'{s}'"


def generate_inserts(conn, table_name: str) -> str:
    """Generate INSERT INTO statements for all rows in the given table.

    Selects all rows and formats them as INSERT statements with proper
    value escaping. Returns an empty string if the table has no rows.
    """
    # Get column names for the table
    cols_result = conn.execute(
        text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table_name
            ORDER BY ordinal_position
        """),
        {"table_name": table_name},
    )
    column_names = [row[0] for row in cols_result]

    if not column_names:
        return ""

    # Select all rows from the table
    rows = conn.execute(text(f'SELECT * FROM "{table_name}"')).fetchall()

    if not rows:
        return ""

    # Build INSERT statements
    col_list = ", ".join(column_names)
    value_rows = []
    for row in rows:
        values = ", ".join(_escape_sql_value(v) for v in row)
        value_rows.append(f"({values})")

    # Format as a single INSERT with multiple value rows for efficiency
    insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES\n"
    insert_sql += ",\n".join(value_rows)
    insert_sql += ";"

    return insert_sql


# ---------------------------------------------------------------------------
# Core utility functions
# ---------------------------------------------------------------------------


def get_table_order(conn) -> list[str]:
    """Return public-schema tables in dependency order (parents before children).

    Queries information_schema for foreign key relationships, builds a directed
    dependency graph, and performs a topological sort using Kahn's algorithm.
    Referenced (parent) tables appear before the tables that reference them.
    """

    # 1. Get all tables in the public schema
    all_tables_result = conn.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            """
        )
    )
    all_tables: set[str] = {row[0] for row in all_tables_result}

    if not all_tables:
        return []

    # 2. Query FK relationships to build dependency edges
    fk_result = conn.execute(
        text(
            """
            SELECT
                tc.table_name AS child_table,
                ccu.table_name AS parent_table
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.constraint_schema = ccu.constraint_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
              AND ccu.table_schema = 'public'
            """
        )
    )

    # 3. Build adjacency list and in-degree count
    # Edge: parent -> child (parent must come before child in output)
    from collections import defaultdict, deque

    adjacency: dict[str, set[str]] = defaultdict(set)
    in_degree: dict[str, int] = {table: 0 for table in all_tables}

    for row in fk_result:
        child_table = row[0]
        parent_table = row[1]

        # Skip self-referencing FKs
        if child_table == parent_table:
            continue

        # Only consider tables in public schema that we know about
        if child_table not in all_tables or parent_table not in all_tables:
            continue

        # Avoid duplicate edges
        if child_table not in adjacency[parent_table]:
            adjacency[parent_table].add(child_table)
            in_degree[child_table] += 1

    # 4. Kahn's algorithm for topological sort
    queue: deque[str] = deque()
    for table in all_tables:
        if in_degree[table] == 0:
            queue.append(table)

    # Sort the initial queue for deterministic output
    queue = deque(sorted(queue))

    ordered: list[str] = []
    while queue:
        table = queue.popleft()
        ordered.append(table)

        # Process children in sorted order for determinism
        for child in sorted(adjacency[table]):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    # If there are remaining tables (cycle), append them at the end
    remaining = sorted(all_tables - set(ordered))
    ordered.extend(remaining)

    return ordered


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def cleanup_old_backups() -> None:
    """Remove .sql backup files older than 1 hour from the backup directory."""
    backup_dir = settings.db_tools_backup_dir

    if not os.path.isdir(backup_dir):
        return

    now = datetime.now()
    cutoff = timedelta(hours=1)

    for filename in os.listdir(backup_dir):
        if not filename.endswith(".sql"):
            continue

        filepath = os.path.join(backup_dir, filename)

        if not os.path.isfile(filepath):
            continue

        try:
            mtime = os.path.getmtime(filepath)
            file_age = now - datetime.fromtimestamp(mtime)

            if file_age > cutoff:
                os.remove(filepath)
                logger.debug("Deleted old backup file: %s", filename)
        except OSError as exc:
            logger.debug("Could not process backup file %s: %s", filename, exc)
