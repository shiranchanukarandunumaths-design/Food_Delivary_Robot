#include <Arduino.h>
#include "config.h"
#include "HX711.h"

// Hardware instances
HX711 scale;

// System States
enum RobotState {
  STATE_IDLE,
  STATE_DRIVING,
  STATE_OBSTACLE_STOP,
  STATE_WATCHDOG_TRIP,
  STATE_ESTOP_ACTIVE
};

RobotState currentState = STATE_IDLE;

// Motor command values (-255 to 255)
int leftSpeedCmd = 0;
int rightSpeedCmd = 0;

// Sensor readings
int frontDistCm = 100;
int leftDistCm = 100;
int rightDistCm = 100;
long loadGrams = 0;
float batteryVolts = 12.0;

// Timers
unsigned long lastCommandTime = 0;
unsigned long lastTelemetryTime = 0;
unsigned long lastSensorReadTime = 0;

// Function prototypes
void setupMotors();
void setMotors(int left, int right);
void stopMotors();
void emergencyStop();
int readUltrasonic(int trigPin, int echoPin);
void readSensors();
void parseSerialCommand(String cmd);
void sendTelemetry();

void setup() {
  Serial.begin(SERIAL_BAUD_RATE);
  while (!Serial && millis() < 2000); // Wait for serial up to 2 seconds

  pinMode(PIN_ESTOP_BUTTON, INPUT_PULLUP);

  setupMotors();

  // Initialize Ultrasonic Pins
  pinMode(PIN_US_FRONT_TRIG, OUTPUT);
  pinMode(PIN_US_FRONT_ECHO, INPUT);
  pinMode(PIN_US_LEFT_TRIG, OUTPUT);
  pinMode(PIN_US_LEFT_ECHO, INPUT);
  pinMode(PIN_US_RIGHT_TRIG, OUTPUT);
  pinMode(PIN_US_RIGHT_ECHO, INPUT);

  // Initialize Load Cell
  scale.begin(PIN_HX711_DOUT, PIN_HX711_SCK);
  // scale.set_scale(calibration_factor); // Adjust after calibration
  // scale.tare();

  lastCommandTime = millis();
  Serial.println(F("SYSTEM_READY: ESP32 Robot Firmware Initialized"));
}

void loop() {
  unsigned long now = millis();

  // 1. Check Hardware E-Stop Button (Active LOW)
  if (digitalRead(PIN_ESTOP_BUTTON) == LOW) {
    currentState = STATE_ESTOP_ACTIVE;
    emergencyStop();
  }

  // 2. Read Serial Commands from Pi / Controller
  while (Serial.available() > 0) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      parseSerialCommand(line);
      lastCommandTime = now;
    }
  }

  // 3. Periodic Sensor Readings (every 50 ms)
  if (now - lastSensorReadTime >= 50) {
    lastSensorReadTime = now;
    readSensors();
  }

  // 4. Watchdog Timer Check
  if (currentState != STATE_ESTOP_ACTIVE) {
    if (now - lastCommandTime > WATCHDOG_TIMEOUT_MS) {
      if (leftSpeedCmd != 0 || rightSpeedCmd != 0) {
        stopMotors();
        currentState = STATE_WATCHDOG_TRIP;
      }
    }
  }

  // 5. Fail-Safe Obstacle Prevention
  if (currentState != STATE_ESTOP_ACTIVE) {
    if (frontDistCm > 0 && frontDistCm <= OBSTACLE_STOP_CM) {
      if (leftSpeedCmd > 0 || rightSpeedCmd > 0) {
        stopMotors();
        currentState = STATE_OBSTACLE_STOP;
      }
    } else if (currentState == STATE_OBSTACLE_STOP) {
      // Clear obstacle stop once path is clear
      currentState = (leftSpeedCmd == 0 && rightSpeedCmd == 0) ? STATE_IDLE : STATE_DRIVING;
    }
  }

  // 6. Apply Motor Output
  if (currentState == STATE_ESTOP_ACTIVE || currentState == STATE_WATCHDOG_TRIP || currentState == STATE_OBSTACLE_STOP) {
    stopMotors();
  } else {
    setMotors(leftSpeedCmd, rightSpeedCmd);
  }

  // 7. Periodic Telemetry Broadcast to Pi (10 Hz)
  if (now - lastTelemetryTime >= TELEMETRY_INTERVAL) {
    lastTelemetryTime = now;
    sendTelemetry();
  }
}

