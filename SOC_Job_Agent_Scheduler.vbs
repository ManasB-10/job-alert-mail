' Launches the SOC Analyst job digest scheduler hidden at Windows login.
' No admin rights needed -- copy this file into your per-user Startup folder
' (Win+R -> shell:startup) and Windows will run it automatically at every logon.
' Edit the two paths below if your Python install or project location differ.
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "E:\Manas\Claude Code\Ai agent"
WshShell.Run """C:\Users\Manas\AppData\Local\Python\bin\pythonw.exe"" ""E:\Manas\Claude Code\Ai agent\scheduler.py""", 0, False
