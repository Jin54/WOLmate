"""
WOLmate Setup - 설치/삭제 전용
- wolmate.exe(서버)를 Program Files\\WOLmate에 설치
- 작업 스케줄러, 방화벽 규칙 등록/제거
"""

import subprocess
import sys
import os
import json
import ctypes
import uuid
import shutil

PORT = 9770
APP_NAME = "WOLmate Shutdown Server"
TASK_NAME = "WOLmate_ShutdownServer"
TASK_NAME_WATCHDOG = "WOLmate_ShutdownServer_Watchdog"
INSTALL_DIR = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "WOLmate")
INSTALL_EXE = os.path.join(INSTALL_DIR, "wolmate.exe")
CONFIG_FILE = os.path.join(INSTALL_DIR, "wolmate-config.json")


def get_bundled_wolmate():
    """번들된 wolmate.exe 경로"""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "wolmate.exe")
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "wolmate.exe")


def get_exe_path():
    if getattr(sys, 'frozen', False):
        return os.path.abspath(sys.executable)
    return os.path.abspath(sys.argv[0])


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin(args=""):
    exe = get_exe_path()
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)


def msgbox(text, title=APP_NAME, style=0):
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)


def hide_console():
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except:
        pass


def load_api_key():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("api_key", "")
        except:
            pass
    return ""


def save_api_key(key):
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
    data["api_key"] = key
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_api_key():
    return uuid.uuid4().hex[:16]


def get_all_adapters():
    result = subprocess.run(["ipconfig", "/all"], capture_output=True, text=True, encoding="cp949")
    adapters = []
    name = mac = ip = None
    for line in result.stdout.splitlines():
        line = line.rstrip()
        if line and not line.startswith(" "):
            if mac and ip:
                adapters.append((name, mac, ip))
            name = line.strip().rstrip(":")
            mac = ip = None
        elif "물리적 주소" in line or "Physical Address" in line:
            mac = line.split(":")[-1].strip().replace("-", ":")
        elif "IPv4" in line:
            addr = line.split(":")[-1].strip()
            if "(" in addr:
                addr = addr.split("(")[0]
            ip = addr
    if mac and ip:
        adapters.append((name, mac, ip))
    return adapters


def show_info_dialog(info_text):
    info_text = info_text.replace("\r\n", "\n").replace("\n", "\r\n")
    escaped = info_text.replace("'", "''").replace("`", "``")
    ps = f'''
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.Text = "{APP_NAME}"
$form.Width = 500
$form.Height = 450
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$tb = New-Object System.Windows.Forms.TextBox
$tb.Multiline = $true
$tb.ReadOnly = $true
$tb.ScrollBars = "Vertical"
$tb.Font = New-Object System.Drawing.Font("Consolas", 10)
$tb.Dock = "Fill"
$tb.Text = '{escaped}'

$panel = New-Object System.Windows.Forms.Panel
$panel.Height = 45
$panel.Dock = "Bottom"

$btnSave = New-Object System.Windows.Forms.Button
$btnSave.Text = "저장"
$btnSave.Width = 80
$btnSave.Height = 30
$btnSave.Location = New-Object System.Drawing.Point(([int]($form.ClientSize.Width / 2) - 90), 8)
$btnSave.Add_Click({{
    $d = New-Object System.Windows.Forms.SaveFileDialog
    $d.Title = "WOLmate 정보 저장"
    $d.Filter = "텍스트 파일 (*.txt)|*.txt|모든 파일 (*.*)|*.*"
    $d.FileName = "WOLmate-Info.txt"
    $d.InitialDirectory = [Environment]::GetFolderPath("Desktop")
    if ($d.ShowDialog() -eq "OK") {{
        [System.IO.File]::WriteAllText($d.FileName, $tb.Text, [System.Text.Encoding]::UTF8)
        [System.Windows.Forms.MessageBox]::Show("저장 완료!`n`n" + $d.FileName, "{APP_NAME}", "OK", "Information")
    }}
}})

$btnOk = New-Object System.Windows.Forms.Button
$btnOk.Text = "확인"
$btnOk.Width = 80
$btnOk.Height = 30
$btnOk.Location = New-Object System.Drawing.Point(([int]($form.ClientSize.Width / 2) + 10), 8)
$btnOk.DialogResult = "OK"
$form.AcceptButton = $btnOk

$panel.Controls.Add($btnSave)
$panel.Controls.Add($btnOk)
$form.Controls.Add($tb)
$form.Controls.Add($panel)
$form.ShowDialog()
'''
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True
    )