// ==========================================
// MOTOR CONTROL (BTS7960)
// ==========================================

void setupMotors() {
  pinMode(PIN_LEFT_R_EN, OUTPUT);
  pinMode(PIN_LEFT_L_EN, OUTPUT);
  pinMode(PIN_RIGHT_R_EN, OUTPUT);
  pinMode(PIN_RIGHT_L_EN, OUTPUT);

  // Enable driver chips
  digitalWrite(PIN_LEFT_R_EN, HIGH);
  digitalWrite(PIN_LEFT_L_EN, HIGH);
  digitalWrite(PIN_RIGHT_R_EN, HIGH);
  digitalWrite(PIN_RIGHT_L_EN, HIGH);

  // Configure ESP32 LEDC PWM
  ledcSetup(PWM_CH_LEFT_FWD, PWM_FREQ, PWM_RES);
  ledcSetup(PWM_CH_LEFT_REV, PWM_FREQ, PWM_RES);
  ledcSetup(PWM_CH_RIGHT_FWD, PWM_FREQ, PWM_RES);
  ledcSetup(PWM_CH_RIGHT_REV, PWM_FREQ, PWM_RES);

  ledcAttachPin(PIN_LEFT_RPWM, PWM_CH_LEFT_FWD);
  ledcAttachPin(PIN_LEFT_LPWM, PWM_CH_LEFT_REV);
  ledcAttachPin(PIN_RIGHT_RPWM, PWM_CH_RIGHT_FWD);
  ledcAttachPin(PIN_RIGHT_LPWM, PWM_CH_RIGHT_REV);

  stopMotors();
}

void setMotors(int left, int right) {
  left = constrain(left, -255, 255);
  right = constrain(right, -255, 255);

  // Left side Motor 
  if (left > 0) {
    ledcWrite(PWM_CH_LEFT_FWD, left);
    ledcWrite(PWM_CH_LEFT_REV, 0);
  } else if (left < 0) {
    ledcWrite(PWM_CH_LEFT_FWD, 0);
    ledcWrite(PWM_CH_LEFT_REV, -left);
  } else {
    ledcWrite(PWM_CH_LEFT_FWD, 0);
    ledcWrite(PWM_CH_LEFT_REV, 0);
  }

  // Right Motor
  if (right > 0) {
    ledcWrite(PWM_CH_RIGHT_FWD, right);
    ledcWrite(PWM_CH_RIGHT_REV, 0);
  } else if (right < 0) {
    ledcWrite(PWM_CH_RIGHT_FWD, 0);
    ledcWrite(PWM_CH_RIGHT_REV, -right);
  } else {
    ledcWrite(PWM_CH_RIGHT_FWD, 0);
    ledcWrite(PWM_CH_RIGHT_REV, 0);
  }

  if (left != 0 || right != 0) {
    currentState = STATE_DRIVING;
  } else if (currentState == STATE_DRIVING) {
    currentState = STATE_IDLE;
  }
}

void stopMotors() {
  ledcWrite(PWM_CH_LEFT_FWD, 0);
  ledcWrite(PWM_CH_LEFT_REV, 0);
  ledcWrite(PWM_CH_RIGHT_FWD, 0);
  ledcWrite(PWM_CH_RIGHT_REV, 0);
}

