"""
Settings dialog styles.
"""

from ui.constants import Colors, Dimensions, Spacing, Typography


def get_settings_styles() -> str:
    """
    Generate stylesheet for settings dialog.

    Returns:
        QSS stylesheet string.
    """
    return f"""
        /* Settings dialog container */
        QDialog#settingsDialog {{
            background-color: {Colors.BG_PRIMARY};
            border: 1px solid {Colors.BORDER_COLOR};
            border-radius: {Dimensions.BORDER_RADIUS}px;
        }}

        /* Scroll area */
        QScrollArea#settingsScrollArea {{
            background-color: transparent;
            border: none;
        }}

        /* Section headers */
        QLabel#settingsSectionHeader {{
            color: {Colors.TEXT_SECONDARY};
            font-size: {Typography.SECTION_HEADER_SIZE}pt;
            font-weight: 600;
            padding-top: {Spacing.MINOR_GAP}px;
            padding-bottom: {Spacing.MINOR_GAP // 2}px;
        }}

        /* Form labels */
        QLabel {{
            color: {Colors.TEXT_PRIMARY};
        }}

        /* Input widgets */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background-color: {Colors.BG_TERTIARY};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER_COLOR};
            border-radius: {Dimensions.BORDER_RADIUS_SMALL}px;
            padding: 6px 10px;
            min-height: 24px;
        }}

        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border-color: {Colors.ACCENT_PRIMARY};
        }}

        /* Checkboxes */
        QCheckBox {{
            color: {Colors.TEXT_PRIMARY};
            spacing: 8px;
        }}

        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 1px solid {Colors.BORDER_COLOR};
            border-radius: 3px;
            background-color: {Colors.BG_TERTIARY};
        }}

        QCheckBox::indicator:checked {{
            background-color: {Colors.ACCENT_PRIMARY};
            border-color: {Colors.ACCENT_PRIMARY};
        }}

        /* Button container */
        QWidget#settingsButtonContainer {{
            background-color: {Colors.BG_SECONDARY};
            border-top: 1px solid {Colors.BORDER_COLOR};
        }}

        /* Cancel button */
        QPushButton#settingsCancelBtn {{
            background-color: {Colors.BG_TERTIARY};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER_COLOR};
            border-radius: {Dimensions.BORDER_RADIUS}px;
        }}

        QPushButton#settingsCancelBtn:hover {{
            background-color: {Colors.HOVER_BG_ITEM};
        }}

        /* Apply button */
        QPushButton#settingsApplyBtn {{
            background-color: {Colors.BG_TERTIARY};
            color: {Colors.TEXT_PRIMARY};
            border: 1px solid {Colors.BORDER_COLOR};
            border-radius: {Dimensions.BORDER_RADIUS}px;
        }}

        QPushButton#settingsApplyBtn:hover {{
            background-color: {Colors.HOVER_BG_ITEM};
        }}

        /* OK button */
        QPushButton#settingsOkBtn {{
            background-color: {Colors.ACCENT_PRIMARY};
            color: {Colors.TEXT_ON_ACCENT};
            border: none;
            border-radius: {Dimensions.BORDER_RADIUS}px;
        }}

        QPushButton#settingsOkBtn:hover {{
            background-color: {Colors.ACCENT_HOVER};
        }}
    """
