"""
Core database functionality: Engine creation, session management, and migrations.
"""

import logging
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .models import Base

logger = logging.getLogger(__name__)

# Default Database Location
HISTORY_DIR = Path.home() / ".config" / "vociferous"
HISTORY_DB = HISTORY_DIR / "vociferous.db"


class DatabaseCore:
    """Manages SQLAlchemy engine, sessions, and schema migrations."""

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the database core."""
        self.db_path = db_path or HISTORY_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{self.db_path}")
        self.Session = sessionmaker(bind=self.engine)

        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Initialize database schema and perform migrations."""
        self._check_legacy_schema()
        self._handle_pre_create_migrations()
        
        # Create tables
        Base.metadata.create_all(self.engine)
        
        self._run_micro_migrations()
        self._enable_foreign_keys()

    def _handle_pre_create_migrations(self) -> None:
        """Run migrations that must occur before table creation (e.g. renames)."""
        from sqlalchemy import inspect
        
        try:
            inspector = inspect(self.engine)
            table_names = inspector.get_table_names()
            
            # Migration: Rename focus_groups -> projects
            if "focus_groups" in table_names:
                if "projects" not in table_names:
                    # Simple rename
                    logger.info("Migrating schema: Renaming focus_groups to projects")
                    with self.engine.connect() as conn:
                        conn.execute(text("ALTER TABLE focus_groups RENAME TO projects"))
                        conn.commit()
                else:
                    # Both exist. Check if projects is empty (likely created by earlier failed run).
                    with self.engine.connect() as conn:
                        count = conn.execute(text("SELECT COUNT(*) FROM projects")).scalar()
                        if count == 0:
                            logger.info("Found empty projects table and existing focus_groups. Replacing projects with focus_groups.")
                            conn.execute(text("DROP TABLE projects"))
                            conn.execute(text("ALTER TABLE focus_groups RENAME TO projects"))
                            conn.commit()
                        else:
                            logger.warning("Both focus_groups and projects tables exist and contain data. Manual intervention required to merge.")

        except Exception as e:
            logger.warning(f"Pre-create migration failed: {e}")

    def _check_legacy_schema(self) -> None:
        """Check for and remove legacy schema."""
        try:
            from sqlalchemy import inspect

            inspector = inspect(self.engine)
            if "schema_version" in inspector.get_table_names():
                logger.info(
                    "Legacy database detected. Performing complete reset (nuke) as requested."
                )
                Base.metadata.drop_all(self.engine)
                with self.engine.connect() as conn:
                    conn.execute(text("DROP TABLE IF EXISTS schema_version"))
                    conn.commit()
        except Exception as e:
            logger.warning(
                f"Error checking for legacy schema: {e}. Proceeding with creation."
            )

    def _run_micro_migrations(self) -> None:
        """Run safe schema updates for existing databases."""
        from sqlalchemy import inspect
        
        inspector = inspect(self.engine)
        table_names = inspector.get_table_names()

        # Migration: Rename transcripts.focus_group_id -> project_id
        if "transcripts" in table_names:
            columns = [c["name"] for c in inspector.get_columns("transcripts")]
            if "focus_group_id" in columns and "project_id" not in columns:
                logger.info("Migrating schema: Renaming transcripts.focus_group_id to project_id")
                with self.engine.connect() as conn:
                    try:
                        conn.execute(text("ALTER TABLE transcripts RENAME COLUMN focus_group_id TO project_id"))
                        conn.commit()
                    except Exception as e:
                        logger.error(f"Failed to rename focus_group_id column: {e}")
        
        # Migration: v2.2.1 - Add parent_id to projects
        try:
            if "projects" in inspector.get_table_names(): # Re-check table names or assume it exists/was renamed
                columns = [c["name"] for c in inspector.get_columns("projects")]
                if "parent_id" not in columns:
                    logger.info("Migrating schema: Adding parent_id to projects")
                    with self.engine.connect() as conn:
                        conn.execute(
                            text(
                                "ALTER TABLE projects ADD COLUMN parent_id INTEGER REFERENCES projects(id)"
                            )
                        )
                        conn.commit()
        except Exception as e:
            logger.warning(f"Migration failed (projects): {e}")

        # Migration: v3.0 - Add current_variant_id to transcripts
        try:
            if "transcripts" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("transcripts")]
                if "current_variant_id" not in columns:
                    logger.info(
                        "Migrating schema: Adding current_variant_id to transcripts"
                    )
                    with self.engine.connect() as conn:
                        conn.execute(
                            text(
                                "ALTER TABLE transcripts ADD COLUMN current_variant_id INTEGER"
                            )
                        )
                        conn.commit()
        except Exception as e:
            logger.warning(f"Migration failed (transcripts): {e}")

    def _enable_foreign_keys(self) -> None:
        """Enforce foreign key constraints (SQLite specific)."""
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))

    def get_session(self):
        """Provide a session context manager."""
        return self.Session()

