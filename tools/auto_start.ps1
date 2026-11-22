param(
    [int]$TimeoutSeconds = 150,
    [int]$IntervalSeconds = 2,
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'gamedir.ps1')
$game = Get-ErEchoGameDir   # 源码已搬出游戏目录，统一走探测（见 gamedir.ps1）
$log = Join-Path $game 'er_echo.log'
$status = Join-Path $game 'er_echo_status.json'

Add-Type @'
using System;
using System.Runtime.InteropServices;
public class AutoStartWin {
  [StructLayout(LayoutKind.Sequential)] public struct KEYBDINPUT { public ushort wVk; public ushort wScan; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }
  [StructLayout(LayoutKind.Sequential)] public struct MOUSEINPUT { public int dx; public int dy; public uint mouseData; public uint dwFlags; public uint time; public IntPtr dwExtraInfo; }
  [StructLayout(LayoutKind.Explicit)] public struct INPUT { [FieldOffset(0)] public uint type; [FieldOffset(8)] public KEYBDINPUT ki; [FieldOffset(8)] public MOUSEINPUT mi; }
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern uint SendInput(uint n, INPUT[] p, int cb);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint uCode, uint uMapType);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindowW(string cls, string title);

  public static IntPtr GameWindow(IntPtr fallback) {
    IntPtr h = FindWindowW(null, "ELDEN RING\u2122");
    if (h == IntPtr.Zero) h = FindWindowW(null, "ELDEN RING");
    return h == IntPtr.Zero ? fallback : h;
  }
  public static void Click(int x, int y) {
    SetCursorPos(x, y);
    System.Threading.Thread.Sleep(120);
    INPUT[] a = new INPUT[1];
    a[0].type = 0;
    a[0].mi.dwFlags = 0x0002;
    SendInput(1, a, Marshal.SizeOf(typeof(INPUT)));
    System.Threading.Thread.Sleep(60);
    a[0].mi.dwFlags = 0x0004;
    SendInput(1, a, Marshal.SizeOf(typeof(INPUT)));
  }
  public static void Enter() {
    INPUT[] a = new INPUT[1];
    a[0].type = 1;
    a[0].ki.wScan = (ushort)MapVirtualKey(0x0D, 0);
    a[0].ki.dwFlags = 0x0008;
    SendInput(1, a, Marshal.SizeOf(typeof(INPUT)));
    System.Threading.Thread.Sleep(80);
    a[0].ki.dwFlags = 0x000A;
    SendInput(1, a, Marshal.SizeOf(typeof(INPUT)));
  }
  public static void Focus(IntPtr hwnd) {
    uint fgPid = 0;
    uint fgThread = GetWindowThreadProcessId(GetForegroundWindow(), out fgPid);
    uint myThread = GetCurrentThreadId();
    AttachThreadInput(myThread, fgThread, true);
    ShowWindow(hwnd, 9);
    BringWindowToTop(hwnd);
    SetForegroundWindow(hwnd);
    AttachThreadInput(myThread, fgThread, false);
  }
  public static int[] Rect(IntPtr hwnd) {
    RECT r;
    if (!GetWindowRect(hwnd, out r)) return null;
    return new int[] { r.Left, r.Top, r.Right, r.Bottom };
  }
}
'@

if (-not $NoLaunch) {
    Write-Host "launching $game\launchmod_eldenring.bat"
    Start-Process -FilePath (Join-Path $game 'launchmod_eldenring.bat') -WorkingDirectory $game
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$started = Get-Date
$lastLogPos = 0
if (Test-Path $log) { $lastLogPos = (Get-Item $log).Length }

while ((Get-Date) -lt $deadline) {
    $p = Get-Process eldenring -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $p) { Start-Sleep -Seconds 2; continue }

    $hwnd = [AutoStartWin]::GameWindow($p.MainWindowHandle)
    try { [AutoStartWin]::Focus($hwnd) } catch {}
    $rect = [AutoStartWin]::Rect($hwnd)
    if ($rect) {
        $cx = [int](($rect[0] + $rect[2]) / 2)
        $h = $rect[3] - $rect[1]
        [AutoStartWin]::Click($cx, $rect[1] + [int]($h * 0.55))
        Start-Sleep -Milliseconds 250
        [AutoStartWin]::Click($cx, $rect[1] + [int]($h * 0.78))
    }
    [AutoStartWin]::Enter()
    Start-Sleep -Seconds $IntervalSeconds

    if (Test-Path $status) {
        try {
            $fresh = (Get-Item $status).LastWriteTime -gt $started
            $j = Get-Content $status -Raw | ConvertFrom-Json
            if ($fresh -and $j.frame -gt 0 -and @($j.clones).Count -gt 0) {
                Write-Host "in game: frame=$($j.frame) clones=$(@($j.clones).Count)"
                return
            }
        } catch {}
    }

    if (Test-Path $log) {
        $len = (Get-Item $log).Length
        if ($len -gt $lastLogPos) {
            $new = Get-Content $log -Tail 200 -Encoding UTF8 | Out-String
            $lastLogPos = $len
            if ($new -match 'event: entered game') {
                Write-Host "entered game (no clone yet); waiting 15s"
                Start-Sleep -Seconds 15
                return
            }
        }
    }
}

Write-Warning "auto_start timed out after ${TimeoutSeconds}s"
