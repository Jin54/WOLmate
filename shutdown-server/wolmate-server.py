"""
WOLmate Shutdown Server (서버 전용)
- wolmate.exe로 빌드되어 Program Files\WOLmate에 설치됨
- 기본 포트: 9770
"""

import http.server
import subprocess
import sys
import os
import json
import ctypes
import logging
import logging.handlers
import glob
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs

PORT = 9770
INSTALL_DIR = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "WOLmate")
CONFIG_FILE = os.path.join(INSTALL_DIR, "wolmate-config.json")
LOG_DIR = os.path.join(INSTALL_DIR, "logs")

logger = logging.getLogger("WOLmate")


def init_logging():
    """로그 초기화 (뮤텍스 획득 후 호출)"""
    os.makedirs(LOG_DIR, exist_ok=True)

    # 7일 지난 로그 삭제 (파일명 날짜 기준)
    import re
    today = datetime.now().date()
    for f in glob.glob(os.path.join(LOG_DIR, "wolmate-*.log")):
        m = re.search(r"wolmate-(\d{4}-\d{2}-\d{2})\.log$", f)
        if m:
            try:
                log_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
                if (today - log_date).days > 7:
                    os.remove(f)
            except (ValueError, OSError):
                pass

    logger.setLevel(logging.INFO)
    _handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(LOG_DIR, "wolmate.log"),
        when="midnight", interval=1, backupCount=7, encoding="utf-8"
    )
    _handler.suffix = "%Y-%m-%d.log"
    _handler.namer = lambda name: os.path.join(LOG_DIR, "wolmate-" + name.split(".")[-2] + ".log")
    _handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(_handler)


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_api_key():
    return load_config().get("api_key", "")


def load_port():
    return load_config().get("port", PORT)


class ShutdownHandler(http.server.BaseHTTPRequestHandler):
    api_key = ""
    _force_timer = None

    def do_GET(self):
        if self.path == "/ping":
            self._respond(200, {"status": "ok", "message": "PC is alive"})
        else:
            self._respond(404, {"error": "not found"})

    def _check_api_key(self, params):
        if not self.api_key:
            return True
        key = params.get("key", [""])[0]
        return key == self.api_key

    def do_POST(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if not self._check_api_key(params):
            self._respond(403, {"error": "invalid API key"})
            return

        if parsed.path == "/shutdown":
            silent = params.get("silent", ["0"])[0] == "1"
            delay = params.get("delay", ["3"])[0]
            try:
                delay = str(max(0, int(delay)))
            except ValueError:
                delay = "3"

            if silent:
                self._respond(200, {"status": "ok", "message": "shutting down immediately (silent)..."})
                subprocess.Popen(["shutdown", "/s", "/f", "/t", "0"], shell=True)
            else:
                self._respond(200, {"status": "ok", "message": f"shutting down in {delay}s..."})
                subprocess.Popen(["shutdown", "/s", "/t", delay], shell=True)
                import threading
                force_sec = int(delay) + 60
                def force_shutdown():
                    subprocess.Popen(["shutdown", "/a"], shell=True)
                    import time; time.sleep(1)
                    subprocess.Popen(["shutdown", "/s", "/f", "/t", "0"], shell=True)
                if ShutdownHandler._force_timer:
                    ShutdownHandler._force_timer.cancel()
                ShutdownHandler._force_timer = threading.Timer(force_sec, force_shutdown)
                ShutdownHandler._force_timer.start()
        elif parsed.path == "/cancel":
            if ShutdownHandler._force_timer:
                ShutdownHandler._force_timer.cancel()
                ShutdownHandler._force_timer = None
            subprocess.Popen(["shutdown", "/a"], shell=True)
            self._respond(200, {"status": "ok", "message": "shutdown cancelled"})
        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))

    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {args[0]}")


def hide_console():
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except:
        pass


def acquire_mutex():
    mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "Global\\WOLmate_ShutdownServer_Mutex")
    last_error = ctypes.windll.kernel32.GetLastError()
    if last_error == 183:  # ERROR_ALREADY_EXISTS
        os._exit(0)
    return mutex


def change_port(new_port):
    """포트 변경: config 저장 → 방화벽 갱신 → 서버 재시작"""
    config = load_config()
    old_port = config.get("port", PORT)
    config["port"] = new_port
    save_config(config)

    # 방화벽 규칙 갱신
    subprocess.run(["netsh", "advfirewall", "firewall", "delete", "rule", "name=WOLmate Shutdown Server"], capture_output=True)
    subprocess.run(["netsh", "advfirewall", "firewall", "add", "rule",
                     "name=WOLmate Shutdown Server", "dir=in", "action=allow",
                     "protocol=TCP", f"localport={new_port}", "profile=private"], capture_output=True)

    # 기존 서버 종료 (자기 PID 제외)
    my_pid = os.getpid()
    subprocess.run(f'wmic process where "name=\'wolmate.exe\' and processid!=\'{my_pid}\'" call terminate',
                   shell=True, capture_output=True)

    print(f"포트 변경 완료: {old_port} -> {new_port}")
    print(f"방화벽 규칙이 포트 {new_port}으로 갱신되었습니다.")

    # VBS로 재시작 (CMD 창 숨김)
    vbs = os.path.join(INSTALL_DIR, "wolmate-start.vbs")
    if os.path.exists(vbs):
        subprocess.Popen(["wscript.exe", vbs])
        print("서버가 재시작되었습니다.")
    else:
        subprocess.Popen([os.path.join(INSTALL_DIR, "wolmate.exe")])
        print("서버가 재시작되었습니다.")


def main():
    # --port 명령 처리
    if len(sys.argv) >= 3 and sys.argv[1] == "--port":
        try:
            new_port = int(sys.argv[2])
            if 1 <= new_port <= 65535:
                change_port(new_port)
            else:
                print("포트 범위: 1-65535")
        except ValueError:
            print("올바른 포트 번호를 입력하세요.")
        return

    hide_console()
    _mutex = acquire_mutex()
    init_logging()

    port = load_port()
    ShutdownHandler.api_key = load_api_key()

    try:
        server = http.server.HTTPServer(("0.0.0.0", port), ShutdownHandler)
    except OSError as e:
        logger.info(f"포트 {port} 사용 중 - 종료")
        # 콘솔이 있으면 에러 메시지 표시
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
                print(f"\n[오류] 포트 {port}을(를) 열 수 없습니다. (이미 사용 중)")
                print(f"\n포트를 변경하려면 관리자 CMD에서:")
                print(f'  "C:\\Program Files\\WOLmate\\wolmate.exe" --port 9771')
                print(f"\n포트 변경 후 WOLmate-Setup.exe로 재설치하면 방화벽/스케줄러가 갱신됩니다.")
                print(f"\n아무 키나 누르면 종료됩니다...")
                import msvcrt
                msvcrt.getch()
        except:
            pass
        os._exit(0)

    logger.info(f"서버 시작 - 포트 {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("서버 종료")
        server.server_close()


if __name__ == "__main__":
    main()
