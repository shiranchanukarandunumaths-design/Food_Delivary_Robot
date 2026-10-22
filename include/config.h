#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ==========================================
// PIN DEFINITIONS (ESP32 DevKit 30-pin)
// ==========================================

// --- Motor Driver (BTS7960 Left Side) ---
#define PIN_LEFT_RPWM       25 // Forward PWM
#define PIN_LEFT_LPWM       26 // Reverse PWM
#define PIN_LEFT_R_EN       27 // Forward Enable
#define PIN_LEFT_L_EN       14 // Reverse Enable

// --- Motor Driver (BTS7960 Right Side) ---
#define PIN_RIGHT_RPWM      32 // Forward PWM
#define PIN_RIGHT_LPWM      33 // Reverse PWM
#define PIN_RIGHT_R_EN      18 // Forward Enable
#define PIN_RIGHT_L_EN      19 // Reverse Enable

// --- PWM Configuration (ESP32 LEDC) ---
#define PWM_FREQ            20000 // 20 kHz (silent motor drive)
#define PWM_RES             8     // 8-bit resolution (0-255)
#define PWM_CH_LEFT_FWD     0
#define PWM_CH_LEFT_REV     1
#define PWM_CH_RIGHT_FWD    2
#define PWM_CH_RIGHT_REV    3

// --- Ultrasonic Sensors ---
#define PIN_US_FRONT_TRIG   12
#define PIN_US_FRONT_ECHO   13

#define PIN_US_LEFT_TRIG    4
#define PIN_US_LEFT_ECHO    16

#define PIN_US_RIGHT_TRIG   17
#define PIN_US_RIGHT_ECHO   5

// --- Load Cell (HX711) ---
#define PIN_HX711_DOUT      23
#define PIN_HX711_SCK       22

// --- Battery Voltage ADC ---
#define PIN_BATTERY_ADC     34 // Connected to voltage divider (12V -> 3.3V)
#define VOLTAGE_DIVIDER_RATIO 4.0f // Adjust according to resistor network

// --- Hardware Emergency Stop ---
#define PIN_ESTOP_BUTTON    35 // Active LOW pull-up button

// ==========================================
// SAFETY & OPERATIONAL PARAMETERS
// ==========================================
#define SERIAL_BAUD_RATE    115200
#define WATCHDOG_TIMEOUT_MS 2000  // Stop if no command within 2 seconds
#define OBSTACLE_STOP_CM    30    // Stop forward movement if distance < 30 cm
#define TELEMETRY_INTERVAL  100   // Send status every 100 ms (10 Hz)

#endif // CONFIG_H
