#include <MPU9250_WE.h>
#include <Wire.h>
#include <MadgwickAHRS.h>

#define MPU9250_ADDR 0x68
#define BUTTON_PIN 13

MPU9250_WE myMPU9250 = MPU9250_WE(MPU9250_ADDR);
Madgwick filter;

bool isLogging = false;
bool headerSent = false;

// Position tracking from origin (0,0,0)
float px = 0, py = 0, pz = 0;
float vx = 0, vy = 0, vz = 0;
unsigned long prevTime = 0;

// Offset for gravity calibration (m/s^2)
float gravity_offset_x = 0;
float gravity_offset_y = 0;
float gravity_offset_z = 0;

void setup() {
  Serial.begin(115200);

  // Initialize I2C (match example: begin, small delay, then init)
  Wire.begin();
  // Optional: use fast I2C if your board and wiring support it
  Wire.setClock(400000);
  delay(10); // give wire a moment to settle

  pinMode(BUTTON_PIN, INPUT_PULLUP);

  // Initialize sensor (same order as example)
  if (!myMPU9250.init()) {
    Serial.println("MPU9250 does not respond");
    // NOTE: example only prints the message and continues. If you want to halt, uncomment next line.
    // while (1);
  } else {
    Serial.println("MPU9250 is connected");
  }

  // Match example: prompt, wait, then autoOffsets
  Serial.println("Position you MPU9250 flat and don't move it - calibrating...");
  delay(1000);
  myMPU9250.autoOffsets();
  delay(200); // allow offsets to settle

  // Read raw accel once to compute gravity offsets (convert g->m/s^2)
  xyzFloat accel = myMPU9250.getGValues();
  gravity_offset_x = accel.x * 9.81f;
  gravity_offset_y = accel.y * 9.81f;
  // subtract 1 g on Z so flat sensor => az = 0 after offset
  gravity_offset_z = accel.z * 9.81f - 9.81f;

  Serial.println("Calibration complete");

  // Sensor configuration (exactly like example)
  myMPU9250.setSampleRateDivider(5);
  myMPU9250.setAccRange(MPU9250_ACC_RANGE_2G);
  myMPU9250.enableAccDLPF(true);
  myMPU9250.setAccDLPF(MPU9250_DLPF_6);

  // Start the filter (sample frequency in Hz). Place after sensor config.
  filter.begin(100);

  Serial.println("Press button to start logging");
  prevTime = millis();
}

void loop() {
  // Button handling
  if (digitalRead(BUTTON_PIN) == LOW) {
    if (!isLogging) {
      isLogging = true;
      headerSent = false;

      // Reset position to origin
      px = py = pz = 0;
      vx = vy = vz = 0;
      prevTime = millis();

      Serial.println("--- LOGGING STARTED ---");
      delay(200);
    }
  } else {
    if (isLogging) {
      isLogging = false;
      Serial.println("--- LOGGING STOPPED ---");
      delay(200);
    }
  }

  if (isLogging) {
    if (!headerSent) {
      Serial.println("unixtime_ms,yaw_deg,pitch_deg,roll_deg,acc_x_ms2,acc_y_ms2,acc_z_ms2,pos_x_m,pos_y_m,pos_z_m");
      headerSent = true;
    }

    // Read sensor data
    xyzFloat accel = myMPU9250.getGValues();
    float ax = accel.x * 9.81f - gravity_offset_x;
    float ay = accel.y * 9.81f - gravity_offset_y;
    float az = accel.z * 9.81f - gravity_offset_z;

    xyzFloat gyro = myMPU9250.getGyrValues();
    // Note: MPU9250 library returns gyro in deg/s by default (check your library settings)
    float gx = gyro.x;
    float gy = gyro.y;
    float gz = gyro.z;

    xyzFloat mag = myMPU9250.getMagValues();
    float mx = mag.x;
    float my = mag.y;
    float mz = mag.z;

    // Update orientation filter
    // IMPORTANT: Madgwick expects gyro in deg/s, accel in m/s^2 (or normalized g depending on implementation),
    // and mag in uT (library-specific). Below we pass gyro (deg/s), accel (m/s^2), mag (raw).
    // If your Madgwick expects normalized accel (g), feed accel/9.81 instead.
    filter.update(gx, gy, gz, ax, ay, az, mx, my, mz);

    float roll = filter.getRoll();
    float pitch = filter.getPitch();
    float yaw = filter.getYaw();

    // Calculate time delta
    unsigned long currTime = millis();
    float dt = (currTime - prevTime) / 1000.0f;
    prevTime = currTime;

    // Transform acceleration to world frame
    float rollRad = roll * DEG_TO_RAD;
    float pitchRad = pitch * DEG_TO_RAD;
    float yawRad = yaw * DEG_TO_RAD;

    // Rotation matrix transformation
    float cos_pitch = cos(pitchRad);
    float sin_pitch = sin(pitchRad);
    float cos_roll = cos(rollRad);
    float sin_roll = sin(rollRad);
    float cos_yaw = cos(yawRad);
    float sin_yaw = sin(yawRad);

    // Transform to world frame
    float ax_world = ax * (cos_yaw * cos_pitch) + ay * (cos_yaw * sin_pitch * sin_roll - sin_yaw * cos_roll) + az * (cos_yaw * sin_pitch * cos_roll + sin_yaw * sin_roll);
    float ay_world = ax * (sin_yaw * cos_pitch) + ay * (sin_yaw * sin_pitch * sin_roll + cos_yaw * cos_roll) + az * (sin_yaw * sin_pitch * cos_roll - cos_yaw * sin_roll);
    float az_world = ax * (-sin_pitch) + ay * (cos_pitch * sin_roll) + az * (cos_pitch * cos_roll);

    // Integrate to velocity
    vx += ax_world * dt;
    vy += ay_world * dt;
    vz += az_world * dt;

    // Integrate to position (distance from origin)
    px += vx * dt;
    py += vy * dt;
    pz += vz * dt;

    // Output CSV format
    Serial.print(currTime);
    Serial.print(",");
    Serial.print(yaw, 2);
    Serial.print(",");
    Serial.print(pitch, 2);
    Serial.print(",");
    Serial.print(roll, 2);
    Serial.print(",");
    Serial.print(ax_world, 3);
    Serial.print(",");
    Serial.print(ay_world, 3);
    Serial.print(",");
    Serial.print(az_world, 3);
    Serial.print(",");
    Serial.print(px, 3);
    Serial.print(",");
    Serial.print(py, 3);
    Serial.print(",");
    Serial.println(pz, 3);

    delay(100);
  }
}
