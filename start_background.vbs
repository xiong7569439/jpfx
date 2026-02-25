Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pythonw d:\coding\jpfx\main.py --schedule", 0, False
Set WshShell = Nothing
