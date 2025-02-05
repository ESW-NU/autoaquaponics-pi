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
pin_num_TDS = 07
pin_num_Dis = 14

# "GPIO.BCM" - Broadcom SOC channel numbers; "GPIO.BOARD" - physical pin headers on Pi
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(pin_num_TDS,GPIO.OUT)
GPIO.setup(pin_num_Dis,GPIO.OUT)

# initialize I2C bus
# I2C - comm protocol. SCL - clock line, synchronizes comm between master (Pi) and slave (sensor) device
# board.SDA - pin designated as the I2C data line
i2c = busio.I2C(board.SCL, board.SDA)

# Variable of DHT22 (best of DHT family) sensor object. Board.D14 - pin where DHT connected. 
# Sensor class of adafruit DHT library. Considering use pulseio for temperature readings. 
dhtDevice = adafruit_dht.DHT22(board.D14, use_pulseio=False)

# To do: figure out what device this is for
base_dir = '/sys/bus/w1/devices/'
try:
    device_folder = glob.glob(base_dir + '28*')[0]
    device_file = device_folder + '/w1_slave'
except:
    device_file = None

#create ADS object
# gain determines the precision of the voltage being read - this gain is pretty low

ads = ADS.ADS1115(i2c)
ads.gain = 2/3
#single ended mode read for pin 0 and 1. "ground" is the relative measure (0), chan1 is one of the ones being measured
ground = AnalogIn(ads, ADS.P0)
raw_tds_chan1 = AnalogIn(ads, ADS.P1)

# working backwards
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
    pH = -5.82*ground.voltage + 22.1  #calibrated equation
    pH = pH/3  #wrong thing
    #pH = ground.voltage
    
    #read air temp and air humidity
    atemp, hum = get_dht()
    if type(hum) != float or type(atemp) != float:
        hum, atemp = last_hum, last_atemp
    distance = 58.42 - get_distance(last_distance)
    
    #read flow rate
    #flow1 = get_flow_rate(12, 4.8)
    #flow2 = get_flow_rate(13, 0.273)

    return pH, TDS, hum, atemp, wtemp, distance  #, flow1, flow2

# Temperature sensor (DS18B20) functions
#change wording later if applicable 
def read_temp_raw():
    try:
        temp_data = open(device_file, 'r')
    except:
        return []
    lines = temp_data.readlines()
    temp_data.close()
    return lines

# Runs 5 attempts to read the temp file - if valid data isn't found (looks for 'YES' at the end of a line), it tries again
# np.nan means not a number - returns "nan"
def get_water_temp():
    for attempts in range(5):
        lines = read_temp_raw()
        if len(lines) > 0:  #only index below if lines is not empty
            while lines[0].strip()[-3:] != 'YES':
                time.sleep(0.2)
                lines = read_temp_raw()
		# finds where the temp value is; temp_string +2 because that's the precision we're reading 
            temp_value_pos = lines[1].find('t=')
            if temp_value_pos != -1:
                temp_string = lines[1][temp_value_pos+2:]
                temp_c = float(temp_string) / 1000.0
                return temp_c
            break
    return np.nan
        
#TDS sensor function

def get_tds(wtemp):
    Vtds_raw = raw_tds_chan1.voltage        #raw reading from sensor right now
    TheoEC = 684                    #theoretical EC (electrical conductivity) of calibration fluid (calibrated with 342 ppm of aqueous NaCl)
    Vc = 1.085751885                #voltage reading of sensor when calibrating
    temp_calibrate = 23.25          #measured water temp when calibrating
    rawECsol = TheoEC*(1+0.02*(temp_calibrate-25))  #temp compensate the calibrated values
    K = (rawECsol)/(133.42*(Vc**3)-255.86*(Vc**2)+857.39*Vc)  #defined calibration factor K for NaCl (this will have to be readjusted for specific solution in tank)
    EC_raw = K*(133.42*(Vtds_raw**3)-255.86*(Vtds_raw**2)+857.39*Vtds_raw)
    EC = EC_raw/(1+0.02*(wtemp-25)) #use current temp for temp compensation
    TDS = EC/2                      #TDS is just half of electrical conductivity in ppm
    return TDS


#DHT function
def get_dht():
#Define temperature and humidity
    temperature_c = np.nan
    humidity = np.nan
    while is_nan(temperature_c) or is_nan(humidity):  #test to see if the value is still nan
        try:
            # get temp and humidity
            temperature_c = dhtDevice.temperature
            humidity = dhtDevice.humidity
        except RuntimeError as error:
            # Errors happen fairly often, DHT's are hard to read. Sets to NaN to restart the function.
            temperature_c = float('NaN')
            humidity = float('NaN')
        except Exception as error:
# If unexpected error, release resources used by the sensor and notifies caller
            dhtDevice.exit() 
            raise error
    return temperature_c, humidity

def is_nan(x):  #used in DHT function
    return (x is np.nan or x != x)

def get_distance(last_distance):  #output distance in cm
    #setup distance sensing
    new_reading = False # Flag to indicate a valid measurement
    counter = 0 #Retry attempts on failed readings
    GPIO_TRIGGER = 6  #set GPIO Pins. 6 sends ultrasonic pulse
    GPIO_ECHO = 18 #Listens for the reflected pulse
    GPIO.setup(GPIO_TRIGGER, GPIO.OUT)  #set GPIO direction (IN / OUT)
    GPIO.setup(GPIO_ECHO, GPIO.IN)
    
    # set Trigger to HIGH
    StopTime = time.time()
    GPIO.output(GPIO_TRIGGER, True) #Start pulse
    
    # set Trigger after 0.01ms to LOW
    time.sleep(0.00006)
    GPIO.output(GPIO_TRIGGER, False) #End pulse
    StartTime = time.time() # Start of pulse
    
    # save StartTime
    while GPIO.input(GPIO_ECHO) == 0:
        pass
        counter += 1  #stop loop if it gets stuck
        if counter == 5000: # We don’t know why it is 5000
            new_reading = True
            break
    StartTime = time.time() # Start of pulse, for error
    
    # save time of arrival of the pulse
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

#Spinny pin raises voltage, when it falls it calls the anonymous function countPulse
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
    
#This should probably be in the main body of the function.
#     except KeyboardInterrupt:
#         print('\nkeyboard interrupt!')
#         GPIO.cleanup()
#         sys.exit()


