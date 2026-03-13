!include "MUI2.nsh"

; --- 기본 설정 ---
Name "WOLmate Shutdown Server"
OutFile "C:\Users\jwy\source\WOLApp\output\WOLmate-Setup.exe"
InstallDir "$PROGRAMFILES64\WOLmate"
RequestExecutionLevel admin
Unicode true

; --- UI 설정 ---
!define MUI_ABORTWARNING
!define MUI_ICON "C:\Users\jwy\source\WOLApp\shutdown-server\wolmate-setup.ico"
!define MUI_UNICON "C:\Users\jwy\source\WOLApp\shutdown-server\wolmate-setup.ico"

; --- 페이지 ---
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Korean"

; --- 설치 섹션 ---
Section "Install"
    ; 기존 서버 프로세스 종료
    nsExec::ExecToLog 'taskkill /F /IM wolmate.exe'

    ; 파일 복사 (onedir: wolmate.exe + _internal/)
    SetOutPath "$INSTDIR"
    File "C:\Users\jwy\source\WOLApp\shutdown-server\dist\wolmate\wolmate.exe"
    File "C:\Users\jwy\source\WOLApp\shutdown-server\show-info.ps1"
    File "C:\Users\jwy\source\WOLApp\shutdown-server\gen-apikey.ps1"
    File "C:\Users\jwy\source\WOLApp\shutdown-server\wolmate-start.vbs"
    SetOutPath "$INSTDIR\_internal"
    File /r "C:\Users\jwy\source\WOLApp\shutdown-server\dist\wolmate\_internal\*.*"
    SetOutPath "$INSTDIR"

    ; API 키 생성 (기존 config 없을 때만)
    IfFileExists "$INSTDIR\wolmate-config.json" SkipApiKey
        nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\gen-apikey.ps1" -InstallDir "$INSTDIR"'
    SkipApiKey:

    ; 작업 스케줄러 등록 (로그온 시 시작)
    nsExec::ExecToLog 'schtasks /Delete /TN "WOLmate_ShutdownServer" /F'
    nsExec::ExecToLog 'schtasks /Create /TN "WOLmate_ShutdownServer" /TR "wscript.exe \"$INSTDIR\wolmate-start.vbs\"" /SC ONLOGON /RL HIGHEST /F'

    ; 5분 간격 워치독
    nsExec::ExecToLog 'schtasks /Delete /TN "WOLmate_ShutdownServer_Watchdog" /F'
    nsExec::ExecToLog 'schtasks /Create /TN "WOLmate_ShutdownServer_Watchdog" /TR "cmd /c \"powershell -NoProfile -Command \\\"try { (New-Object Net.Sockets.TcpClient(''127.0.0.1'',9770)).Close() } catch { Start-Process ''wscript.exe'' -ArgumentList ''\\\"$INSTDIR\wolmate-start.vbs\\\"'' }\\\"\"" /SC MINUTE /MO 5 /RL HIGHEST /F'

    ; 방화벽 규칙
    nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="WOLmate Shutdown Server"'
    nsExec::ExecToLog 'netsh advfirewall firewall add rule name="WOLmate Shutdown Server" dir=in action=allow protocol=TCP localport=9770 profile=private'

    ; 서버 시작 (VBS로 CMD 창 없이)
    Exec 'wscript.exe "$INSTDIR\wolmate-start.vbs"'

    ; 언인스톨러 생성
    WriteUninstaller "$INSTDIR\uninstall.exe"

    ; 프로그램 추가/제거에 등록
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WOLmate" "DisplayName" "WOLmate Shutdown Server"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WOLmate" "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WOLmate" "InstallLocation" "$INSTDIR"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WOLmate" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WOLmate" "NoRepair" 1

    ; 바탕화면에 정보 텍스트 저장
    nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\show-info.ps1" -InstallDir "$INSTDIR"'

    ; NSIS MessageBox로 알림 (한글 깨짐 방지)
    MessageBox MB_ICONINFORMATION|MB_OK "WOLmate 설치 완료!$\n$\nPC 정보가 바탕화면에 저장되었습니다.$\n(WOLmate-Info.txt)"

    ; ps1 파일 정리
    Delete "$INSTDIR\gen-apikey.ps1"
    Delete "$INSTDIR\show-info.ps1"
SectionEnd

; --- 제거 섹션 ---
Section "Uninstall"
    ; 서버 종료
    nsExec::ExecToLog 'taskkill /F /IM wolmate.exe'

    ; 스케줄러 제거
    nsExec::ExecToLog 'schtasks /Delete /TN "WOLmate_ShutdownServer" /F'
    nsExec::ExecToLog 'schtasks /Delete /TN "WOLmate_ShutdownServer_Watchdog" /F'

    ; 방화벽 제거
    nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="WOLmate Shutdown Server"'

    ; 레지스트리 제거
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\WOLmate"

    ; 파일 삭제
    Delete "$INSTDIR\wolmate.exe"
    Delete "$INSTDIR\wolmate-config.json"
    Delete "$INSTDIR\wolmate.log"
    RMDir /r "$INSTDIR\logs"
    Delete "$INSTDIR\uninstall.exe"
    Delete "$INSTDIR\gen-apikey.ps1"
    Delete "$INSTDIR\show-info.ps1"
    Delete "$INSTDIR\wolmate-start.vbs"
    RMDir /r "$INSTDIR\_internal"
    RMDir "$INSTDIR"
SectionEnd
