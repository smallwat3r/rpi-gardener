"""Shared constants for the configuration module.

These constants are separated to avoid circular imports between settings.py
and thresholds.py.
"""

# Hysteresis offsets for alert recovery (prevents flapping)
# Alert triggers at threshold, clears at threshold +/- hysteresis
HYSTERESIS_TEMPERATURE = 1  # Celsius
HYSTERESIS_HUMIDITY = 3  # %
HYSTERESIS_MOISTURE = 3  # %