void emergencyStop() {
  stopMotors();
  digitalWrite(PIN_LEFT_R_EN, LOW);
  digitalWrite(PIN_LEFT_L_EN, LOW);
  digitalWrite(PIN_RIGHT_R_EN, LOW);
  digitalWrite(PIN_RIGHT_L_EN, LOW);
}

// ==========================================
// SENSORS
// ==========================================

int readUltrasonic(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 25000); // 25ms timeout (~4m max)
  if (duration == 0) return 400; // Out of range / clear
  return duration * 0.034 / 2;
}

void readSensors() {
  frontDistCm = readUltrasonic(PIN_US_FRONT_TRIG, PIN_US_FRONT_ECHO);
  leftDistCm = readUltrasonic(PIN_US_LEFT_TRIG, PIN_US_LEFT_ECHO);
  rightDistCm = readUltrasonic(PIN_US_RIGHT_TRIG, PIN_US_RIGHT_ECHO);

  // Read Load Cell (HX711) non-blocking if ready
  if (scale.is_ready()) {
    loadGrams = scale.get_units(1); // Single reading
  }

  // Read Battery Voltage via ADC
  int rawAdc = analogRead(PIN_BATTERY_ADC);
  batteryVolts = (rawAdc / 4095.0f) * 3.3f * VOLTAGE_DIVIDER_RATIO;
}

// ==========================================
// SERIAL PROTOCOL PARSER
// ==========================================

void parseSerialCommand(String cmd) {
  if (cmd.startsWith("DRIVE,")) {
    // Expected: DRIVE,<left_speed>,<right_speed>
    int firstComma = cmd.indexOf(',');
    int secondComma = cmd.indexOf(',', firstComma + 1);
    if (secondComma != -1) {
      int left = cmd.substring(firstComma + 1, secondComma).toInt();
      int right = cmd.substring(secondComma + 1).toInt();

      if (currentState != STATE_ESTOP_ACTIVE) {
        leftSpeedCmd = left;
        rightSpeedCmd = right;
        currentState = (left == 0 && right == 0) ? STATE_IDLE : STATE_DRIVING;
      }
    }
  } else if (cmd == "STOP") {
    leftSpeedCmd = 0;
    rightSpeedCmd = 0;
    stopMotors();
    if (currentState != STATE_ESTOP_ACTIVE) {
      currentState = STATE_IDLE;
    }
  } else if (cmd == "ESTOP") {
    currentState = STATE_ESTOP_ACTIVE;
    emergencyStop();
  } else if (cmd == "RESET_ESTOP") {
    digitalWrite(PIN_LEFT_R_EN, HIGH);
    digitalWrite(PIN_LEFT_L_EN, HIGH);
    digitalWrite(PIN_RIGHT_R_EN, HIGH);
    digitalWrite(PIN_RIGHT_L_EN, HIGH);
    currentState = STATE_IDLE;
  } else if (cmd == "GET_STATUS") {
    sendTelemetry();
  }
}

// ==========================================
// TELEMETRY OUTPUT
// ==========================================

void sendTelemetry() {
  const char* stateStr = "IDLE";
  switch (currentState) {
    case STATE_IDLE: stateStr = "IDLE"; break;
    case STATE_DRIVING: stateStr = "DRIVING"; break;
    case STATE_OBSTACLE_STOP: stateStr = "OBSTACLE_STOP"; break;
    case STATE_WATCHDOG_TRIP: stateStr = "WATCHDOG_TRIP"; break;
    case STATE_ESTOP_ACTIVE: stateStr = "ESTOP_ACTIVE"; break;
  }

  // STATUS,<load_g>,<front_cm>,<left_cm>,<right_cm>,<batt_v>,<state>
  Serial.print("STATUS,");
  Serial.print(loadGrams);
  Serial.print(",");
  Serial.print(frontDistCm);
  Serial.print(",");
  Serial.print(leftDistCm);
  Serial.print(",");
  Serial.print(rightDistCm);
  Serial.print(",");
  Serial.print(batteryVolts, 2);
  Serial.print(",");
  Serial.println(stateStr);
}
