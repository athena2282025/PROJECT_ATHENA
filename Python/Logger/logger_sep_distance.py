import serial
import csv
import time
import os
from datetime import datetime
import math

# --- Configuration ---
COM_PORT = 'COM5'
BAUD_RATE = 115200
FILE_NAME = r'D:\mpu9250_data.csv'
SUMMARY_FILE = r'D:\mpu9250_distance_summary.csv'
# ---------------------

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def log_serial_data():
    """Reads data from the serial port and writes it to a CSV file."""
    
    ser = None
    csvfile = None
    summary_file = None
    
    try:
        print("="*70)
        print(" MPU9250 DATA LOGGER WITH DISTANCE MEASUREMENT")
        print("="*70)
        print(f"Attempting to open serial port {COM_PORT}...")
        
        ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
        print(f"SUCCESS: Serial port {COM_PORT} opened at {BAUD_RATE} baud")
        time.sleep(2)
        ser.flushInput()
        ser.flushOutput()
        
        print(f"Opening CSV file: {FILE_NAME}")
        csvfile = open(FILE_NAME, 'w', newline='', encoding='utf-8', buffering=1)
        csv_writer = csv.writer(csvfile)
        
        print(f"Opening distance summary file: {SUMMARY_FILE}")
        summary_file = open(SUMMARY_FILE, 'w', newline='', encoding='utf-8', buffering=1)
        summary_writer = csv.writer(summary_file)
        summary_writer.writerow(['session_number', 'start_time', 'end_time', 'duration_sec', 
                                 'distance_x_m', 'distance_y_m', 'distance_z_m', 'total_distance_m', 'num_samples'])
        summary_file.flush()
        
        print(f"SUCCESS: Files ready")
        print("="*70)
        print("")
        print("WAITING FOR BUTTON PRESS ON ESP32...")
        print("")

        index_counter = 0
        header_written = False
        is_logging = False
        session_start = None
        session_number = 0
        
        # Distance tracking variables
        start_pos_x = 0
        start_pos_y = 0
        start_pos_z = 0
        current_pos_x = 0
        current_pos_y = 0
        current_pos_z = 0

        while True:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if not line:
                        continue

                    # Protocol Handling
                    if "LOGGING STARTED" in line:
                        clear_screen()
                        session_start = datetime.now()
                        session_number += 1
                        
                        # Reset distance tracking for new session
                        start_pos_x = 0
                        start_pos_y = 0
                        start_pos_z = 0
                        current_pos_x = 0
                        current_pos_y = 0
                        current_pos_z = 0
                        
                        print("="*70)
                        print(f" LOGGING SESSION #{session_number}")
                        print("="*70)
                        print(f"Started: {session_start.strftime('%H:%M:%S')}")
                        print(f"Saving to: {FILE_NAME}")
                        print("-"*70)
                        print(f"{'Entry':<8} {'Time(ms)':<12} {'Yaw':<8} {'Pitch':<8} {'Roll':<8} {'Pos X':<10} {'Pos Y':<10} {'Pos Z':<10}")
                        print("-"*70)
                        is_logging = True
                        index_counter = 0
                        header_written = False
                        continue
                    
                    elif line.startswith("unixtime_ms") or "unixtime_ms" in line:
                        if not header_written:
                            header_parts = line.split(',')
                            csv_writer.writerow(header_parts)
                            csvfile.flush()
                            header_written = True
                        continue
                        
                    elif "LOGGING STOPPED" in line:
                        session_end = datetime.now()
                        duration = (session_end - session_start).total_seconds() if session_start else 0
                        
                        # Calculate total distance moved
                        distance_x = current_pos_x - start_pos_x
                        distance_y = current_pos_y - start_pos_y
                        distance_z = current_pos_z - start_pos_z
                        total_distance = math.sqrt(distance_x**2 + distance_y**2 + distance_z**2)
                        
                        # Write summary to distance file
                        summary_writer.writerow([
                            session_number,
                            session_start.strftime('%Y-%m-%d %H:%M:%S'),
                            session_end.strftime('%Y-%m-%d %H:%M:%S'),
                            round(duration, 2),
                            round(distance_x, 3),
                            round(distance_y, 3),
                            round(distance_z, 3),
                            round(total_distance, 3),
                            index_counter
                        ])
                        summary_file.flush()
                        
                        print("-"*70)
                        print(f"LOGGING STOPPED")
                        print(f"Duration: {duration:.1f} seconds")
                        print(f"Samples: {index_counter}")
                        print("")
                        print("DISTANCE MOVED:")
                        print(f"  X-axis: {distance_x:>10.3f} m")
                        print(f"  Y-axis: {distance_y:>10.3f} m")
                        print(f"  Z-axis: {distance_z:>10.3f} m")
                        print(f"  Total:  {total_distance:>10.3f} m")
                        print("")
                        print(f"Data saved to: {FILE_NAME}")
                        print(f"Distance summary saved to: {SUMMARY_FILE}")
                        print("="*70)
                        print("")
                        print("WAITING FOR BUTTON PRESS ON ESP32...")
                        print("")
                        is_logging = False
                        csvfile.flush()
                        continue
                    
                    # Data Parsing
                    if is_logging and header_written:
                        parts = line.split(',')
                        
                        if len(parts) == 10:
                            try:
                                data_row = [float(p) for p in parts]
                                csv_writer.writerow(data_row)
                                csvfile.flush()
                                
                                index_counter += 1
                                
                                timestamp = data_row[0]
                                yaw = data_row[1]
                                pitch = data_row[2]
                                roll = data_row[3]
                                current_pos_x = data_row[7]
                                current_pos_y = data_row[8]
                                current_pos_z = data_row[9]
                                
                                # Store starting position from first sample
                                if index_counter == 1:
                                    start_pos_x = current_pos_x
                                    start_pos_y = current_pos_y
                                    start_pos_z = current_pos_z
                                
                                print(f"{index_counter:<8} {timestamp:<12.0f} {yaw:<8.2f} {pitch:<8.2f} {roll:<8.2f} {current_pos_x:<10.3f} {current_pos_y:<10.3f} {current_pos_z:<10.3f}")
                                    
                            except ValueError:
                                pass
                                    
                except Exception as e:
                    print(f"Error: {e}")
            
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n")
        print("="*70)
        print(" LOGGING INTERRUPTED BY USER")
        print("="*70)
    except serial.SerialException as e:
        print(f"ERROR: Cannot open serial port {COM_PORT}")
        print(f"Details: {e}")
        print("Check: port name, device connection, close Arduino IDE Serial Monitor")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        if csvfile:
            try:
                csvfile.flush()
                csvfile.close()
                print(f"CSV file saved: {FILE_NAME}")
            except:
                pass
        if summary_file:
            try:
                summary_file.flush()
                summary_file.close()
                print(f"Distance summary saved: {SUMMARY_FILE}")
            except:
                pass
        if ser:
            try:
                ser.close()
                print(f"Serial port closed")
            except:
                pass
        print(f"Total entries logged: {index_counter}")


if __name__ == '__main__':
    log_serial_data()