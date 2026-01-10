"""
Styles for MetricsStrip widget.

QSS rules for metrics strip container, labels, values, and dividers.
"""

from ui.constants import Colors

METRICS_STRIP_STYLESHEET = f"""
    /* Metrics strip container */
    QWidget#metricsStrip {{
        background-color: {Colors.BG_SECONDARY};
        border-radius: 6px;
    }}

    /* Metric label */
    QLabel#metricLabel {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 11px;
    }}

    /* Metric value */
    QLabel#metricValue {{
        color: {Colors.TEXT_PRIMARY};
        font-size: 13px;
        font-weight: 500;
    }}

    /* Metric divider */
    QWidget#metricDivider {{
        background-color: {Colors.BORDER_DEFAULT};
    }}

    /* Collapsed state label */
    QLabel#metricsCollapsed {{
        color: {Colors.TEXT_SECONDARY};
        font-size: 11px;
    }}
"""
