# get_data.py
import numpy as np
import sys
import time
from time import sleep
import json

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
pin_num = 17
pin_num2 = 27

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
chan2 = AnalogIn(ads, ADS.P2) # TODO: is this the right ADC pin?

# dissolved oxygen sensor constants
VREF = 5000 # VREF (mv) // TODO: should this be 5V or 3.3V
ADC_RES = 65535 # ADC Resolution is 16 bits
# saturation dissolved oxygen concentrations at various temperatures
do_table = [14460, 14220, 13820, 13440, 13090, 12740, 12420, 12110, 11810, 11530,
            11260, 11010, 10770, 10530, 10300, 10080, 9860, 9660, 9460, 9270,
            9080, 8900, 8730, 8570, 8410, 8250, 8110, 7960, 7820, 7690,
            7560, 7430, 7300, 7180, 7070, 6950, 6840, 6730, 6630, 6530, 6410]

# main function that calls on all other functions to generate data list
def get_data(last_distance, last_wtemp, last_hum, last_atemp, last_do, do_cal1_v, do_cal1_t):
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

    # read dissolved oxygen sensor
    do = get_do(do_cal1_v, do_cal1_t, wtemp)
    if is_nan(do):
        do = last_do

    #read flow rate
    #flow1 = get_flow_rate(12, 4.8)
    #flow2 = get_flow_rate(13, 0.273)

    return pH, TDS, hum, atemp, wtemp, distance, do  #, flow1, flow2

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

# Dissolved Oxygen Sensor (SKU:SEN0237) functions
# Based on the following arduino code
    # https://wiki.dfrobot.com/Gravity__Analog_Dissolved_Oxygen_Sensor_SKU_SEN0237#target_3

# read sensor and convert to mg/L dissolved oxygen
def get_do(cal1_v, cal1_t, wtemp_c):
    V_saturation = cal1_v + 35 * wtemp_c - cal1_t * 35
    voltage_mv = get_do_voltage()
    do_ug_l = voltage_mv * do_table[wtemp_c] / V_saturation # micrograms per liter
    return do_ug_l / 1000 # milligrams per liter

# returns raw reading from do sensor
def read_do_raw():
    return chan2.voltage

# returns converted voltage from do sensor
def get_do_voltage():
    return read_do_raw() * VREF / ADC_RES

# returns if do sensor has been calibrated in the last month
def is_do_calibrated(curr_time):
    with open("do_calibration.json", "r") as f:
        do_calib_data = json.load(f)
    last_time = do_calib_data["last_calibrated_time"]
    # the internet recommends callibrating the SEN0237 sensor monthly
    if not last_time:
        return False
    sec_per_month = 60*60*24*30
    time_elapsed = curr_time - last_time
    print(curr_time, last_time, time_elapsed, sec_per_month)
    print(time_elapsed > sec_per_month)
    print(type(time_elapsed), type(sec_per_month))
    return time_elapsed < sec_per_month

# calibrate do sensor by printing instructions, reading the sensor, and saving user-provided value to file
def calibrate_do():
    input("""
        Please calibrate the dissolved oxygen sensor, which should be done at least monthly. See details on the single-point calibration steps (https://wiki.dfrobot.com/Gravity__Analog_Dissolved_Oxygen_Sensor_SKU_SEN0237#target_3). Here are quickstart instructions to callibrate the SEN0237 dissolved oxygen sensor:
        \t1. Prepare the probe
        \t2. Wet the probe in pure water and shake off excess water drops
        \t3. Expose the probe to the air and maintain proper air flow (do not use a fan to blow)
        \t4. Press any key to continue this script and start data collection
        \t5. After the output voltage is stable (about 1 min), record the voltage, which is the saturated dissolved oxygen voltage at the current temperature
        \t6. Exit data collection with CTRL+C and enter the voltage
        """)
    # get sensor readings from do (voltage) and dht (air temperature)
    try:
        while True:
            voltage = get_do_voltage()
            raw = read_do_raw()
            print(f"Raw: {raw} \tVoltage(mv): {voltage}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        cal_v = input("\nEnter stable voltage (mv): ")
        atemp, hum = get_dht()
        if is_nan(atemp):
            atemp = input("Unable to get valid air temperature reading, please enter a value.\n Air temp (C): ")
        else:
            print(f"Proceeding with measured air temperature value of {atemp}")
        # update calibration values in json file
        with open("do_calibration.json", "r") as f:
            data = json.load(f)
        data["CAL1_V"] = cal_v
        data["CAL1_T"] = atemp
        data["last_calibrated_time"] = round(time.time())
        with open("do_calibration.json", "w") as f:
            json.dump(data, f)
        print("calibration values saved to file!")

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
