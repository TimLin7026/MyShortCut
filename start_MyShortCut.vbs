' MyShortCut - ?????????
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
exePath = currentDir & "\MyShortCut.exe"
mainPyPath = currentDir & "\main.py"

If fso.FileExists(exePath) Then
    ' ???????? exe (0 ????????? CMD)
    WshShell.Run """" & exePath & """", 0, False
Else
    ' ?? pythonw.exe (???? Python ???)
    cmd = "pythonw.exe """ & mainPyPath & """"
    WshShell.CurrentDirectory = currentDir
    WshShell.Run cmd, 0, False
End If