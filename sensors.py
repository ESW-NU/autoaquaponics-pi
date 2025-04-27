from main import Task
import numpy as np
import time
from logs import global_logger, setup_logger

import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from firebase import db

stream_logger = setup_logger("logs/sensors.log", "Sensors")

sensors = ('unix_time', 'pH', 'TDS', 'humidity', 'air_temp', 'water_temp', 'distance', 'flow')

class SensorDataCollector(Task):
    def __init__(self):
        self.logging_interval = 15 * 60 # seconds

        # store the last values
        self.pH = np.nan
        self.TDS = np.nan
        self.distance = np.nan  #to give an arbitrary initial value to getData for the first time the distance sensor fails
        self.wtemp = 21  #arbitrary initial value
        self.hum = np.nan
        self.atemp = np.nan
        self.last_log_time = round(time.time())
        self.next_log_time = self.last_log_time
        self.flow = np.nan

    def start(self):
        # get initial readings; these are done immediately to allow sensors to stabilize
        for i in range(10):
            self.pH, self.TDS, self.hum, self.atemp, self.wtemp, self.distance, self.flow = np.round(get_data(self.distance, self.wtemp, self.hum, self.atemp), 2)
            stream_logger.info(f"Initial reading #{i}: {self.pH}, {self.TDS}, {self.hum}, {self.atemp}, {self.wtemp}, {self.distance}, {self.flow}")
            time.sleep(1)

        while True:
            # wait until the right time to log
            curr_time = round(time.time())
            if curr_time < self.next_log_time:
                stream_logger.info(f"Waiting for next log time: {self.next_log_time - curr_time} seconds")
                time.sleep(self.next_log_time - curr_time)
                continue

            # the time to log has passed; get the data
            self.pH, self.TDS, self.hum, self.atemp, self.wtemp, self.distance, self.flow = np.round(get_data(self.distance, self.wtemp, self.hum, self.atemp), 2)

            # package the data and send to firebase
            curr_data = (curr_time, self.pH, self.TDS, self.hum, self.atemp, self.wtemp, self.distance, self.flow)
            stream_logger.info(f"Logging data: {curr_data}")
            data_as_dict = {}
            for i in range(len(curr_data)):
                data_as_dict[sensors[i]] = curr_data[i]
            db.collection(u'stats').add(data_as_dict)

            # update the last log time
            self.next_log_time = self.last_log_time + self.logging_interval
            self.last_log_time = self.next_log_time

    def stop(self):
        pass

def get_data(distance, wtemp, hum, atemp):
    # get the actual data
    return get_ph(), np.nan, np.nan, np.nan, np.nan, np.nan, get_flow()

# initialize interface with sensors
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ads.gain = 2/3
ph_adc = AnalogIn(ads, ADS.P2)

def get_ph():
    neutral_voltage = 1.5 # the voltage when the pH is 7
    inverse_slope = -0.1765 # volts per pH unit
    return (ph_adc.voltage - neutral_voltage) / inverse_slope + 7.0

def get_flow():
    # TODO add code to get the flow rn
    pass
