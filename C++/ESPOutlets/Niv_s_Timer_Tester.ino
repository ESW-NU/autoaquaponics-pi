/*
 Repeat timer example

 This example shows how to use hardware timer in ESP32. The timer calls onTimer
 function every second. The timer can be stopped with button attached to PIN 0
 (IO0).

 This example code is in the public domain.
 */

// Stop button is attached to PIN 0 (IO0)
#define BTN_STOP_ALARM    0
#include <string> 
#include <iostream> 
#include <stdint.h>

hw_timer_t * timer = NULL;
volatile SemaphoreHandle_t timerSemaphore;
portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED;

volatile uint32_t mins_counter = 0;    // counts the number of minutes that have passed in ten minute interval
volatile uint32_t tens_counter = 0;    // counts the number of ten-minute increments that have passed in current hour
volatile uint32_t hour_counter = 0;    // counts the number of hours that have passed in current day
volatile uint32_t day_counter = 0;     // counts the number of days that have passed in current week

uint32_t outlet_mode[15];              // array holding values for the mode an outlet is set to
uint32_t on_time[15];                  // array holding times at which outlets will turn on in ten-minute intervals from the start of the day
uint32_t on_or_off[15];                // array holding values for whether outlet is on or off 
uint32_t duration[15];                 // array holding the durations an outlet will be on in daily-repeat and time cycle modes
uint32_t cyc_cnts[15];                 // array that specifies how much time is left for on/off mode on outlets in time-cycle mode

// Interrupt that is called every minute and increments the time counters accordingly
void IRAM_ATTR on_min(){
  // Increment the counter every ten seconds 
  portENTER_CRITICAL_ISR(&timerMux);
  mins_counter++;
  if (mins_counter == 10){
    tens_counter++;
    mins_counter = 0;
  }
  if (tens_counter == 6){
    hour_counter++;
    tens_counter = 0;
  }
  if (hour_counter == 24){
    day_counter++;
    hour_counter = 0;
  }
  if (day_counter == 7){
    mins_counter = 0;
    tens_counter = 0;
    hour_counter = 0;
    day_counter = 0;
  }

  // for loop for checking counters against arrays and changing values
  // will check the mode for all outlets and change on/off and duration values accordingly
  // Needs to be in on_min interrupt because time_cycle values will change too quickly otherwise
  for (int i = 0; i < 15; i++) {
      mode = outlet_mode[i];
      swtich(mode){
        case 0:
        break;

        case 1:                                   // Time Cycle Mode (01) (mode 1)

        break;

        case 2:                                   // Daily Repeat Mode (10) (mode 2)
        break;

        case 3:                                   // Permanent State Mode (11) (mode 3)  
        break;
      }

  }

  portEXIT_CRITICAL_ISR(&timerMux);
  // Give a semaphore that we can check in the loop
  xSemaphoreGiveFromISR(timerSemaphore, NULL);
  // It is safe to use digitalRead/Write here if you want to toggle an output  
}

void setup() {
  Serial.begin(115200);

  // Set BTN_STOP_ALARM to input mode
  pinMode(BTN_STOP_ALARM, INPUT);

  // Create semaphore to inform us when the timer has fired
  timerSemaphore = xSemaphoreCreateBinary();

  // Use 1st timer of 4 (counted from zero).
  // Set 80 divider for prescaler (see ESP32 Technical Reference Manual for more
  // info).
  timer = timerBegin(0, 80, true);

  // Attach onTimer function to our timer.
 timerAttachInterrupt(timer, &on_min, true);

  // Set alarm to call onmin function every minute (value in microseconds).
  // Repeat the alarm (third parameter)
  timerAlarmWrite(timer, 60000000, true);

  // Start an alarm
  timerAlarmEnable(timer);

  pinMode(ledPin, OUTPUT);
}

void loop() {
  // If Timer has fired
  if (xSemaphoreTake(timerSemaphore, 0) == pdTRUE){
    uint32_t isrCount = 0, isrTime = 0;
    // Read the interrupt count and time
    portENTER_CRITICAL(&timerMux);
    //set counter values that will be checked in here
    portEXIT_CRITICAL(&timerMux);
  }
  
  // The message that has been received will be broken down into segments specified by
  // the AutoOutlet C++ Code Documentation on Google Drive: 
  // https://docs.google.com/document/d/17H-WvJsHd-YGuLblgH95uoM-LP0ZRlJ7i7fLkkYbfUw/edit
  
  uint32_t message;
  uint32_t req_mode = (message & 0x3);
  uint32_t blue_bits = (message >> 2) & 0xFF;
  uint32_t red_bits = (message >> 10) & 0x7FF;
  uint32_t green_bits = (message >> 21) & 0x7FF;


  // switch cases need to be placed in interrupt for receiving messages
  // will need its own interrupt
  switch (req_mode) {
    case 0:                                   // Initialization Mode (00)
      time = red_bits;                        // Message from RPi showing number of ten-minute intervals from start of day
      int hrs = time/60;                      // Number of hours from start of the day
      int tens = (time % 60) / 10;            // Number of ten minute intervals that have passed in given hour
      portENTER_CRITICAL(&timerMux);
      tens_counter = tens;
      hour_counter = hrs;                     // Counter values will be reset here based on time from RPi
      portEXIT_CRITICAL(&timerMux);
      break;

    case 1:                                   // Time Cycle Mode (01) (mode 1)
      uint32_t outlet_num = blue_bits;
      outlet_mode[outlet_num] = req_mode;
      uint32_t cyc_time = red_bits;
      duration[outlet_num] = red_bits;
      break;

    case 2:                                   // Daily Repeat Mode (10) (mode 2)
      uint32_t outlet_num = blue_bits;
      outlet_mode[outlet_num] = req_mode;
      uint32_t time_to_turn_on = red_bits;
      on_time[outlet_num] = time_to_turn_on;
      uint32_t duration_10 = green_bits;      // Gets duration in increments of 10 (i.e. value of 4 = 40 minutes)
      duration[outlet_num] = duration_10;
      break;

    case 3:                                   // Permanent State Mode (11) (mode 3)      
      uint32_t outlet_num = blue_bits;
      outlet_mode[outlet_num] = req_mode;
      uint32_t state = green_bits;
      on_or_off[outlet_num] = state;
      uint32_t permenant_or_not = red_bits;
      //duration[outlet_num] = INT_FAST#@_MAX; //use infinity to show we are in permanant mode
      break;      
  }


  // for loop for turning outlets on/off based on on_or_off array
  for (int i = 0; i < 15; i ++){
      power = on_or_off[i];
      // use if statements to turn on/off GPIO pins
      // make array of GPIO pins?
  }
}
