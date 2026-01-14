import logging
from sqlalchemy import delete, select, update, func
from database.core import DatabaseCore
from database.models import Project, Transcript

logger = logging.getLogger(__name__)

class ProjectRepository:
    def __init__(self, db_core: DatabaseCore):
        self.db = db_core

    def create(
        self, name: str, color: str | None = None, parent_id: int | None = None
    ) -> int | None:
        """Create a new Project."""
        try:
            with self.db.get_session() as session:
                group = Project(name=name, color=color, parent_id=parent_id)
                session.add(group)
                session.commit()
                return group.id

        except Exception as e:
            logger.error(f"Failed to create Project: {e}")
            return None

    def get_all(self) -> list[tuple[int, str, str | None, int | None]]:
        """Get all Projects."""
        try:
            with self.db.get_session() as session:
                stmt = select(Project).order_by(Project.created_at.asc())
                groups = session.execute(stmt).scalars().all()
                return [(g.id, g.name, g.color, g.parent_id) for g in groups]

        except Exception as e:
            logger.error(f"Failed to get Projects: {e}")
            return []

    def rename(self, project_id: int, new_name: str) -> bool:
        """Rename a Project."""
        try:
            with self.db.get_session() as session:
                stmt = (
                    update(Project)
                    .where(Project.id == project_id)
                    .values(name=new_name)
                )
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:
                    logger.info(f"Renamed Project {project_id} to '{new_name}'")
                    return True
                else:
                    logger.warning(f"Project {project_id} not found")
                    return False

        except Exception as e:
            logger.error(f"Failed to rename Project: {e}")
            return False

    def update_color(self, project_id: int, color: str | None) -> bool:
        """Update a Project's accent color."""
        try:
            with self.db.get_session() as session:
                stmt = (
                    update(Project)
                    .where(Project.id == project_id)
                    .values(color=color)
                )
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:
                    logger.info(
                        f"Updated Project {project_id} color to '{color}'"
                    )
                    return True
                else:
                    logger.warning(f"Project {project_id} not found")
                    return False

        except Exception as e:
            logger.error(f"Failed to update Project color: {e}")
            return False

    def delete(
        self, project_id: int, move_to_unassigned: bool = True
    ) -> bool:
        """Delete a Project."""
        try:
            with self.db.get_session() as session:
                # Check if group has transcripts
                stmt_count = select(func.count(Transcript.id)).where(
                    Transcript.project_id == project_id
                )
                count = session.execute(stmt_count).scalar() or 0

                if count > 0 and not move_to_unassigned:
                    logger.warning(
                        f"Cannot delete Project {project_id}: "
                        f"contains {count} transcripts"
                    )
                    return False

                if count > 0 and move_to_unassigned:
                    update_stmt = (
                        update(Transcript)
                        .where(Transcript.project_id == project_id)
                        .values(project_id=None)
                    )
                    session.execute(update_stmt)

                stmt = delete(Project).where(Project.id == project_id)
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:
                    logger.info(f"Deleted Project {project_id}")
                    return True
                else:
                    logger.warning(f"Project {project_id} not found")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete Project: {e}")
            return False

    def get_colors(self) -> dict[int, str | None]:
        """Get color mapping for all Projects."""
        try:
            with self.db.get_session() as session:
                stmt = select(Project.id, Project.color)
                results = session.execute(stmt).all()

                colors = {}
                for row in results:
                    colors[row[0]] = row[1]
                return colors

        except Exception as e:
            logger.error(f"Failed to get Project colors: {e}")
            return {}
