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

Vociferous uses numbered color scales from 0 (lightest) to 9 (darkest).

#### Gray Scale

| Token | Hex | Usage |
|-------|-----|-------|
| `GRAY_0` | `#ffffff` | Pure white |
| `GRAY_1` | `#e0e0e0` | Lightest gray |
| `GRAY_2` | `#d4d4d4` | Light gray |
| `GRAY_3` | `#bbbbbb` | Primary text (light theme) |
| `GRAY_4` | `#888888` | Secondary text |
| `GRAY_5` | `#555555` | Tertiary text |
| `GRAY_6` | `#4c4c4c` | Dark gray |
| `GRAY_7` | `#3c3c3c` | Panel backgrounds |
| `GRAY_8` | `#2a2a2a` | Content background |
| `GRAY_9` | `#1e1e1e` | Shell background |

#### Blue Scale (Primary)

| Token | Hex | Usage |
|-------|-----|-------|
| `BLUE_0` | `#e6f0fa` | Lightest blue |
| `BLUE_1` | `#cce0f5` | Light blue |
| `BLUE_2` | `#99c2ed` | Hover states |
| `BLUE_3` | `#6db3e8` | Active indicators |
| `BLUE_4` | `#5a9fd4` | Primary accent (Content Border) |
| `BLUE_5` | `#4a8ac0` | Buttons, links |
| `BLUE_6` | `#3d4f5f` | Strong accent |
| `BLUE_7` | `#2d5a7b` | Dark blue |
| `BLUE_8` | `#2d3d4d` | Very dark blue |
| `BLUE_9` | `#1a252e` | Darkest blue |

#### Semantic Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `GREEN_5` | `#4caf50` | Success, recording active |
| `RED_5` | `#ff6b6b` | Error, destructive actions |
| `PURPLE_5` | `#8a2be2` | Refinement, AI features |
| `ORANGE_5` | `#ffa500` | Warnings |

### Surface Colors

| Token | Value | Meaning |
|-------|-------|-------|
| `SHELL_BACKGROUND` | `GRAY_9` | Window / App Frame |
| `CONTENT_BACKGROUND` | `GRAY_8` | Interactive Areas / Inputs |
| `SHELL_BORDER` | `GRAY_7` | Structural Borders |
| `CONTENT_BORDER` | `BLUE_4` | Focus / Active Borders |
| `OVERLAY_BACKDROP` | `rgba(0,0,0,0.5)` | Modal overlays |

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

### Text Colors

| Context | Token |
|---------|-------|
| Primary text | `TEXT_PRIMARY` (`GRAY_2`) |
| Secondary text | `TEXT_SECONDARY` (`GRAY_4`) |
| Tertiary text | `TEXT_TERTIARY` (`GRAY_5`) |

---

## Spacing Scale

Vociferous uses a non-linear spacing scale:

| Token | Value | Usage |
|-------|-------|-------|
| `S0` | 4px | Tightest |
| `S1` | 8px | Compact |
| `S2` | 12px | Default gaps |
| `S3` | 16px | Standard padding |
| `S4` | 24px | Comfortable |
| `S5` | 32px | Spacious |
| `S6` | 48px | Generous |
| `S7` | 64px | Maximum |

### Semantic Aliases

| Alias | Value | Usage |
|-------|-------|-------|
| `MINOR_GAP` | `S2` (12px) | Between related elements |
| `MAJOR_GAP` | `S4` (24px) | Between sections |
| `HEADER_CONTROLS_GAP` | `S3` (16px) | Below headers |

---

## Unified Stylesheet

### Location

`src/ui/styles/unified_stylesheet.py`

### Invariant

> **Ad-hoc `setStyleSheet()` calls on individual widgets are forbidden.** All styling must go through the unified stylesheet or view-specific style modules.

---

## Icons

### Icon Directory

`assets/icons/`

### Icon Access

```python
from src.core.resource_manager import ResourceManager

icon_path = ResourceManager.get_icon_path("record")
icon = QIcon(str(icon_path))
```
