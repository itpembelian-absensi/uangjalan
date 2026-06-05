# Requirements Document

## Introduction

This feature provides API endpoints for backing up and restoring the PostgreSQL database (`uang_pengiriman`) used by the Uang Jalan application. The feature is implemented entirely in Python (no external CLI tools like `pg_dump` required), making it portable across all operating systems. The backup produces a SQL dump file containing DDL and INSERT statements, and the restore executes that SQL to recreate the database state. These endpoints are only available in development mode (controlled by an environment variable) and do not require user authentication.

## Glossary

- **Backup_Service**: The Python module responsible for connecting to the database, extracting schema and data, and producing a SQL dump file.
- **Restore_Service**: The Python module responsible for receiving an uploaded SQL dump file and executing the SQL statements against the database to restore its state.
- **Dump_File**: A SQL text file containing DDL statements (CREATE TABLE, etc.) and INSERT statements representing all data in the database.
- **API_Gateway**: The FastAPI application serving the `/api` route prefix.
- **Dev_Mode**: A boolean configuration flag (`ENABLE_DB_TOOLS`) set in the environment variables. When `true`, the backup and restore endpoints are active. When `false` or absent, the endpoints are disabled and return HTTP 404.
- **Background_Task**: A FastAPI background task that runs the backup process asynchronously so the user does not block waiting for the dump to complete.
- **DB_Connection**: The database connection established using the existing `DATABASE_URL` environment variable via SQLAlchemy/psycopg2.

## Requirements

### Requirement 1: Dev-Mode Gating

**User Story:** As a developer, I want backup and restore endpoints to only be available during development, so that these dangerous operations are never exposed in production.

#### Acceptance Criteria

1. THE API_Gateway SHALL register the backup and restore endpoints only when the `ENABLE_DB_TOOLS` environment variable is set to `true`.
2. WHEN `ENABLE_DB_TOOLS` is not set or is set to any value other than `true`, THE API_Gateway SHALL NOT expose the backup and restore endpoints (requests to those paths SHALL return HTTP 404).
3. THE API_Gateway SHALL NOT require user authentication or session validation for backup and restore endpoints when Dev_Mode is active.

### Requirement 2: Connection Test on Load

**User Story:** As a developer, I want the system to automatically verify that the database is reachable when the module loads, so that I immediately know whether backup/restore operations will work.

#### Acceptance Criteria

1. WHEN the backup/restore module is initialized and Dev_Mode is active, THE Backup_Service SHALL attempt a test connection to the database using the DB_Connection (executing a simple query like `SELECT 1`).
2. IF the database is reachable, THEN THE Backup_Service SHALL log an info message indicating the database tools are ready.
3. IF the database is unreachable, THEN THE Backup_Service SHALL log a warning message describing the connection error.
4. WHEN a GET request is sent to the db-tools status endpoint, THE Backup_Service SHALL return a JSON response indicating whether the database connection is currently healthy, along with the database name and host.

### Requirement 3: Database Backup (Background Process)

**User Story:** As a developer, I want to trigger a database backup that runs in the background, so that I can download the dump file without waiting for the full export process to complete on the initial request.

#### Acceptance Criteria

1. WHEN a POST request is sent to the backup trigger endpoint, THE Backup_Service SHALL start the backup process as a Background_Task and immediately return an HTTP 202 response with a JSON body containing a unique `backup_id` and a `status` field set to `"in_progress"`.
2. THE Backup_Service SHALL connect to the database using Python (SQLAlchemy or psycopg2) and generate a SQL dump containing all table schemas (CREATE TABLE statements with constraints and indexes) and all data (INSERT statements).
3. THE Backup_Service SHALL export tables in dependency order (respecting foreign key relationships) to ensure the dump can be restored without constraint violations.
4. WHEN a GET request is sent to the backup status endpoint with a valid `backup_id`, THE Backup_Service SHALL return the current status of the backup (`in_progress`, `completed`, or `failed`).
5. WHEN the backup status is `completed`, THE Backup_Service SHALL include a `download_url` field in the status response pointing to the download endpoint for that specific backup, and the file size in bytes.
6. WHEN a GET request is sent to the backup download endpoint with a valid `backup_id` whose status is `completed`, THE Backup_Service SHALL stream the Dump_File as a downloadable response with Content-Type `application/sql`.
7. IF the backup process encounters an error (connection failure, permission error, etc.), THEN THE Backup_Service SHALL set the backup status to `failed` and include a descriptive error message in the status response.
8. IF a `backup_id` is not found, THEN THE Backup_Service SHALL return an HTTP 404 response.

