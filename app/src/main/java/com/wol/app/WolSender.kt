package com.wol.app

import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

object WolSender {

    /**
     * WOL 매직 패킷 전송
     * @param macAddress MAC 주소 (AA:BB:CC:DD:EE:FF 또는 AA-BB-CC-DD-EE-FF)
     * @param ipAddress 브로드캐스트 IP (예: 192.168.0.255)
     * @param port 포트 (기본 9)
     */
    fun send(macAddress: String, ipAddress: String, port: Int = 9): Result<Unit> {
        return try {
            val macBytes = parseMac(macAddress)
            val magicPacket = buildMagicPacket(macBytes)

            val address = InetAddress.getByName(ipAddress)
            val packet = DatagramPacket(magicPacket, magicPacket.size, address, port)

            DatagramSocket().use { socket ->
                socket.broadcast = true
                socket.send(packet)
            }

            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun parseMac(mac: String): ByteArray {
        val hex = mac.replace("[:\\-]".toRegex(), "")
        require(hex.length == 12) { "MAC 주소 형식이 잘못되었습니다" }
        return ByteArray(6) { i ->
            hex.substring(i * 2, i * 2 + 2).toInt(16).toByte()
        }
    }

    private fun buildMagicPacket(macBytes: ByteArray): ByteArray {
        // 매직 패킷: 0xFF 6개 + MAC 주소 16번 반복 = 102 바이트
        val packet = ByteArray(6 + 16 * 6)

        // 0xFF 6개
        for (i in 0..5) {
            packet[i] = 0xFF.toByte()
        }

        // MAC 주소 16번 반복
        for (i in 0..15) {
            System.arraycopy(macBytes, 0, packet, 6 + i * 6, 6)
        }

        return packet
    }
}
