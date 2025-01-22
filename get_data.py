# get_data.py
import numpy as np
import sys
import time
from time import sleep

#import necessary modules for I2C
import board
import busio

import RPi.GPIO as GPIO
#import board module (ADS1115)
import adafruit_ads1x15.ads1115 as ADS
#import ADS1x15 library's version of AnalogIn
from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_dht
#import the w1 water temp sensor module
import glob


#initialize GPIO pins for TDS sensor switch + distance sensor
pin_num = 07
pin_num2 = 14

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(pin_num,GPIO.OUT)
GPIO.setup(pin_num2,GPIO.OUT)

# initialize I2C bus
i2c = busio.I2C(board.SCL, board.SDA)

dhtDevice = adafruit_dht.DHT22(board.D14, use_pulseio=False)

base_dir = '/sys/bus/w1/devices/'
try:
    device_folder = glob.glob(base_dir + '28*')[0]
    device_file = device_folder + '/w1_slave'
except:
    device_file = None

#create ADS object
ads = ADS.ADS1115(i2c)
ads.gain = 2/3
#single ended mode read for pin 0 and 1
chan = AnalogIn(ads, ADS.P0)
chan1 = AnalogIn(ads, ADS.P1)


def get_data(last_distance, last_wtemp, last_hum, last_atemp):  #main function that calls on all other functions to generate data list
    #read w1 water temp sensor
    wtemp = get_water_temp()
    GPIO.output(pin_num,GPIO.HIGH)  #turn TDS sensor on
    sleep(0.5)
    #call TDS function to get a value while pin is HIGH
    if wtemp == np.nan:  #use last wtemp value if it's NaN
        TDS = get_tds(last_wtemp)
    else:
        TDS = get_tds(wtemp)        
    GPIO.output(pin_num,GPIO.LOW)  #turn TDS sensor off
    sleep(0.5)
    
    #define readings from ADC
    pH = -5.82*chan.voltage + 22.1  #calibrated equation
    pH = pH/3  #wrong thing
    #pH = chan.voltage
    
    #read air temp and air humidity
    atemp, hum = get_dht()
    if type(hum) != float or type(atemp) != float:
        hum, atemp = last_hum, last_atemp
    distance = 58.42 - get_distance(last_distance)
    
    #read flow rate
    #flow1 = get_flow_rate(12, 4.8)
    #flow2 = get_flow_rate(13, 0.273)

    return pH, TDS, hum, atemp, wtemp, distance  #, flow1, flow2

#DS18B20 functions
def read_temp_raw():
    try:
        f = open(device_file, 'r')
    except:
        return []
    lines = f.readlines()
    f.close()
    return lines

def get_water_temp():
    for _ in range(5):
        lines = read_temp_raw()
        if len(lines) > 0:  #only index below if lines is not empty
            while lines[0].strip()[-3:] != 'YES':
                time.sleep(0.2)
                lines = read_temp_raw()
            equals_pos = lines[1].find('t=')
            if equals_pos != -1:
                temp_string = lines[1][equals_pos+2:]
                temp_c = float(temp_string) / 1000.0
                return temp_c
            break
    return np.nan
        
#TDS sensor function
def get_tds(wtemp):
    Vtds_raw = chan1.voltage        #raw reading from sensor right now
    TheoEC = 684                    #theoretical EC of calibration fluid
    Vc = 1.085751885                #v reading of sensor when calibrating
    temp_calibrate = 23.25          #measured water temp when calibrating
    rawECsol = TheoEC*(1+0.02*(temp_calibrate-25))  #temp compensate the calibrated values
    K = (rawECsol)/(133.42*(Vc**3)-255.86*(Vc**2)+857.39*Vc)  #defined calibration factor K
    EC_raw = K*(133.42*(Vtds_raw**3)-255.86*(Vtds_raw**2)+857.39*Vtds_raw)
    EC = EC_raw/(1+0.02*(wtemp-25)) #use current temp for temp compensation
    TDS = EC/2                      #TDS is just half of electrical conductivity in ppm
    return TDS

#DHT function
def get_dht():
    temperature_c = np.nan
    humidity = np.nan
    while is_nan(temperature_c) or is_nan(humidity):  #test to see if the value is still nan
        try:
            # get temp and humidity
            temperature_c = dhtDevice.temperature
            humidity = dhtDevice.humidity
        except RuntimeError as error:
            # Errors happen fairly often, DHT's are hard to read, just keep going
            temperature_c = float('NaN')
            humidity = float('NaN')
        except Exception as error:
            dhtDevice.exit()
            raise error
    return temperature_c, humidity

def is_nan(x):  #used in DHT function
    return (x is np.nan or x != x)

def get_distance(last_distance):  #output distance in cm
    #setup distance sensing
    new_reading = False
    counter = 0
    GPIO_TRIGGER = 6  #set GPIO Pins
    GPIO_ECHO = 18
    GPIO.setup(GPIO_TRIGGER, GPIO.OUT)  #set GPIO direction (IN / OUT)
    GPIO.setup(GPIO_ECHO, GPIO.IN)
    
    # set Trigger to HIGH
    StopTime = time.time()
    GPIO.output(GPIO_TRIGGER, True)
    
    # set Trigger after 0.01ms to LOW
    time.sleep(0.00006)
    GPIO.output(GPIO_TRIGGER, False)
    StartTime = time.time()
    
    # save StartTime
    while GPIO.input(GPIO_ECHO) == 0:
        pass
        counter += 1  #stop loop if it gets stuck
        if counter == 5000:
            new_reading = True
            break
    StartTime = time.time()
    
    # save time of arrival
    while GPIO.input(GPIO_ECHO) == 1:
        pass
    StopTime = time.time()
    
    # time difference between start and arrival
    TimeElapsed = StopTime - StartTime
    
    # multiply with the sonic speed (34300 cm/s) and divide by 2, because there and back
    if new_reading:
        return last_distance
    else:
        return (TimeElapsed * 34300)/2

# def get_flow_rate(FLOW_SENSOR_GPIO, k):
#     GPIO.setmode(GPIO.BCM)
#     GPIO.setup(FLOW_SENSOR_GPIO, GPIO.IN, pull_up_down = GPIO.PUD_UP)
#     global count
#     count = 0
#     start_counter = 0
#     def countPulse(channel):
#         global count
#         if start_counter == 1:
#             count = count+1
    
#     GPIO.add_event_detect(FLOW_SENSOR_GPIO, GPIO.FALLING, callback=countPulse)

#     try:
#         start_counter = 1
#         time.sleep(1)
#         start_counter = 0
#         flow = (count / k)*15.850323141489  # Pulse frequency (Hz) = 0.2Q, Q is flow rate in GPH.
#         print("The flow is: %.3f GPH" % (flow))
#         print("The count is: " + str(count))
#         count = 0
#         time.sleep(0.1)
    
#     except KeyboardInterrupt:
#         print('\nkeyboard interrupt!')
#         GPIO.cleanup()
#         sys.exit()
