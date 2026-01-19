# Design System

This page documents Vociferous's visual design system including colors, typography, spacing, and component styling.

---

## Overview

Vociferous uses a **token-based design system** with centralized constants for consistent styling across all UI components.

### Design Files

| File | Purpose |
|------|---------|
| `src/ui/constants/colors.py` | Color palette definitions |
| `src/ui/constants/spacing.py` | Spacing scale and dimensions |
| `src/ui/constants/__init__.py` | Typography and other constants |
| `src/ui/styles/unified_stylesheet.py` | Global QSS stylesheet |

---

## Color System

### Color Scales

Vociferous uses numbered color scales from 0 (lightest) to 9 (darkest):

#### Gray Scale

| Token | Hex | Usage |
|-------|-----|-------|
| `GRAY_0` | `#FFFFFF` | Pure white |
| `GRAY_1` | `#F5F5F5` | Lightest gray |
| `GRAY_2` | `#E5E5E5` | Light gray |
| `GRAY_3` | `#D4D4D4` | Primary text (light theme) |
| `GRAY_4` | `#A3A3A3` | Secondary text |
| `GRAY_5` | `#737373` | Tertiary text |
| `GRAY_6` | `#525252` | Dark gray |
| `GRAY_7` | `#404040` | Panel backgrounds |
| `GRAY_8` | `#262626` | Content background |
| `GRAY_9` | `#171717` | Shell background |

#### Blue Scale (Primary)

| Token | Hex | Usage |
|-------|-----|-------|
| `BLUE_0` | `#EFF6FF` | Lightest blue |
| `BLUE_1` | `#DBEAFE` | Light blue |
| `BLUE_2` | `#BFDBFE` | Hover states |
| `BLUE_3` | `#93C5FD` | Active indicators |
| `BLUE_4` | `#60A5FA` | Primary accent |
| `BLUE_5` | `#3B82F6` | Buttons, links |
| `BLUE_6` | `#2563EB` | Strong accent |
| `BLUE_7` | `#1D4ED8` | Dark blue |
| `BLUE_8` | `#1E40AF` | Very dark blue |
| `BLUE_9` | `#1E3A8A` | Darkest blue |

#### Semantic Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `GREEN` | `#22C55E` | Success, recording active |
| `RED` | `#EF4444` | Error, destructive actions |
| `PURPLE` | `#A855F7` | Refinement, AI features |

### Surface Colors

| Token | Value | Usage |
|-------|-------|-------|
| `SHELL_BACKGROUND` | `GRAY_9` | Window background |
| `CONTENT_BACKGROUND` | `GRAY_8` | Content panels |
| `ELEVATED_BACKGROUND` | `GRAY_7` | Cards, dialogs |
| `OVERLAY_BACKDROP` | `rgba(0,0,0,0.7)` | Modal overlays |

---

## Typography

### Font Scale

| Token | Size | Usage |
|-------|------|-------|
| `FONT_SIZE_XS` | 10px | Captions, labels |
| `FONT_SIZE_SM` | 12px | Secondary text |
| `FONT_SIZE_MD` | 14px | Body text (default) |
| `FONT_SIZE_LG` | 16px | Subheadings |
| `FONT_SIZE_XL` | 20px | Headings |
| `FONT_SIZE_XXL` | 28px | Page titles |

### Font Weights

| Weight | Qt Constant | Usage |
|--------|-------------|-------|
| Normal | `QFont.Weight.Normal` | Body text |
| Medium | `QFont.Weight.Medium` | Emphasized text |
| DemiBold | `QFont.Weight.DemiBold` | Subheadings |
| Bold | `QFont.Weight.Bold` | Headings |

### Text Colors

| Context | Token |
|---------|-------|
| Primary text | `GRAY_3` |
| Secondary text | `GRAY_4` |
| Muted text | `GRAY_5` |
| Link text | `BLUE_4` |
| Error text | `RED` |
| Success text | `GREEN` |

---

## Spacing Scale

Vociferous uses a non-linear spacing scale for consistent rhythm:

| Token | Value | Usage |
|-------|-------|-------|
| `S0` | 4px | Tight spacing, icon padding |
| `S1` | 8px | Component padding |
| `S2` | 12px | Element gaps |
| `S3` | 16px | Section padding |
| `S4` | 24px | Card padding |
| `S5` | 32px | Major sections |
| `S6` | 48px | Page margins |
| `S7` | 64px | Large separations |

### Semantic Aliases

| Alias | Value | Usage |
|-------|-------|-------|
| `MINOR_GAP` | `S2` (12px) | Between related elements |
| `MAJOR_GAP` | `S4` (24px) | Between sections |
| `HEADER_CONTROLS_GAP` | `S3` (16px) | Below headers |

---

## Dimensions

