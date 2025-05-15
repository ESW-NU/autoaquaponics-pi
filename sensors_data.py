from dataclasses import dataclass

# this has to go here instead of sensors.py to avoid circular import

@dataclass
class SensorData:
    """Data from all sensors."""
    unix_time: int
    pH: float
    flow: float
    air_temp: float
    humidity: float

