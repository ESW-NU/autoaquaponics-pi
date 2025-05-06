from dataclasses import dataclass

# this has to go here instead of sensors.py to avoid circular import

@dataclass
class SensorData:
    """Data from all sensors."""
    pH: float
    flow_rate: float

