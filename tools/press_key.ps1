#requires -Version 5
<#
.SYNOPSIS
  先聚焦「ELDEN RING™」窗口，再在同一个进程里发一次键盘按键。

.DESCRIPTION
  分开跑 focus_game.ps1 + sit_grace.ps1 时，新起的 PowerShell 控制台可能在按键前
  抢走前台，游戏收不到键。这里把 focus 和 keybd_event 放一起。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\press_key.ps1 -Key E
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\press_key.ps1 -Key W -HoldMs 600
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\press_key.ps1 -Key DOWN
#>
param(
    [Parameter(Mandatory = $true)][string]$Key,
    [int]$HoldMs = 100
)

Add-Type @'
using System;
using System.Runtime.InteropServices;
public class ErKey {
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr extra);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint uCode, uint uMapType);
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
  public static void Send(byte vk, int holdMs, bool extended) {
    uint scan = MapVirtualKey(vk, 0);
    uint down = extended ? 0x0001u : 0u;
    uint up = extended ? 0x0003u : 0x0002u;
    keybd_event(vk, (byte)scan, down, UIntPtr.Zero);
    System.Threading.Thread.Sleep(holdMs);
    keybd_event(vk, (byte)scan, up, UIntPtr.Zero);
  }
}
'@

$map = @{
    'E' = 0x45; 'Q' = 0x51; 'W' = 0x57; 'A' = 0x41; 'S' = 0x53; 'D' = 0x44;
    'F' = 0x46; 'ENTER' = 0x0D; 'ESC' = 0x1B;
    'UP' = 0x26; 'DOWN' = 0x28; 'LEFT' = 0x25; 'RIGHT' = 0x27;
}
$name = $Key.ToUpper()
if (-not $map.ContainsKey($name)) { throw "unsupported key: $Key" }
$extended = $name -in @('UP', 'DOWN', 'LEFT', 'RIGHT')

$h = [ErKey]::Find()
if ($h -eq [IntPtr]::Zero) { throw "ELDEN RING window not found" }
[ErKey]::Focus($h) | Out-Null
Start-Sleep -Milliseconds 250
[ErKey]::Send([byte]$map[$name], [Math]::Max(60, $HoldMs), $extended)
Start-Sleep -Milliseconds 120
Write-Host "sent $name (hold ${HoldMs}ms) to ELDEN RING window"
