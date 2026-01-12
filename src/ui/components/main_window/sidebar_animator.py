"""
SidebarAnimator - Handles sidebar collapse/expand animations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
)

from ui.constants import Dimensions, Spacing, Timing

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QPushButton, QWidget


class SidebarAnimator:
    """
    Manages sidebar collapse/expand animations.

    Handles parallel animations for:
    - Sidebar width (min/max)
    - Toggle button position
    """

    def __init__(
        self,
        sidebar: QWidget,
        toggle_btn: QPushButton,
        parent: QWidget,
    ) -> None:
        self._sidebar = sidebar
        self._toggle_btn = toggle_btn
        self._parent = parent
        self._anim_group: QParallelAnimationGroup | None = None

    def animate_width(
        self,
        start: int,
        end: int,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        """Animate sidebar width and button position.

        Animates both minimumWidth and maximumWidth simultaneously to keep
        the sidebar locked at a specific width throughout the animation.
        This prevents layout jitter and ensures smooth transitions.
        """
        # Stop any running animation
        if (
            self._anim_group
            and self._anim_group.state() == QAbstractAnimation.State.Running
        ):
            self._anim_group.stop()

        group = QParallelAnimationGroup(self._parent)

        # Animate sidebar width by animating both min and max in parallel
        # This keeps the sidebar at a fixed width during the entire animation
        for prop in (b"minimumWidth", b"maximumWidth"):
            anim = QPropertyAnimation(self._sidebar, prop, self._parent)
            anim.setDuration(Timing.UI_TRANSITION_MS)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            anim.setStartValue(start)
            anim.setEndValue(end)
            group.addAnimation(anim)

        # Animate toggle button position
        btn_anim = QPropertyAnimation(self._toggle_btn, b"pos", self._parent)
        btn_anim.setDuration(Timing.UI_TRANSITION_MS)
        btn_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        btn_anim.setStartValue(self._toggle_pos(start))
        btn_anim.setEndValue(self._toggle_pos(end))
        group.addAnimation(btn_anim)

        if on_finished:
            group.finished.connect(on_finished)

        self._anim_group = group
        group.start()

    def _toggle_pos(self, sidebar_width: int) -> QPoint:
        """Compute toggle button position for a given sidebar width.

        Positions the button overlapping the right edge of the sidebar.
        """
        # Position button 12px back from the sidebar's right edge to overlap nicely
        btn_x = Spacing.APP_OUTER + sidebar_width - 12
        btn_y = Spacing.APP_OUTER
        return QPoint(btn_x, btn_y)

    def calculate_sidebar_width(self, window_width: int) -> int:
        """Calculate locked sidebar width (30% of window, clamped to valid range).

        Uses centralized clamping logic to ensure consistency across all components.
        """
        target = int(window_width * Dimensions.SIDEBAR_DEFAULT_RATIO)
        return Dimensions.clamp_sidebar_width(target, window_width)

    def get_toggle_position(self, sidebar_width: int) -> QPoint:
        """Get toggle button position for current sidebar width."""
        return self._toggle_pos(sidebar_width)
