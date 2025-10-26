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
import adafruit_dht
from firebase import AddSensorData, Firebase
from sensors_data import SensorData
from dataclasses import dataclass

sensor_logger = register_logger("logs/sensors.log", "Sensors")

# Functions for measuring the sensors.
#
# The parameters to these functions are objects representing the raw hardware
# resources. These functions then perform the device-specific operations
# required to take a measurement and return a meaningful value.

def measure_ph(ph_adc):
    """Get pH reading."""
    neutral_voltage = 1.38102  # the voltage when the pH is 7
    inverse_slope = -0.161711  # volts per pH unit
    return (ph_adc.voltage - neutral_voltage) / inverse_slope + 7.0

def measure_do(do_adc):
    do_table = [14460, 14220, 13820, 13440, 13090, 12740, 12420, 12110, 11810, 11530,
            11260, 11010, 10770, 10530, 10300, 10080, 9860, 9660, 9460, 9270,
            9080, 8900, 8730, 8570, 8410, 8250, 8110, 7960, 7820, 7690,
            7560, 7430, 7300, 7180, 7070, 6950, 6840, 6730, 6630, 6530, 6410]
    v_cal = 0.81 # voltage when fully saturated
    v_temp = 23.4 # temperature in C for above measurement
    v_saturation = v_cal + 35 * v_temp - v_temp * 35

    # current water temperature in C. this should be obtained
    # from a sensor but we don't have that yet so use a dummy value
    wtemp_c = 25.6

    mg_per_liter = do_adc.voltage * do_table[int(wtemp_c)] / v_saturation / 1000
    return mg_per_liter

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
    """
    This class encapsulates all hardware resources involved with taking sensor
    measurements. When constructed, this class initializes those hardware
    resources. Methods on this class then use the relevant resources to take
    measurements, delegating to other functions to actually perform the
    device-specific operations.
    """
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
        self.raw_tds = AnalogIn(self.ads, ADS.P0)
        self.adc_do = AnalogIn(self.ads, ADS.P3)

        # initialize DHT
        self.dht = adafruit_dht.DHT22(board.D27, use_pulseio=False)

    def measure_all(self) -> SensorData:
        temperature, humidity = self.measure_dht()

        return SensorData(
            unix_time=round(time.time()),
            pH=self.measure_ph(),
            flow=self.measure_flow(),
            air_temp=temperature,
            humidity=humidity,
            TDS = self.get_tds(),
            dissolved_oxygen = self.measure_do(),
        )

    def measure_ph(self):
        return measure_ph(self.adc_ph)

    def measure_flow(self):
        return measure_flow(self.gpio, self.flow_pin)

    def measure_do(self):
        return measure_do(self.adc_do)

    def measure_dht(self):
        def is_nan(x):  #used in DHT function
            return (x is np.nan or x != x)
        temperature_c = np.nan
        humidity = np.nan
        while is_nan(temperature_c) or is_nan(humidity):  #test to see if the value is still nan
            try:
                temperature_c = self.dht.temperature
                humidity = self.dht.humidity
            except RuntimeError as error:
                sensor_logger.error(error.args[0])
                # Errors happen fairly often, DHT's are hard to read. Sets to NaN to restart the function.
                temperature_c = float('NaN')
                humidity = float('NaN')
            except Exception as error:
                # If unexpected error, release resources used by the sensor and notifies caller
                # self.dht.exit()
                sensor_logger.error(error)
                raise error
        return temperature_c, humidity
    def get_tds(self, wtemp=25):
        Vtds_raw = self.raw_tds.voltage        #raw reading from sensor right now
        TheoEC = 684                    #theoretical EC (electrical conductivity) of calibration fluid (calibrated with 342 ppm of aqueous NaCl)
        Vc = 1.085751885                #voltage reading of sensor when calibrating
        temp_calibrate = 23.25          #measured water temp when calibrating
        rawECsol = TheoEC*(1+0.02*(temp_calibrate-25))  #temp compensate the calibrated values
        K = (rawECsol)/(133.42*(Vc**3)-255.86*(Vc**2)+857.39*Vc)  #defined calibration factor K for NaCl (this will have to be readjusted for specific solution in tank)
        EC_raw = K*(133.42*(Vtds_raw**3)-255.86*(Vtds_raw**2)+857.39*Vtds_raw)
        EC = EC_raw/(1+0.02*(wtemp-25)) #use current temp for temp compensation
        TDS = EC/2                      #TDS is just half of electrical conductivity in ppm
        return TDS
# Data type definitions for messages for the sensors actor. Sending messages of
# these types to the actor will cause it to perform certain actions.
# See main.py for more information on the actor system.

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

def get_actor_firebase():
    """Get the first firebase actor."""
    lst = pykka.ActorRegistry.get_by_class(Firebase)
    return lst[0] if lst else None

class Sensors(pykka.ThreadingActor):
    """
    This actor is responsible for all business related to the sensors. As part
    of its responsibilities, it takes periodic measurements from the sensors
    using a SensorsHardware object and sends them to the firebase actor.
    """

    def __init__(self, sensor_logger=sensor_logger):
        super().__init__()

        self.logger = sensor_logger

        # initialize latest sensor values
        self.pH = np.nan
        self.flow = np.nan

        # variables for measurement intervals
        self.measurement_interval = None
        self.last_measure_time = None
        self.next_measurement_time = None
        self.timer_thread = None

        # a SensorsHardware object for actually performing the measurements
        self.hardware = None

    def on_start(self):
        """Initialize hardware and start data collection."""

        try:
            self.logger.info("Initializing sensors hardware")
            self.hardware = SensorsHardware()

            # send messages to self to start the measurement loop
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
            self.last_measure_time = round(time.time())
            self.next_measurement_time = self.last_measure_time
            self.measurement_interval = message.logging_interval
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
        """
        Take 10 initial pH readings for stabilization.
        """
        self.logger.info("Measuring 10 initial pH readings for stabilization")
        for i in range(10):
            data = self.hardware.measure_ph()
            self.logger.debug(f"Initial reading #{i}: {data}")
            time.sleep(1)

    def measure_and_send_data(self):
        """
        Get and send data.
        """
        data = self.hardware.measure_all()
        self.logger.debug(f"Logging data: {data}")
        if actor_firebase := get_actor_firebase():
            actor_firebase.tell(AddSensorData(data))
        else:
            self.logger.warning("Couldn't send data: no firebase actor found")

    def measure_and_send_data_repeated(self):
        """
        Call *once* to start the measurement loop. Do not call in a loop! After
        this function takes a measurement, it will schedule itself to be called
        again in the future.
        """

        # cancel any existing timer to make sure there is only one measurement
        # loop
        if self.timer_thread is not None:
            self.timer_thread.cancel()

        self.measure_and_send_data()

        # schedule the next measurement time
        curr_time = round(time.time())
        self.last_measure_time = self.next_measurement_time
        self.next_measurement_time = self.last_measure_time + self.measurement_interval
        if self.next_measurement_time <= curr_time:
            self.next_measurement_time = curr_time + self.measurement_interval
        wait_time = self.next_measurement_time - curr_time
        self.logger.debug(f"Next log time: {self.next_measurement_time} in {wait_time} seconds")
        self.timer_thread = threading.Timer(wait_time, self.measure_and_send_data_repeated)
        self.timer_thread.start()
