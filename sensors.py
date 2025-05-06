import numpy as np
import time
import pykka
import threading
from logs import register_logger
import lgpio as GPIO
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from firebase import AddSensorData
from sensors_data import SensorData
from dataclasses import dataclass

sensor_logger = register_logger("logs/sensors.log", "Sensors")

def measure_ph(ph_adc):
    """Get pH reading."""
    neutral_voltage = 1.5  # the voltage when the pH is 7
    inverse_slope = -0.1765  # volts per pH unit
    return (ph_adc.voltage - neutral_voltage) / inverse_slope + 7.0

def measure_flow(gpio, flow_pin, t_sec=5):
    """Get flow rate reading."""
    flow_cb = GPIO.callback(gpio, flow_pin, GPIO.FALLING_EDGE)
    time.sleep(t_sec)
    count = flow_cb.tally()
    freq = count/t_sec
    flow = (freq / 0.2) * 15.850323141489  # Pulse frequency (Hz) = 0.2Q, Q is flow rate in GPH
    flow_cb.cancel()
    return flow

class SensorsHardware:
    def __init__(self):
        # initialize GPIO
        self.flow_pin = 16
        self.gpio = GPIO.gpiochip_open(0)
        GPIO.gpio_claim_alert(self.gpio, self.flow_pin, eFlags=GPIO.FALLING_EDGE, lFlags=GPIO.SET_PULL_UP)

        # initialize I2C and ADC
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.ads = ADS.ADS1115(self.i2c)
        self.ads.gain = 2/3
        self.adc_ph = AnalogIn(self.ads, ADS.P2)

    def measure_all(self) -> SensorData:
        return SensorData(
            unix_time=round(time.time()),
            pH=self.measure_ph(),
            flow=self.measure_flow()
        )

    def measure_ph(self):
        return measure_ph(self.adc_ph)

    def measure_flow(self):
        return measure_flow(self.gpio, self.flow_pin)

@dataclass
class StabilizeMeasurements:
    """Message to trigger making multiple measurements immediately to stabilize
    readings."""
    pass

@dataclass
class CollectAndSendData:
    """Message to trigger data collection."""
    pass

@dataclass
class TriggerSensorLoop:
    """Message to trigger the sensor loop."""
    logging_interval: int

class Sensors(pykka.ThreadingActor):
    def __init__(self, actor_firebase, sensor_logger=sensor_logger):
        super().__init__()

        self.logger = sensor_logger

        self.actor_firebase = actor_firebase

        # initialize latest sensor values
        self.pH = np.nan
        self.flow = np.nan

        self.logging_interval = None
        self.last_log_time = None
        self.next_log_time = None
        self.timer_thread = None

        self.hardware = None

    def on_start(self):
        """Initialize hardware and start data collection."""

        try:
            self.logger.info("Initializing sensors hardware")
            self.hardware = SensorsHardware()

            self.actor_ref.tell(StabilizeMeasurements())
            self.actor_ref.tell(TriggerSensorLoop(logging_interval=15 * 60))
        except Exception as e:
            self.logger.error(f"Error initializing sensors hardware: {e}")
            raise e

    def on_receive(self, message):
        """Handle incoming messages."""
        self.logger.debug(f"Received message: {message}")

        if isinstance(message, TriggerSensorLoop):
            self.logger.info("Starting sensor loop")
            self.last_log_time = round(time.time())
            self.next_log_time = self.last_log_time
            self.logging_interval = message.logging_interval
            threading.Thread(target=self.measure_and_send_data_repeated).start()
            return

        if isinstance(message, CollectAndSendData):
            self.measure_and_send_data()
            return

        if isinstance(message, StabilizeMeasurements):
            self.stabilize_measurements()
            return

        self.logger.warning(f"Received unknown message type: {type(message)}")

    def on_stop(self):
        """Clean up hardware resources."""
        self.logger.info("Stopping sensors")
        if self.gpio:
            GPIO.gpiochip_close(self.gpio)

    def on_failure(self, failure):
        """Handle actor failures."""
        self.logger.error(f"Sensors actor failed: {failure}")
        self.on_stop()

    # custom methods

    def stabilize_measurements(self):
        self.logger.info("Measuring 10 initial pH readings for stabilization")
        for i in range(10):
            data = self.hardware.measure_ph()
            self.logger.debug(f"Initial reading #{i}: {data}")
            time.sleep(1)

    def measure_and_send_data(self):
        # get and send data
        data = self.hardware.measure_all()
        self.logger.debug(f"Logging data: {data}")
        self.actor_firebase.tell(AddSensorData(data))

    def measure_and_send_data_repeated(self):
        if self.timer_thread is not None:
            self.timer_thread.cancel()

        self.measure_and_send_data()

        # schedule the next log time
        curr_time = round(time.time())
        self.last_log_time = self.next_log_time
        self.next_log_time = self.last_log_time + self.logging_interval
        if self.next_log_time <= curr_time:
            self.next_log_time = curr_time + self.logging_interval
        wait_time = self.next_log_time - curr_time
        self.logger.debug(f"Next log time: {self.next_log_time} in {wait_time} seconds")
        self.timer_thread = threading.Timer(wait_time, self.measure_and_send_data_repeated)
        self.timer_thread.start()
