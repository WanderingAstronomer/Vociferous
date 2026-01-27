"""
Core database functionality: Engine creation, session management, and migrations.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.core.resource_manager import ResourceManager
from .models import Base

logger = logging.getLogger(__name__)


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

    def _initialize_schema(self) -> None:
        """Initialize database schema and perform migrations."""
        self._check_legacy_schema()
        self._handle_pre_create_migrations()

        # Create tables
        Base.metadata.create_all(self.engine)

        self._run_micro_migrations()
        self._enable_sqlite_features()

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
                        conn.execute(
                            text("ALTER TABLE focus_groups RENAME TO projects")
                        )
                        conn.commit()
                else:
                    # Both exist. Check if projects is empty (likely created by earlier failed run).
                    with self.engine.connect() as conn:
                        count = conn.execute(
                            text("SELECT COUNT(*) FROM projects")
                        ).scalar()
                        if count == 0:
                            logger.info(
                                "Found empty projects table and existing focus_groups. Replacing projects with focus_groups."
                            )
                            conn.execute(text("DROP TABLE projects"))
                            conn.execute(
                                text("ALTER TABLE focus_groups RENAME TO projects")
                            )
                            conn.commit()
                        else:
                            logger.warning(
                                "Both focus_groups and projects tables exist and contain data. Manual intervention required to merge."
                            )

        except Exception as e:
            logger.warning(f"Pre-create migration failed: {e}")

    def _check_legacy_schema(self) -> None:
        """
        Check for legacy schema_version table and handle migration safely.
        
        Instead of destructively dropping all tables, this method:
        1. Creates a timestamped backup if legacy schema is detected
        2. Attempts to migrate data if transcripts table exists
        3. Only resets if migration is impossible
        """
        try:
            from sqlalchemy import inspect

            inspector = inspect(self.engine)
            table_names = inspector.get_table_names()
            
            if "schema_version" not in table_names:
                # No legacy schema detected, proceed normally
                return
            
            logger.info("Legacy database detected (schema_version table present).")
            
            # Initialize backup_path to None - will be set if backup is created
            backup_path: Path | None = None
            
            # Check if we have any data to preserve
            has_transcripts = "transcripts" in table_names
            has_data = False
            
            if has_transcripts:
                try:
                    with self.engine.connect() as conn:
                        count = conn.execute(text("SELECT COUNT(*) FROM transcripts")).scalar()
                        has_data = count > 0 if count else False
                except Exception as e:
                    logger.warning(f"Could not check transcript count: {e}")
                    has_data = False
            
            # Create backup before any destructive operation
            if has_data or has_transcripts:
                backup_path = self._create_backup()
                if backup_path:
                    logger.info(f"Created database backup: {backup_path}")
                else:
                    logger.warning("Failed to create backup, but proceeding with migration")
            
            # Try to migrate if we have transcripts table
            if has_transcripts:
                try:
                    # Check if transcripts table has compatible schema
                    columns = [c["name"] for c in inspector.get_columns("transcripts")]
                    required_columns = ["id", "timestamp", "raw_text", "normalized_text"]
                    has_required = all(col in columns for col in required_columns)
                    
                    if has_required:
                        logger.info(
                            "Legacy transcripts table has compatible schema. "
                            "Migrating in place (removing schema_version only)."
                        )
                        # Just remove schema_version, keep the data
                        with self.engine.connect() as conn:
                            conn.execute(text("DROP TABLE IF EXISTS schema_version"))
                            conn.commit()
                        return
                    else:
                        logger.warning(
                            "Legacy transcripts table has incompatible schema. "
                            "Cannot migrate data safely."
                        )
                except Exception as e:
                    logger.error(f"Error checking transcript schema: {e}")
                    logger.warning("Cannot migrate safely, will reset database")
            
            # If we get here, migration is not possible or failed
            # Only reset if we successfully created a backup or if there's no data
            if has_data and not backup_path:
                # Don't destroy data without backup
                raise RuntimeError(
                    "Legacy database detected with data, but backup creation failed. "
                    "Please manually backup your database before upgrading. "
                    f"Database location: {self.db_path}"
                )
            
            logger.warning(
                "Resetting legacy database schema. "
                f"{'Backup created at: ' + str(backup_path) if backup_path else 'No data to preserve.'}"
            )
            Base.metadata.drop_all(self.engine)
            with self.engine.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS schema_version"))
                conn.commit()
                
        except RuntimeError:
            # Re-raise RuntimeError (backup failure)
            raise
        except Exception as e:
            logger.warning(
                f"Error checking for legacy schema: {e}. Proceeding with creation."
            )
    
    def _create_backup(self) -> Path | None:
        """
        Create a timestamped backup of the database file.
        
        Returns:
            Path to backup file if successful, None otherwise.
        """
        if not self.db_path.exists():
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.db_path.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            backup_path = backup_dir / f"vociferous_backup_{timestamp}.db"
            shutil.copy2(self.db_path, backup_path)
            
            # Keep only last 5 backups to avoid disk space issues
            backups = sorted(backup_dir.glob("vociferous_backup_*.db"), reverse=True)
            for old_backup in backups[5:]:
                try:
                    old_backup.unlink()
                    logger.debug(f"Removed old backup: {old_backup}")
                except Exception:
                    pass
            
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create database backup: {e}")
            return None

    def _run_micro_migrations(self) -> None:
        """Run safe schema updates for existing databases."""
        from sqlalchemy import inspect

        inspector = inspect(self.engine)
        table_names = inspector.get_table_names()

        # Migration: Rename transcripts.focus_group_id -> project_id
        if "transcripts" in table_names:
            columns = [c["name"] for c in inspector.get_columns("transcripts")]
            if "focus_group_id" in columns and "project_id" not in columns:
                logger.info(
                    "Migrating schema: Renaming transcripts.focus_group_id to project_id"
                )
                with self.engine.connect() as conn:
                    try:
                        conn.execute(
                            text(
                                "ALTER TABLE transcripts RENAME COLUMN focus_group_id TO project_id"
                            )
                        )
                        conn.commit()
                    except Exception as e:
                        logger.error(f"Failed to rename focus_group_id column: {e}")

        # Migration: v2.2.1 - Add parent_id to projects
        try:
            if (
                "projects" in inspector.get_table_names()
            ):  # Re-check table names or assume it exists/was renamed
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

                if "display_name" not in columns:
                    logger.info("Migrating schema: Adding display_name to transcripts")
                    with self.engine.connect() as conn:
                        conn.execute(
                            text(
                                "ALTER TABLE transcripts ADD COLUMN display_name VARCHAR"
                            )
                        )
                        conn.commit()
        except Exception as e:
            logger.warning(f"Migration failed (transcripts): {e}")

    def _enable_sqlite_features(self) -> None:
        """Enable SQLite-specific features (WAL, foreign keys)."""
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.execute(text("PRAGMA journal_mode = WAL"))
            conn.commit()

    def get_session(self):
        """Provide a session context manager."""
        return self.Session()
