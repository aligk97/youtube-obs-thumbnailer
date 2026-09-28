Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
venvPythonw = baseDir & "\.venv\Scripts\pythonw.exe"
watcher = baseDir & "\watch_obs.py"
config = baseDir & "\config.json"

If fso.FileExists(venvPythonw) Then
  command = """" & venvPythonw & """ """ & watcher & """ --config """ & config & """"
Else
  command = "pyw """ & watcher & """ --config """ & config & """"
End If

shell.Run command, 0, False
