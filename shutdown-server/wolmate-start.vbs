Set WshShell = CreateObject("Wscript.Shell")
WshShell.Run """" & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\wolmate.exe""", 0, False
