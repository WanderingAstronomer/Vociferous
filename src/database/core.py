"""
Core database functionality: Engine creation, session management, and migrations.

Migrations are tracked via a ``schema_version`` table so that each migration is
applied exactly once, in order.  Every migration runs inside a transaction;
a failure rolls back the single migration and halts the sequence.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from sqlalchemy import create_engine, text, Connection, inspect
from sqlalchemy.orm import sessionmaker

from src.core.resource_manager import ResourceManager
from .models import Base

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema version tracking
# ---------------------------------------------------------------------------

_SCHEMA_VERSION_DDL = (
    "CREATE TABLE IF NOT EXISTS schema_version ("
    "  id INTEGER PRIMARY KEY CHECK (id = 1),"
    "  version INTEGER NOT NULL DEFAULT 0"
    ")"
)


def _get_schema_version(conn: Connection) -> int:
    """Return the current schema version (0 if table does not exist yet)."""
    tables = inspect(conn).get_table_names()
    if "schema_version" not in tables:
        return 0
    row = conn.execute(text("SELECT version FROM schema_version WHERE id = 1")).first()
    return int(row[0]) if row else 0


def _set_schema_version(conn: Connection, version: int) -> None:
    """Upsert the schema version row."""
    conn.execute(text(_SCHEMA_VERSION_DDL))
    conn.execute(
        text(
            "INSERT INTO schema_version (id, version) VALUES (1, :v) "
            "ON CONFLICT(id) DO UPDATE SET version = :v"
        ),
        {"v": version},
    )


# ---------------------------------------------------------------------------
# Migration registry
# ---------------------------------------------------------------------------
# Each migration is a callable(conn) that receives an *active* connection
# inside a transaction.  Return normally on success; raise to abort.
#
# Migrations are keyed by version number.  The current schema version is the
# highest migration that has been applied.  Only migrations with version >
# current schema version will run.
#
# IMPORTANT: existing databases that pre-date this versioning system already
# have all these migrations applied (via the old ad-hoc approach).  When the
# schema_version table is absent, we detect the existing state and seed the
# version appropriately (see _bootstrap_version_for_existing_dbs).


def _migration_v1_rename_focus_groups(conn: Connection) -> None:
    """Rename legacy focus_groups table to projects."""
    tables = inspect(conn).get_table_names()
    if "focus_groups" not in tables:
        return  # Nothing to do
    if "projects" not in tables:
        logger.info("Migration v1: Renaming focus_groups → projects")
        conn.execute(text("ALTER TABLE focus_groups RENAME TO projects"))
    else:
        count = conn.execute(text("SELECT COUNT(*) FROM projects")).scalar()
        if count == 0:
            logger.info("Migration v1: Replacing empty projects with focus_groups")
            conn.execute(text("DROP TABLE projects"))
            conn.execute(text("ALTER TABLE focus_groups RENAME TO projects"))
        else:
            logger.warning(
                "Migration v1: Both focus_groups and projects contain data. "
                "Manual merge required."
            )


def _migration_v2_rename_focus_group_id(conn: Connection) -> None:
    """Rename transcripts.focus_group_id → project_id."""
    tables = inspect(conn).get_table_names()
    if "transcripts" not in tables:
        return
    columns = [c["name"] for c in inspect(conn).get_columns("transcripts")]
    if "focus_group_id" in columns and "project_id" not in columns:
        logger.info("Migration v2: Renaming transcripts.focus_group_id → project_id")
        conn.execute(
            text("ALTER TABLE transcripts RENAME COLUMN focus_group_id TO project_id")
        )


def _migration_v3_add_parent_id(conn: Connection) -> None:
    """Add parent_id column to projects."""
    tables = inspect(conn).get_table_names()
    if "projects" not in tables:
        return
    columns = [c["name"] for c in inspect(conn).get_columns("projects")]
    if "parent_id" not in columns:
        logger.info("Migration v3: Adding parent_id to projects")
        conn.execute(
            text(
                "ALTER TABLE projects ADD COLUMN parent_id INTEGER REFERENCES projects(id)"
            )
        )


def _migration_v4_add_variant_fields(conn: Connection) -> None:
    """Add current_variant_id and display_name to transcripts."""
    tables = inspect(conn).get_table_names()
    if "transcripts" not in tables:
        return
    columns = [c["name"] for c in inspect(conn).get_columns("transcripts")]
    if "current_variant_id" not in columns:
        logger.info("Migration v4: Adding current_variant_id to transcripts")
        conn.execute(
            text("ALTER TABLE transcripts ADD COLUMN current_variant_id INTEGER")
        )
    if "display_name" not in columns:
        logger.info("Migration v4: Adding display_name to transcripts")
        conn.execute(
            text("ALTER TABLE transcripts ADD COLUMN display_name VARCHAR")
        )


# Ordered list of versioned migrations.  Keys MUST be sequential starting at 1.
_MIGRATIONS: list[tuple[int, str, Callable[[Connection], None]]] = [
    (1, "rename_focus_groups_to_projects", _migration_v1_rename_focus_groups),
    (2, "rename_focus_group_id_column", _migration_v2_rename_focus_group_id),
    (3, "add_parent_id_to_projects", _migration_v3_add_parent_id),
    (4, "add_variant_fields_to_transcripts", _migration_v4_add_variant_fields),
]

LATEST_SCHEMA_VERSION = _MIGRATIONS[-1][0] if _MIGRATIONS else 0


# ---------------------------------------------------------------------------
# DatabaseCore
# ---------------------------------------------------------------------------


class DatabaseCore:
    """Manages SQLAlchemy engine, sessions, and schema migrations."""

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the database core."""
        if db_path:
            self.db_path = db_path
        else:
            # Prefer XDG_DATA_HOME, fallback to generic config dir if it exists there (legacy)
            modern_path = ResourceManager.get_user_data_dir() / "vociferous.db"
            legacy_path = ResourceManager.get_user_config_dir() / "vociferous.db"

            if legacy_path.exists() and not modern_path.exists():
                logger.info(f"Detected legacy DB at {legacy_path}, using it.")
                self.db_path = legacy_path
            else:
                self.db_path = modern_path

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{self.db_path}")
        self.Session = sessionmaker(bind=self.engine)

        self._initialize_schema()

    # ------------------------------------------------------------------
    # Schema lifecycle
    # ------------------------------------------------------------------

    def _initialize_schema(self) -> None:
        """Initialize database schema and perform versioned migrations."""
        # Pre-create migrations (v1) must run before create_all
        self._run_pre_create_migrations()

        # Create/update ORM tables
        Base.metadata.create_all(self.engine)

        # Ensure schema_version table exists and bootstrap version for
        # databases that pre-date the versioning system.
        self._ensure_version_table()

        # Run any pending migrations
        self._run_versioned_migrations()

        self._enable_sqlite_features()

    def _ensure_version_table(self) -> None:
        """Create the schema_version table and seed the version for existing DBs."""
        with self.engine.begin() as conn:
            conn.execute(text(_SCHEMA_VERSION_DDL))
            current = _get_schema_version(conn)
            if current == 0:
                # Detect whether this is a brand-new DB or a pre-existing one
                tables = inspect(conn).get_table_names()
                if "transcripts" in tables:
                    # Existing database — all old ad-hoc migrations already applied
                    logger.info(
                        "Bootstrapping schema_version for existing database → v%d",
                        LATEST_SCHEMA_VERSION,
                    )
                    _set_schema_version(conn, LATEST_SCHEMA_VERSION)
                else:
                    # Fresh database — start at v0 (create_all just created tables)
                    _set_schema_version(conn, LATEST_SCHEMA_VERSION)

    def _run_pre_create_migrations(self) -> None:
        """Run migrations that must execute before ``create_all`` (table renames)."""
        # Only v1 (focus_groups → projects) needs to run before create_all
        with self.engine.begin() as conn:
            current = _get_schema_version(conn)
            if current < 1:
                tables = inspect(conn).get_table_names()
                if "focus_groups" in tables:
                    try:
                        _migration_v1_rename_focus_groups(conn)
                    except Exception as e:
                        logger.error("Pre-create migration v1 failed: %s", e)
                        raise

    def _run_versioned_migrations(self) -> None:
        """Apply each pending migration inside its own transaction."""
        with self.engine.begin() as conn:
            current = _get_schema_version(conn)

        for version, label, fn in _MIGRATIONS:
            if version <= current:
                continue
            logger.info("Applying migration v%d: %s", version, label)
            try:
                with self.engine.begin() as conn:
                    fn(conn)
                    _set_schema_version(conn, version)
                logger.info("Migration v%d applied successfully.", version)
            except Exception:
                logger.exception(
                    "Migration v%d (%s) failed — halting migration sequence.", version, label
                )
                raise

    def _enable_sqlite_features(self) -> None:
        """Enable SQLite-specific features (WAL, foreign keys)."""
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.execute(text("PRAGMA journal_mode = WAL"))
            conn.commit()

    def get_session(self):
        """Provide a session context manager."""
        return self.Session()
