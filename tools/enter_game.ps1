#requires -Version 5
<#
.SYNOPSIS
  启动/继续游戏，自动点掉标题、离线提示、主菜单，直到 DLL 日志出现 `event: entered game`。

.DESCRIPTION
  比 auto_start.ps1 更稳：不依赖鼠标坐标，而是聚焦游戏窗口后反复发 E
  （标题「按任一按钮」→ 联机/离线提示「确定」→ 主菜单「继续游戏」都用 E 确认），
  每 2.5 秒一次；日志里出现 entered game 就停。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\enter_game.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\enter_game.ps1 -NoLaunch
#>
param(
    [switch]$NoLaunch,
    [switch]$Click,
    [int]$TimeoutSeconds = 180
)

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class EnterGameKey {
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr extra);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint uCode, uint uMapType);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern IntPtr SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  public struct RECT { public int Left, Top, Right, Bottom; }
  // 按标题包含 "ELDEN RING" 找窗口：class 名匹配在 1.17.2 时好时坏。
  public static IntPtr Find() {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => {
      if (!IsWindowVisible(h)) return true;
      var sb = new StringBuilder(256);
      GetWindowTextW(h, sb, 256);
      if (sb.ToString().IndexOf("ELDEN RING", StringComparison.OrdinalIgnoreCase) >= 0) {
        found = h;
        return false;
      }
      return true;
    }, IntPtr.Zero);
    return found;
  }
  public static void Focus(IntPtr h) {
    if (h != IntPtr.Zero && GetForegroundWindow() != h) SetForegroundWindow(h);
  }
  public static void Tap(byte vk, int holdMs) {
    uint scan = MapVirtualKey(vk, 0);
    keybd_event(vk, (byte)scan, 0, UIntPtr.Zero);
    System.Threading.Thread.Sleep(holdMs);
    keybd_event(vk, (byte)scan, 2, UIntPtr.Zero);
  }
  public static void ClickFraction(IntPtr h, double fx, double fy) {
    RECT r;
    if (!GetWindowRect(h, out r)) return;
    int w = r.Right - r.Left;
    int hgt = r.Bottom - r.Top;
    // 窗口最小化时 rect 是 -32000; 别把点击甩到桌面/浏览器上
    if (w < 800 || hgt < 600 || r.Left <= -10000 || r.Top <= -10000) return;
    if (GetForegroundWindow() != h) return;
    int x = r.Left + (int)(w * fx);
    int y = r.Top + (int)(hgt * fy);
    SetCursorPos(x, y);
    System.Threading.Thread.Sleep(120);
    mouse_event(0x0002, 0, 0, 0, UIntPtr.Zero);
    System.Threading.Thread.Sleep(60);
    mouse_event(0x0004, 0, 0, 0, UIntPtr.Zero);
    System.Threading.Thread.Sleep(120);
  }
}
'@

. (Join-Path $PSScriptRoot 'gamedir.ps1')
$game = Get-ErEchoGameDir   # 源码已搬出游戏目录，统一走探测（见 gamedir.ps1）
$log = Join-Path $game 'er_echo.log'

if (-not $NoLaunch) {
    Start-Process -FilePath (Join-Path $game 'launchmod_eldenring.bat') -WorkingDirectory $game
}

$startLen = if (Test-Path $log) { (Get-Item $log).Length } else { 0 }
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$attempts = 0
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    $h = [EnterGameKey]::Find()
    if ($h -eq [IntPtr]::Zero) { continue }
    [EnterGameKey]::Focus($h)
    Start-Sleep -Milliseconds 200
    if ($Click) {
        # 可选：标题界面只认鼠标点击（合成 E 无效）。0.78h 是「请按任一按钮」；
        # 0.32h 是离线提示的「确定」；0.46h 是主菜单「继续游戏」。
        [EnterGameKey]::ClickFraction($h, 0.5, 0.78) | Out-Null
        [EnterGameKey]::ClickFraction($h, 0.5, 0.32) | Out-Null
        [EnterGameKey]::ClickFraction($h, 0.5, 0.46) | Out-Null
    }
    [EnterGameKey]::Tap(0x45, 400)   # E
    $attempts++

    if (Test-Path $log) {
        $len = (Get-Item $log).Length
        if ($len -gt $startLen) {
            $fs = [System.IO.File]::Open($log, 'Open', 'Read', 'ReadWrite')
            try {
                $fs.Seek($startLen, 'Begin') | Out-Null
                $sr = New-Object System.IO.StreamReader($fs)
                $new = $sr.ReadToEnd()
            } finally { $fs.Dispose() }
            if ($new -match 'event: entered game') {
                Write-Host "entered game after $attempts E presses"
                return
            }
        }
    }
}
Write-Warning "enter_game timed out after ${TimeoutSeconds}s ($attempts E presses)"
