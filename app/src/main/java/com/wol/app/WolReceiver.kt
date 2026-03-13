package com.wol.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.widget.Toast
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

/**
 * 빅스비 루틴에서 인텐트로 직접 WOL/종료 전송 가능
 */
class WolReceiver : BroadcastReceiver() {

    companion object {
        const val SHUTDOWN_PORT = 9770
    }

    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            "com.wol.app.SEND_WOL" -> handleWol(context, intent)
            "com.wol.app.SHUTDOWN" -> handleShutdown(context, intent)
        }
    }

    private fun handleWol(context: Context, intent: Intent) {
        val prefs = context.getSharedPreferences("wol_prefs", Context.MODE_PRIVATE)

        val mac = intent.getStringExtra("mac")
            ?: prefs.getString("mac", "") ?: ""
        val pcIp = prefs.getString("pc_ip", "192.168.0.10") ?: "192.168.0.10"
        val ip = intent.getStringExtra("ip") ?: toBroadcast(pcIp)
        val port = intent.getIntExtra("port", -1).let {
            if (it == -1) prefs.getString("port", "9")?.toIntOrNull() ?: 9 else it
        }

        if (mac.isEmpty()) {
            Toast.makeText(context, "MAC 주소가 설정되지 않았습니다", Toast.LENGTH_SHORT).show()
            return
        }

        thread {
            val result = WolSender.send(mac, ip, port)
            android.os.Handler(android.os.Looper.getMainLooper()).post {
                if (result.isSuccess) {
                    Toast.makeText(context, "PC 켜기 신호 전송!", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(context, "WOL 전송 실패", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun toBroadcast(ip: String): String {
        val parts = ip.split(".")
        if (parts.size != 4) return ip
        return "${parts[0]}.${parts[1]}.${parts[2]}.255"
    }

    private fun handleShutdown(context: Context, intent: Intent) {
        val prefs = context.getSharedPreferences("wol_prefs", Context.MODE_PRIVATE)
        val pcIp = intent.getStringExtra("pc_ip")
            ?: prefs.getString("pc_ip", "") ?: ""
        val apiKey = prefs.getString("api_key", "") ?: ""

        if (pcIp.isEmpty()) {
            Toast.makeText(context, "PC IP가 설정되지 않았습니다", Toast.LENGTH_SHORT).show()
            return
        }

        val query = if (apiKey.isNotEmpty()) "?key=$apiKey" else ""
        thread {
            val result = try {
                val url = URL("http://$pcIp:$SHUTDOWN_PORT/shutdown$query")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.connectTimeout = 3000
                conn.readTimeout = 3000
                conn.doOutput = true
                conn.outputStream.close()
                conn.inputStream.bufferedReader().readText()
                conn.disconnect()
                true
            } catch (e: Exception) {
                false
            }
            android.os.Handler(android.os.Looper.getMainLooper()).post {
                if (result) {
                    Toast.makeText(context, "PC 끄기 신호 전송!", Toast.LENGTH_SHORT).show()
                } else {
                    Toast.makeText(context, "PC 종료 실패", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}
