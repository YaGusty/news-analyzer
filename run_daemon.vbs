Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strCurrentDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strCurrentDir

pythonwPath = "C:\Users\USER\AppData\Local\Programs\Python\Python313\pythonw.exe"
If Not FSO.FileExists(pythonwPath) Then
    pythonwPath = "pythonw.exe"
End If

cmd = """" & pythonwPath & """ """ & strCurrentDir & "\scripts\main.py"" scheduler --daemon"
WshShell.Run cmd, 0, False