### Fixed Dimensions

| Token | Value | Usage |
|-------|-------|-------|
| `ICON_RAIL_WIDTH` | 72px | Navigation rail |
| `ACTION_DOCK_WIDTH` | 120px | Action button area |
| `TITLE_BAR_HEIGHT` | 80px | View title bars |
| `BUTTON_HEIGHT` | 36px | Standard buttons |
| `INPUT_HEIGHT` | 36px | Text inputs |

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `RADIUS_SM` | 4px | Buttons, inputs |
| `RADIUS_MD` | 8px | Cards, panels |
| `RADIUS_LG` | 12px | Dialogs, overlays |
| `RADIUS_ROUND` | 50% | Circular elements |

---

## Unified Stylesheet

### Location

`src/ui/styles/unified_stylesheet.py`

### Structure

The global stylesheet is organized by component:

```python
def get_unified_stylesheet() -> str:
    return f"""
    /* Base */
    QWidget {{ ... }}
    
    /* Buttons */
    QPushButton {{ ... }}
    QPushButton:hover {{ ... }}
    QPushButton:pressed {{ ... }}
    
    /* Inputs */
    QLineEdit {{ ... }}
    QComboBox {{ ... }}
    
    /* Lists */
    QListView {{ ... }}
    QTableView {{ ... }}
    
    /* Scrollbars */
    QScrollBar {{ ... }}
    
    /* View-specific */
    #SettingsView {{ ... }}
    #SearchView {{ ... }}
    """
```

### Application

The stylesheet is applied once at startup:

```python
# In main.py or ApplicationCoordinator
from src.ui.styles.unified_stylesheet import get_unified_stylesheet
app.setStyleSheet(get_unified_stylesheet())
```

### Invariant

> **Ad-hoc `setStyleSheet()` calls on individual widgets are forbidden.** All styling must go through the unified stylesheet or view-specific style modules.

---

## View-Specific Styles

Complex views have dedicated style modules:

| View | Style Module |
|------|--------------|
| Settings | `src/ui/styles/settings_view_styles.py` |
| User | `src/ui/styles/user_view_styles.py` |
| Refine | `src/ui/styles/refine_view_styles.py` |

### Usage Pattern

```python
from src.ui.styles.settings_view_styles import get_settings_view_stylesheet

class SettingsView(BaseView):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(get_settings_view_stylesheet())
```

---

## Icons

### Icon Directory

`assets/icons/`

### Available Icons

| Icon | File | Usage |
|------|------|-------|
| Record | `record.svg` | Start recording |
| Stop | `stop.svg` | Stop recording |
| Copy | `copy.svg` | Copy to clipboard |
| Edit | `edit.svg` | Edit transcript |
| Delete | `delete.svg` | Delete transcript |
| Settings | `settings.svg` | Settings view |
| History | `history.svg` | History view |
| Search | `search.svg` | Search view |
| Refine | `refine.svg` | Refinement feature |
| User | `user.svg` | User view |

### Icon Access

```python
from src.core.resource_manager import ResourceManager

icon_path = ResourceManager.get_icon_path("record")
icon = QIcon(str(icon_path))
```

---

## Component Patterns

### Cards

```css
.card {
    background: GRAY_7;
    border-radius: RADIUS_MD;
    padding: MAJOR_GAP;
    border: 1px solid GRAY_6;
}
```

### Buttons

| State | Background | Text |
|-------|------------|------|
| Default | `GRAY_7` | `GRAY_3` |
| Hover | `GRAY_6` | `GRAY_2` |
| Pressed | `GRAY_5` | `GRAY_1` |
| Primary | `BLUE_5` | `GRAY_0` |
| Destructive | `RED` | `GRAY_0` |

### Input Fields

```css
QLineEdit {
    background: GRAY_8;
    border: 1px solid GRAY_6;
    border-radius: RADIUS_SM;
    padding: S1;
    color: GRAY_3;
}

QLineEdit:focus {
    border-color: BLUE_4;
}
```

---

## Dark Theme

Vociferous uses a dark theme by default with:
- Dark backgrounds (`GRAY_8`, `GRAY_9`)
- Light text (`GRAY_3`, `GRAY_4`)
- Accent colors for interactive elements

---

## Best Practices

### Do

- ✅ Use token constants for all values
- ✅ Apply styles through unified stylesheet
- ✅ Use semantic color names
- ✅ Maintain consistent spacing rhythm

### Don't

- ❌ Hardcode color hex values in widgets
- ❌ Use `setStyleSheet()` on individual widgets
- ❌ Mix pixel values without using scale tokens
- ❌ Create new colors without adding to constants

---

## See Also

- [Architecture](Architecture) — System design
- [UI Views Overview](UI-Views-Overview) — View architecture
