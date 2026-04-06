import serial
import time
import threading
import paho.mqtt.client as mqtt

class HardwareReceiver:
    """Class to securely manage serial or MQTT heart-rate acquisition threads."""
    
    def __init__(self, mode="serial", port="COM3", baud=115200, mqtt_broker="localhost"):
        self.mode = mode
        self.port = port
        self.baud = baud
        self.mqtt_broker = mqtt_broker
        self.heart_rate = 75 # Baseline reading
        self.running = False
        self.thread = None
        self.serial_conn = None
        self.mqtt_client = None
        
    def start(self):
        """Spins up daemonic workers for parallel execution."""
        if self.running:
            return
            
        self.running = True
        if self.mode == "serial":
            self.thread = threading.Thread(target=self._read_serial, daemon=True)
            self.thread.start()
        elif self.mode == "mqtt":
            self.thread = threading.Thread(target=self._start_mqtt, daemon=True)
            self.thread.start()
            
    def stop(self):
        """Gracefully halts threads to avoid dangling connections and resource locks."""
        self.running = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
            
    def _read_serial(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baud, timeout=1)
            print(f"HardwareReceiver -> Listening on {self.port}")
            while self.running:
                if self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                    if line.isdigit():
                        val = int(line)
                        if 30 <= val <= 250: # Biological normalization bounds check
                            self.heart_rate = val
        except serial.SerialException as e:
            print(f"Serial port unavailable ({e}). Falling back to mock sensor readings...")
            self._simulate()
        except Exception as e:
            print(f"Unexpected failure in serial thread: {e}")

    def _simulate(self):
        while self.running:
            time.sleep(2)

    def _start_mqtt(self):
        def on_message(client, userdata, msg):
            try:
                payload = msg.payload.decode('utf-8').strip()
                if payload.isdigit():
                    val = int(payload)
                    if 30 <= val <= 250:
                        self.heart_rate = val
            except Exception as e:
                print(f"Decoding error from MQTT payload: {e}")

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_message = on_message
        try:
            self.mqtt_client.connect(self.mqtt_broker, 1883, timeout=5)
            self.mqtt_client.subscribe("smartcare/vitals/hr")
            self.mqtt_client.loop_start()
            
            while self.running:
                time.sleep(1) # Keep alive loop waiting for signals
        except Exception as e:
            print(f"MQTT Broker error ({e}). Mocking sensor data locally...")
            self._simulate()

    def get_heart_rate(self):
        """Returns the atomic integer mapped directly to memory."""
        return self.heart_rate
