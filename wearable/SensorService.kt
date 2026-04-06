package com.smartcare.wearable

import android.app.Service
import android.content.Intent
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.IBinder
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import kotlin.math.sqrt

class SensorService : Service(), SensorEventListener {

    private lateinit var sensorManager: SensorManager
    private var accelSensor: Sensor? = null
    private var heartRateSensor: Sensor? = null

    private val accelWindow = mutableListOf<JSONObject>()
    private var currentHeartRate: Int = 0

    // ENERGY SAVING FILTER: 
    // Only send window data to cloud if a sudden motion spike > 15 m/s^2 is detected.
    private val MOTION_THRESHOLD = 15.0 

    override fun onCreate() {
        super.onCreate()
        sensorManager = getSystemService(SENSOR_SERVICE) as SensorManager
        accelSensor = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        heartRateSensor = sensorManager.getDefaultSensor(Sensor.TYPE_HEART_RATE)

        // Register listeners: normal delay for battery saving (e.g., 50Hz)
        sensorManager.registerListener(this, accelSensor, SensorManager.SENSOR_DELAY_GAME)
        sensorManager.registerListener(this, heartRateSensor, SensorManager.SENSOR_DELAY_NORMAL)
        
        Log.d("SmartCare", "Wearable Sensors Initiated")
    }

    override fun onSensorChanged(event: SensorEvent?) {
        if (event == null) return

        if (event.sensor.type == Sensor.TYPE_HEART_RATE) {
            currentHeartRate = event.values[0].toInt()
        } else if (event.sensor.type == Sensor.TYPE_ACCELEROMETER) {
            val x = event.values[0]
            val y = event.values[1]
            val z = event.values[2]

            val dataPoint = JSONObject()
            dataPoint.put("x", x)
            dataPoint.put("y", y)
            dataPoint.put("z", z)
            dataPoint.put("timestamp", System.currentTimeMillis())

            accelWindow.add(dataPoint)

            // Once we have a 1 second window of 50 samples
            if (accelWindow.size == 50) {
                // Determine if a potentially sharp movement occurred
                val magnitude = sqrt((x*x + y*y + z*z).toDouble())
                if (magnitude > MOTION_THRESHOLD) {
                    sendDataToCloud(ArrayList(accelWindow))
                }
                
                // Keep memory usage low
                accelWindow.clear() 
            }
        }
    }

    private fun sendDataToCloud(window: List<JSONObject>) {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                // Production: Replace with your actual server IP running the FastAPI backend
                val url = URL("http://YOUR_FASTAPI_IP:8000/api/monitor")
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.setRequestProperty("Content-Type", "application/json")
                connection.doOutput = true

                val payload = JSONObject()
                payload.put("user_id", "senior_001")
                
                val vitals = JSONObject()
                vitals.put("heart_rate", currentHeartRate)
                vitals.put("timestamp", System.currentTimeMillis())
                payload.put("vitals", vitals)

                payload.put("accel_data", JSONArray(window))

                val writer = OutputStreamWriter(connection.outputStream)
                writer.write(payload.toString())
                writer.flush()

                val responseCode = connection.responseCode
                Log.d("SmartCare", "Cloud Post Code: $responseCode")
                connection.disconnect()
            } catch (e: Exception) {
                Log.e("SmartCare", "Network Error: ${e.message}")
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
    override fun onBind(intent: Intent?): IBinder? = null
    override fun onDestroy() {
        super.onDestroy()
        sensorManager.unregisterListener(this)
    }
}
