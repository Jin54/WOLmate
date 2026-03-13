package com.wol.app

import android.content.SharedPreferences
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.wol.app.databinding.ActivityMainBinding
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var prefs: SharedPreferences
    private val handler = Handler(Looper.getMainLooper())
    private var pingRunnable: Runnable? = null

    companion object {
        const val SHUTDOWN_PORT = 9770
        const val DEFAULT_PING_INTERVAL = 5_000L // 5초
    }

    private fun getPingInterval(): Long {
        val sec = binding.etPingInterval.text.toString().trim().toLongOrNull()
        return if (sec != null && sec > 0) sec * 1000 else DEFAULT_PING_INTERVAL
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        prefs = getSharedPreferences("wol_prefs", MODE_PRIVATE)
        loadSettings()

        when (intent?.action) {
            "com.wol.app.SEND_WOL" -> sendWol()
            "com.wol.app.SHUTDOWN" -> sendShutdown()
        }

        binding.btnSave.setOnClickListener {
            saveSettings()
            restartPingLoop()
            Toast.makeText(this, "설정이 저장되었습니다", Toast.LENGTH_SHORT).show()
        }

        binding.btnSendWol.setOnClickListener {
            sendWol()
        }

        binding.btnShutdown.setOnClickListener {
            sendShutdown()
        }

        binding.btnCancelShutdown.setOnClickListener {
            sendCancelShutdown()
        }

        startPingLoop()
    }

    override fun onDestroy() {
        super.onDestroy()
        stopPingLoop()
    }

    private fun startPingLoop() {
        pingRunnable = object : Runnable {
            override fun run() {
                checkPcStatus()
                handler.postDelayed(this, getPingInterval())
            }
        }
        pingRunnable?.run()
    }

    private fun stopPingLoop() {
        pingRunnable?.let { handler.removeCallbacks(it) }
    }

    private fun restartPingLoop() {
        stopPingLoop()
        startPingLoop()
    }

    private fun checkPcStatus() {
        val pcIp = binding.etPcIp.text.toString().trim()
        if (pcIp.isEmpty()) {
            binding.tvPcStatus.text = "--"
            binding.tvPcStatus.setTextColor(0xFF888888.toInt())
            binding.progressStatus.visibility = View.GONE
            return
        }

        // 로딩 스피너를 점 위치에 표시, 기존 ON/OFF 텍스트 유지
        binding.progressStatus.visibility = View.VISIBLE
        // 점 문자를 제거하고 텍스트만 유지 (첫 실행 시에는 "확인 중...")
        val currentText = binding.tvPcStatus.text.toString()
        if (currentText == "--" || currentText.isEmpty()) {
            binding.tvPcStatus.text = "확인 중..."
            binding.tvPcStatus.setTextColor(0xFF888888.toInt())
        } else {
            // 기존 PC ON/PC OFF 텍스트에서 점만 제거
            binding.tvPcStatus.text = currentText.replace("\u2B24  ", "")
        }

        thread {
            val alive = try {
                val url = URL("http://$pcIp:$SHUTDOWN_PORT/ping")
                val conn = url.openConnection() as HttpURLConnection
                conn.connectTimeout = 3000
                conn.readTimeout = 3000
                conn.requestMethod = "GET"
                val code = conn.responseCode
                conn.disconnect()
                code == 200
            } catch (e: Exception) {
                false
            }

            runOnUiThread {
                binding.progressStatus.visibility = View.GONE
                val card = binding.cardPcStatus.getChildAt(0)
                if (alive) {
                    binding.tvPcStatus.text = "\u2B24  PC ON"
                    binding.tvPcStatus.setTextColor(0xFF2E7D32.toInt())
                    card.setBackgroundColor(0xFFE8F5E9.toInt())
                    binding.btnSendWol.isEnabled = false
                    binding.btnShutdown.isEnabled = true
                    binding.btnCancelShutdown.isEnabled = true
                } else {
                    binding.tvPcStatus.text = "\u2B24  PC OFF"
                    binding.tvPcStatus.setTextColor(0xFFC62828.toInt())
                    card.setBackgroundColor(0xFFFFEBEE.toInt())
                    binding.btnSendWol.isEnabled = true
                    binding.btnShutdown.isEnabled = false
                    binding.btnCancelShutdown.isEnabled = false
                }
            }
        }
    }

    private fun toBroadcast(ip: String): String {
        val parts = ip.split(".")
        if (parts.size != 4) return ip
        return "${parts[0]}.${parts[1]}.${parts[2]}.255"
    }

    private fun sendWol() {
        val mac = binding.etMacAddress.text.toString().trim()
        val pcIp = binding.etPcIp.text.toString().trim()
        val port = binding.etPort.text.toString().trim().toIntOrNull() ?: 9

        if (mac.isEmpty() || pcIp.isEmpty()) {
            binding.tvStatus.text = "MAC 주소와 PC IP를 입력하세요"
            return
        }

        val broadcastIp = toBroadcast(pcIp)
        binding.tvStatus.text = "전송 중..."
        binding.btnSendWol.isEnabled = false

        thread {
            val result = WolSender.send(mac, broadcastIp, port)
            runOnUiThread {
                binding.btnSendWol.isEnabled = true
                if (result.isSuccess) {
                    binding.tvStatus.text = "WOL 패킷 전송 완료! ($broadcastIp)"
                    Toast.makeText(this, "PC 켜기 신호 전송!", Toast.LENGTH_SHORT).show()
                    // 즉시 상태 갱신
                    checkPcStatus()
                } else {
                    binding.tvStatus.text = "전송 실패: ${result.exceptionOrNull()?.message}"
                    Toast.makeText(this, "전송 실패", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun sendShutdown() {
        val pcIp = binding.etPcIp.text.toString().trim()
        val delay = binding.etShutdownDelay.text.toString().trim().toIntOrNull()
        val apiKey = binding.etApiKey.text.toString().trim()

        if (pcIp.isEmpty()) {
            binding.tvStatus.text = "PC IP를 입력하세요"
            return
        }

        val silent = binding.switchSilentShutdown.isChecked

        val params = mutableListOf<String>()
        if (silent) {
            params.add("delay=0")
            params.add("silent=1")
        } else if (delay != null) {
            params.add("delay=$delay")
        }
        if (apiKey.isNotEmpty()) params.add("key=$apiKey")
        val query = if (params.isNotEmpty()) "?" + params.joinToString("&") else ""
        val url = "http://$pcIp:$SHUTDOWN_PORT/shutdown$query"

        binding.tvStatus.text = "종료 요청 중..."
        binding.btnShutdown.isEnabled = false

        thread {
            val result = sendHttpPost(url)
            runOnUiThread {
                binding.btnShutdown.isEnabled = true
                if (result.isSuccess) {
                    val msg = if (delay != null) "${delay}초 후 PC 종료!" else "PC 종료 요청 완료!"
                    binding.tvStatus.text = msg
                    Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
                    // 즉시 상태 갱신
                    checkPcStatus()
                } else {
                    binding.tvStatus.text = "종료 실패: ${result.exceptionOrNull()?.message}"
                    Toast.makeText(this, "종료 실패 - PC 서버 확인", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun sendCancelShutdown() {
        val pcIp = binding.etPcIp.text.toString().trim()
        val apiKey = binding.etApiKey.text.toString().trim()

        if (pcIp.isEmpty()) {
            binding.tvStatus.text = "PC IP를 입력하세요"
            return
        }

        val query = if (apiKey.isNotEmpty()) "?key=$apiKey" else ""
        val url = "http://$pcIp:$SHUTDOWN_PORT/cancel$query"

        binding.tvStatus.text = "종료 취소 요청 중..."
        binding.btnCancelShutdown.isEnabled = false

        thread {
            val result = sendHttpPost(url)
            runOnUiThread {
                binding.btnCancelShutdown.isEnabled = true
                if (result.isSuccess) {
                    binding.tvStatus.text = "종료 취소 완료!"
                    Toast.makeText(this, "종료 취소 완료!", Toast.LENGTH_SHORT).show()
                    checkPcStatus()
                } else {
                    binding.tvStatus.text = "취소 실패: ${result.exceptionOrNull()?.message}"
                    Toast.makeText(this, "취소 실패", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun sendHttpPost(urlStr: String): Result<String> {
        return try {
            val url = URL(urlStr)
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.connectTimeout = 3000
            conn.readTimeout = 3000
            conn.doOutput = true
            conn.outputStream.close()

            val response = conn.inputStream.bufferedReader().readText()
            conn.disconnect()
            Result.success(response)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun saveSettings() {
        prefs.edit().apply {
            putString("mac", binding.etMacAddress.text.toString())
            putString("pc_ip", binding.etPcIp.text.toString())
            putString("port", binding.etPort.text.toString())
            putString("api_key", binding.etApiKey.text.toString())
            putString("shutdown_delay", binding.etShutdownDelay.text.toString())
            putString("ping_interval", binding.etPingInterval.text.toString())
            putBoolean("silent_shutdown", binding.switchSilentShutdown.isChecked)
            apply()
        }
    }

    private fun loadSettings() {
        binding.etMacAddress.setText(prefs.getString("mac", ""))
        binding.etPcIp.setText(prefs.getString("pc_ip", "192.168.0.10"))
        binding.etPort.setText(prefs.getString("port", "9"))
        binding.etApiKey.setText(prefs.getString("api_key", ""))
        binding.etShutdownDelay.setText(prefs.getString("shutdown_delay", ""))
        binding.etPingInterval.setText(prefs.getString("ping_interval", "5"))
        binding.switchSilentShutdown.isChecked = prefs.getBoolean("silent_shutdown", false)
    }
}
