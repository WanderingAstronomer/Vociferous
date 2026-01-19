"""
View-specific stylesheet overrides for SettingsView.
"""

import src.ui.constants.colors as c


def get_settings_view_stylesheet() -> str:
    """
    Custom stylesheet for Settings View.

    Includes:
    - Dark dropdown backgrounds
    - Consistent field styling with focus states
    - Fixed-width form elements
    - Proper alignment and spacing
    """
    return f"""
        /* Settings View Container */
        SettingsView {{
            background-color: {c.GRAY_9};
        }}
        
        /* Base Input Field Styles */
        SettingsView QLineEdit {{
            background-color: {c.GRAY_8};
            color: {c.GRAY_2};
            border: 1px solid {c.GRAY_6};
            border-radius: 4px;
            padding: 6px 12px;
            min-height: 28px;
        }}
        
        SettingsView QLineEdit:hover {{
            border: 1px solid {c.BLUE_4};
            background-color: {c.GRAY_7};
        }}
        
        SettingsView QLineEdit:focus {{
            border: 2px solid {c.BLUE_4};
            background-color: {c.GRAY_7};
        }}
        
        SettingsView QSpinBox, SettingsView QDoubleSpinBox {{
            background-color: {c.GRAY_8};
            color: {c.GRAY_2};
            border: 1px solid {c.GRAY_6};
            border-radius: 4px;
            padding: 6px 12px;
            min-height: 28px;
        }}
        
        SettingsView QSpinBox:hover, SettingsView QDoubleSpinBox:hover {{
            border: 1px solid {c.BLUE_4};
            background-color: {c.GRAY_7};
        }}
        
        SettingsView QSpinBox:focus, SettingsView QDoubleSpinBox:focus {{
            border: 2px solid {c.BLUE_4};
            background-color: {c.GRAY_7};
        }}
        
        /* ComboBox (Dropdowns) - Dark background */
        SettingsView QComboBox {{
            combobox-popup: 0;
            background-color: {c.GRAY_8};
            color: {c.GRAY_2};
            border: 1px solid {c.GRAY_6};
            border-radius: 4px;
            padding: 6px 12px;
            min-height: 28px;
            min-width: 200px;
        }}
        
        SettingsView QComboBox:hover {{
            border: 1px solid {c.BLUE_4};
            background-color: {c.GRAY_7};
        }}
        
        SettingsView QComboBox:focus {{
            border: 2px solid {c.BLUE_4};
            background-color: {c.GRAY_7};
        }}
        
        SettingsView QComboBox::drop-down {{
            border: none;
            padding-right: 8px;
        }}
        
        SettingsView QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 6px solid {c.GRAY_4};
            width: 0;
            height: 0;
        }}
        
        /* Dropdown menu - BLACK background */
        SettingsView QComboBox QAbstractItemView {{
            background-color: {c.GRAY_9};
            color: {c.GRAY_2};
            border: 1px solid {c.BLUE_4};
            selection-background-color: {c.BLUE_4};
            selection-color: {c.GRAY_0};
            padding: 0px;
            outline: none;
        }}
        
        SettingsView QComboBox QAbstractItemView::item {{
            padding: 6px 12px;
            min-height: 24px;
        }}
        
        SettingsView QComboBox QAbstractItemView::item:hover {{
            background-color: {c.BLUE_3};
        }}
        
        /* Language field - Consistent with other fields, blue only on focus */
        SettingsView QLineEdit#languageField {{
            background-color: {c.GRAY_8};
            color: {c.GRAY_2};
            border: 1px solid {c.GRAY_6};
            border-radius: 4px;
            padding: 6px 12px;
            min-height: 28px;
            min-width: 120px;
            max-width: 120px;
            font-weight: 600;
        }}
        
        SettingsView QLineEdit#languageField:hover {{
            border: 1px solid {c.BLUE_4};
            background-color: {c.GRAY_7};
        }}
        
        SettingsView QLineEdit#languageField:focus {{
            border: 2px solid {c.BLUE_4};
            background-color: {c.GRAY_7};
        }}
        
        /* Hotkey widget - Consistent with other fields, blue only on focus */
        HotkeyWidget {{
            background-color: {c.GRAY_8};
            border: 1px solid {c.GRAY_6};
            border-radius: 4px;
            padding: 8px 12px;
            min-height: 28px;
            min-width: 200px;
        }}
        
        HotkeyWidget:hover {{
            border: 1px solid {c.BLUE_4};
            background-color: {c.GRAY_7};
        }}
        
        HotkeyWidget:focus {{
            border: 2px solid {c.BLUE_4};
            background-color: {c.GRAY_7};
        }}
        
        HotkeyWidget QLabel {{
            background-color: transparent;
            color: {c.GRAY_2};
            font-weight: 600;
        }}
        
        /* Change button inside HotkeyWidget - Match Primary Button style (Unfilled) */
        HotkeyWidget QPushButton#hotkeyChangeBtn {{
            background-color: transparent;
            color: {c.BLUE_4};
            border: 1px solid {c.BLUE_4};
            border-radius: 4px;
            padding: 4px 12px;
            font-weight: 600;
            margin-left: 8px;
        }}
        
        HotkeyWidget QPushButton#hotkeyChangeBtn:hover {{
            background-color: {c.BLUE_9};
            color: {c.GRAY_0};
        }}
        
        /* Form labels */
        SettingsView QLabel {{
            color: {c.GRAY_2};
        }}
        
        /* Section cards */
        SettingsView QFrame#settingsCard {{
            background-color: {c.GRAY_8};
            border: 1px solid {c.GRAY_6};
            border-radius: 8px;
        }}
        
        /* Buttons */
        SettingsView QPushButton#secondaryButton {{
            background-color: {c.GRAY_8};
            color: {c.GRAY_2};
            border: 1px solid {c.GRAY_6};
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: 600;
        }}
        
        SettingsView QPushButton#secondaryButton:hover {{
            background-color: {c.GRAY_7};
            border-color: {c.BLUE_4};
        }}
        
        SettingsView QPushButton#destructiveButton {{
            background-color: {c.GRAY_8};
            color: {c.RED_5};
            border: 1px solid {c.RED_5};
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: 600;
        }}
        
        SettingsView QPushButton#destructiveButton:hover {{
            background-color: {c.RED_5};
            color: {c.GRAY_0};
        }}
        
        SettingsView QPushButton#primaryButton {{
            background-color: transparent;
            color: {c.BLUE_4};
            border: 1px solid {c.BLUE_4};
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: 600;
        }}
        
        SettingsView QPushButton#primaryButton:hover {{
            background-color: {c.BLUE_9};
            color: {c.GRAY_0};
        }}
        
        SettingsView QPushButton#primaryButton:disabled {{
            background-color: transparent;
            color: {c.GRAY_6};
            border: 1px solid {c.GRAY_6};
        }}
    """
