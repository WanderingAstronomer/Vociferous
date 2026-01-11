"""
Styles for MetricsStrip widget.

QSS rules for metrics strip container, labels, values, and dividers.
"""

from ui.constants import Colors, Dimensions, Typography

METRICS_STRIP_STYLESHEET = f"""
    /* Metrics strip container */
    QWidget#metricsStrip {{
        background-color: {Colors.SURFACE};
        border-radius: {Dimensions.BORDER_RADIUS_MD}px;
    }}

    /* Metric label */
    QLabel#metricLabel {{
        color: {Colors.TEXT_SECONDARY};
        font-size: {Typography.FONT_SIZE_XS}px;
    }}

    /* Metric value */
    QLabel#metricValue {{
        color: {Colors.TEXT_PRIMARY};
        font-size: {Typography.FONT_SIZE_SM}px;
        font-weight: {Typography.FONT_WEIGHT_EMPHASIS};
    }}

    /* Metric divider */
    QWidget#metricDivider {{
        background-color: {Colors.BORDER_DEFAULT};
    }}

    /* Collapsed state label */
    QLabel#metricsCollapsed {{
        color: {Colors.TEXT_SECONDARY};
        font-size: {Typography.FONT_SIZE_XS}px;
    }}
"""
