import logging
from sqlalchemy import delete, select, update, func
from database.core import DatabaseCore
from database.models import FocusGroup, Transcript

logger = logging.getLogger(__name__)

class FocusGroupRepository:
    def __init__(self, db_core: DatabaseCore):
        self.db = db_core

    def create(
        self, name: str, color: str | None = None, parent_id: int | None = None
    ) -> int | None:
        """Create a new focus group."""
        try:
            with self.db.get_session() as session:
                group = FocusGroup(name=name, color=color, parent_id=parent_id)
                session.add(group)
                session.commit()
                return group.id

        except Exception as e:
            logger.error(f"Failed to create focus group: {e}")
            return None

    def get_all(self) -> list[tuple[int, str, str | None, int | None]]:
        """Get all focus groups."""
        try:
            with self.db.get_session() as session:
                stmt = select(FocusGroup).order_by(FocusGroup.created_at.asc())
                groups = session.execute(stmt).scalars().all()
                return [(g.id, g.name, g.color, g.parent_id) for g in groups]

        except Exception as e:
            logger.error(f"Failed to get focus groups: {e}")
            return []

    def rename(self, focus_group_id: int, new_name: str) -> bool:
        """Rename a focus group."""
        try:
            with self.db.get_session() as session:
                stmt = (
                    update(FocusGroup)
                    .where(FocusGroup.id == focus_group_id)
                    .values(name=new_name)
                )
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:
                    logger.info(f"Renamed focus group {focus_group_id} to '{new_name}'")
                    return True
                else:
                    logger.warning(f"Focus group {focus_group_id} not found")
                    return False

        except Exception as e:
            logger.error(f"Failed to rename focus group: {e}")
            return False

    def update_color(self, focus_group_id: int, color: str | None) -> bool:
        """Update a focus group's accent color."""
        try:
            with self.db.get_session() as session:
                stmt = (
                    update(FocusGroup)
                    .where(FocusGroup.id == focus_group_id)
                    .values(color=color)
                )
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:
                    logger.info(
                        f"Updated focus group {focus_group_id} color to '{color}'"
                    )
                    return True
                else:
                    logger.warning(f"Focus group {focus_group_id} not found")
                    return False

        except Exception as e:
            logger.error(f"Failed to update focus group color: {e}")
            return False

    def delete(
        self, focus_group_id: int, move_to_ungrouped: bool = True
    ) -> bool:
        """Delete a focus group."""
        try:
            with self.db.get_session() as session:
                # Check if group has transcripts
                stmt_count = select(func.count(Transcript.id)).where(
                    Transcript.focus_group_id == focus_group_id
                )
                count = session.execute(stmt_count).scalar() or 0

                if count > 0 and not move_to_ungrouped:
                    logger.warning(
                        f"Cannot delete focus group {focus_group_id}: "
                        f"contains {count} transcripts"
                    )
                    return False

                if count > 0 and move_to_ungrouped:
                    update_stmt = (
                        update(Transcript)
                        .where(Transcript.focus_group_id == focus_group_id)
                        .values(focus_group_id=None)
                    )
                    session.execute(update_stmt)

                stmt = delete(FocusGroup).where(FocusGroup.id == focus_group_id)
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:
                    logger.info(f"Deleted focus group {focus_group_id}")
                    return True
                else:
                    logger.warning(f"Focus group {focus_group_id} not found")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete focus group: {e}")
            return False

    def get_colors(self) -> dict[int, str | None]:
        """Get color mapping for all focus groups."""
        try:
            with self.db.get_session() as session:
                stmt = select(FocusGroup.id, FocusGroup.color)
                results = session.execute(stmt).all()

                colors = {}
                for row in results:
                    colors[row[0]] = row[1]
                return colors

        except Exception as e:
            logger.error(f"Failed to get focus group colors: {e}")
            return {}
