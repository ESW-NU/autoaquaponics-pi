from main import Task
import numpy as np
import firebase_admin
import time
from firebase_admin import credentials, firestore

import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

sensors = ('unix_time', 'pH', 'TDS', 'humidity', 'air_temp', 'water_temp', 'distance')
cred = credentials.Certificate("../Desktop/serviceAccountKey.json")
app = firebase_admin.initialize_app(cred)
db = firestore.client()

LOG_EVERY = 15 # minutes

class SensorDataCollector(Task):
    def __init__(self):
        pass

    def start(self):
        distance = np.nan  #to give an arbitrary initial value to getData for the first time the distance sensor fails
        wtemp = 21  #arbitrary initial value
        hum = np.nan
        atemp = np.nan
        last_log_time = round(time.time())
        interval = LOG_EVERY * 60  # convert minutes to seconds
        next_log_time = last_log_time

        while True:
            # wait until the right time to log
            curr_time = round(time.time())
            if curr_time < next_log_time:
                time.sleep(next_log_time - curr_time)
                continue

            # the time to log has passed; get the data
            pH, TDS, hum, atemp, wtemp, distance = np.round(get_data(distance, wtemp, hum, atemp), 2)

            # package the data and send to firebase
            curr_data = (curr_time, pH, TDS, hum, atemp, wtemp, distance)
            data_as_dict = {}
            for i in range(len(curr_data)):
                data_as_dict[sensors[i]] = curr_data[i]
            db.collection(u'stats').add(data_as_dict)

            # update the last log time
            next_log_time = last_log_time + interval
            last_log_time = next_log_time

    def stop(self):
        pass

def get_data(distance, wtemp, hum, atemp):
    # get the actual data
    return get_ph(), np.nan, np.nan, np.nan, np.nan, np.nan

# initialize interface with sensors
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ads.gain = 2/3
ph_adc = AnalogIn(ads, ADS.P0)

def get_ph():
    neutral_voltage = 1.5 # the voltage when the pH is 7
    inverse_slope = -0.1765 # volts per pH unit
    return (ph_adc.voltage - neutral_voltage) / inverse_slope + 7.0