def install():
    if not is_admin():
        run_as_admin("--install")
        os._exit(0)

    hide_console()
    errors = []

    # 기존 서버 프로세스 종료
    subprocess.run(["taskkill", "/F", "/IM", "wolmate.exe"], capture_output=True)

    # Program Files\WOLmate 폴더 생성 및 wolmate.exe 복사
    bundled = get_bundled_wolmate()
    try:
        os.makedirs(INSTALL_DIR, exist_ok=True)
        shutil.copy2(bundled, INSTALL_EXE)
    except Exception as e:
        errors.append(f"파일 복사: {e}")

    # 작업 스케줄러 등록 (로그온 시 시작)
    subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], capture_output=True)
    result = subprocess.run(
        ["schtasks", "/Create",
         "/TN", TASK_NAME,
         "/TR", f'"{INSTALL_EXE}"',
         "/SC", "ONLOGON",
         "/RL", "HIGHEST",
         "/F"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        errors.append(f"작업 스케줄러: {result.stderr.strip()}")

    # 5분 간격 워치독 (포트 체크 후 서버가 꺼져있을 때만 실행)
    watchdog_cmd = (
        f'cmd /c "powershell -NoProfile -Command '
        f"\"try {{ (New-Object Net.Sockets.TcpClient('127.0.0.1',{PORT})).Close() }} "
        f"catch {{ Start-Process '{INSTALL_EXE}' }}\""
        f'"'
    )
    subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME_WATCHDOG, "/F"], capture_output=True)
    result = subprocess.run(
        ["schtasks", "/Create",
         "/TN", TASK_NAME_WATCHDOG,
         "/TR", watchdog_cmd,
         "/SC", "MINUTE",
         "/MO", "5",
         "/RL", "HIGHEST",
         "/F"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        errors.append(f"감시 스케줄러: {result.stderr.strip()}")

    # 방화벽 규칙
    subprocess.run(
        ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={APP_NAME}"],
        capture_output=True
    )
    result = subprocess.run(
        ["netsh", "advfirewall", "firewall", "add", "rule",
         f"name={APP_NAME}",
         "dir=in", "action=allow", "protocol=TCP",
         f"localport={PORT}",
         "profile=private"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        errors.append(f"방화벽: {result.stderr.strip()}")

    if errors:
        msgbox("설치 중 오류:\n" + "\n".join(errors), style=0x10)
    else:
        # API 키 생성
        api_key = load_api_key()
        if not api_key:
            api_key = generate_api_key()
            save_api_key(api_key)

        # 스케줄러를 통해 서버 시작 (Setup 프로세스와 완전 분리)
        subprocess.run(["schtasks", "/Run", "/TN", TASK_NAME], capture_output=True)

        adapters = get_all_adapters()
        info_lines = (
            f"설치 완료!\n\n"
            f"• 설치 경로: {INSTALL_DIR}\n"
            f"• 작업 스케줄러 등록됨\n"
            f"• 5분 간격 감시 스케줄러 등록됨\n"
            f"• 방화벽 규칙 추가됨\n"
            f"• 서버 시작됨\n"
        )
        info_lines += f"\n── API 키 ──\n{api_key}\n"
        if adapters:
            info_lines += "\n── 앱에 입력할 정보 ──\n"
            for name, mac, ip in adapters:
                info_lines += f"\n[{name}]\n  MAC: {mac}\n  IP: {ip}\n"
            info_lines += "\nWOL 포트: 9"
        show_info_dialog(info_lines)


def uninstall():
    if not is_admin():
        run_as_admin("--uninstall")
        os._exit(0)

    hide_console()
    errors = []

    # 서버 프로세스 종료
    subprocess.run(["taskkill", "/F", "/IM", "wolmate.exe"], capture_output=True)

    # 스케줄러 제거
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        errors.append(f"작업 스케줄러: {result.stderr.strip()}")

    subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME_WATCHDOG, "/F"], capture_output=True)

    # 방화벽 제거
    result = subprocess.run(
        ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={APP_NAME}"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        errors.append(f"방화벽: {result.stderr.strip()}")

    # 설치 폴더 삭제 (지연)
    if os.path.exists(INSTALL_DIR):
        try:
            subprocess.Popen(
                f'ping -n 4 127.0.0.1 >nul & rmdir /s /q "{INSTALL_DIR}"',
                shell=True
            )
        except:
            errors.append(f"폴더 삭제 실패: {INSTALL_DIR}")

    if errors:
        msgbox("제거 중 오류:\n" + "\n".join(errors), style=0x10)
    else:
        msgbox(
            f"제거 완료!\n\n"
            f"• 작업 스케줄러 제거됨\n"
            f"• 감시 스케줄러 제거됨\n"
            f"• 방화벽 규칙 제거됨\n"
            f"• 서버 종료됨\n"
            f"• 설치 폴더 삭제됨\n"
            f"  ({INSTALL_DIR})",
            style=0x40
        )


def main():
    hide_console()

    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "--install":
            install()
            return
        elif cmd == "--uninstall":
            uninstall()
            return

    # 인수 없이 실행 → 설치/제거 선택
    result = msgbox(
        "WOLmate Shutdown Server\n\n"
        "설치 → [예]\n"
        "삭제 → [아니오]\n"
        "닫기 → [취소]",
        style=0x23
    )
    if result == 6:
        install()
    elif result == 7:
        uninstall()


if __name__ == "__main__":
    main()
