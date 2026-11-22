#requires -Version 5
<#
.SYNOPSIS
  把「ELDEN RING™」游戏窗口切到前台（注入键盘/截图前先跑一次）。

.DESCRIPTION
  eldenring.exe 还有一个 ME2 控制台窗口（ConsoleWindowClass）。直接用
  MainWindowHandle 会点到控制台；这里和 auto_start.ps1 一样按标题找游戏窗口。
#>
param()

Add-Type @'
using System;
using System.Runtime.InteropServices;
public class FocusGameWin {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindowW(string cls, string title);
  public static IntPtr Find() {
    IntPtr h = FindWindowW(null, "ELDEN RING\u2122");
    if (h == IntPtr.Zero) h = FindWindowW(null, "ELDEN RING");
    return h;
  }
  public static bool Focus(IntPtr hwnd) {
    if (hwnd == IntPtr.Zero) return false;
    uint fgPid = 0;
    uint fgThread = GetWindowThreadProcessId(GetForegroundWindow(), out fgPid);
    uint myThread = GetCurrentThreadId();
    AttachThreadInput(myThread, fgThread, true);
    ShowWindow(hwnd, 9);
    BringWindowToTop(hwnd);
    bool ok = SetForegroundWindow(hwnd);
    AttachThreadInput(myThread, fgThread, false);
    return ok;
  }
}
'@

$h = [FocusGameWin]::Find()
if ($h -eq [IntPtr]::Zero) { throw "ELDEN RING window not found" }
[FocusGameWin]::Focus($h) | Out-Null
Start-Sleep -Milliseconds 400
Write-Host "focused ELDEN RING window ($h)"