### Requirement 4: Backup File Metadata

**User Story:** As a developer, I want the backup filename to contain meaningful metadata, so that I can easily identify when the backup was created.

#### Acceptance Criteria

1. THE Backup_Service SHALL generate the backup filename using the pattern `uang_pengiriman_YYYY-MM-DDTHH-MM-SS.sql` where the timestamp represents the server's current local time at the moment the backup is initiated.
2. THE Backup_Service SHALL set the Content-Disposition header with the generated filename when serving the download.

### Requirement 5: Database Restore from Upload

**User Story:** As a developer, I want to upload a SQL dump file and choose a restore mode, so that I can recover data, reset the schema, or fully restore the database during development.

#### Acceptance Criteria

1. WHEN a valid Dump_File is uploaded to the restore endpoint via a POST request with multipart form data, THE Restore_Service SHALL read the file content and execute the SQL statements against the database using the DB_Connection.
2. THE Restore_Service SHALL support three restore modes via a `mode` form field: `full` (default — drops all tables and recreates schema and data), `schema_only` (drops and recreates tables without inserting data), and `data_only` (truncates tables and inserts data without modifying the schema).
3. WHEN mode is `full`, THE Restore_Service SHALL drop all existing tables (in reverse dependency order), then execute all DDL and INSERT statements from the dump file.
4. WHEN mode is `schema_only`, THE Restore_Service SHALL drop all existing tables (in reverse dependency order), then execute only the DDL statements (CREATE TABLE, CREATE INDEX, etc.) from the dump file.
5. WHEN mode is `data_only`, THE Restore_Service SHALL truncate all existing tables (in reverse dependency order respecting foreign keys), then execute only the INSERT statements from the dump file.
6. WHEN the restore operation completes successfully, THE Restore_Service SHALL return an HTTP 200 response with a JSON body containing a success message, the restore mode used, and the timestamp of the restore operation.
7. IF the uploaded file is empty or has zero bytes, THEN THE Restore_Service SHALL return an HTTP 400 response with the message "File backup kosong atau tidak valid".
8. IF the SQL execution encounters an error, THEN THE Restore_Service SHALL rollback the transaction and return an HTTP 500 response with a descriptive error message.
9. THE Restore_Service SHALL accept only files with a maximum size of 100 MB.
10. IF the uploaded file exceeds 100 MB, THEN THE Restore_Service SHALL return an HTTP 413 response with the message "Ukuran file melebihi batas maksimum 100 MB".
11. THE Restore_Service SHALL execute the restore within a single database transaction to ensure atomicity (all-or-nothing).

### Requirement 6: Restore Safety Confirmation

**User Story:** As a developer, I want the restore endpoint to require explicit confirmation, so that accidental restores that would overwrite current data are prevented.

#### Acceptance Criteria

1. THE Restore_Service SHALL require a `confirm` field in the multipart form data with the value `true` before proceeding with the restore operation.
2. IF the `confirm` field is missing or has a value other than `true`, THEN THE Restore_Service SHALL return an HTTP 400 response with the message "Konfirmasi restore diperlukan. Kirim field 'confirm' dengan nilai 'true'".

### Requirement 7: Backup Cleanup

**User Story:** As a developer, I want completed backup files to be automatically cleaned up, so that disk space is not consumed indefinitely by old backup files.

#### Acceptance Criteria

1. THE Backup_Service SHALL store backup files in a temporary directory on the backend server.
2. THE Backup_Service SHALL automatically delete backup files that are older than 1 hour.
3. WHEN a new backup is triggered, THE Backup_Service SHALL remove any previously completed backup files before starting the new backup process.
