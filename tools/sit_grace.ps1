#requires -Version 5
<#
.SYNOPSIS
  在游戏内按一次「交互」键盘 E（等价于手柄 Y）——用来坐着火/开赐福菜单。

.DESCRIPTION
  Elden Ring 的标题/对话框吃鼠标点，进入游戏后「在赐福休息」的交互键可以用
  键盘 E。这里用 keybd_event（不是 SendInput）发扫描码，实测游戏能收到。
  只发一次，不做循环；需要重复就多跑几次。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\sit_grace.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\sit_grace.ps1 -DelayMs 1500
#>
param(
    [int]$DelayMs = 500
)

Add-Type @'
using System;
using System.Runtime.InteropServices;
public class SitGraceKey {
  [DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint uCode, uint uMapType);
  public static void TapE() {
    uint scan = MapVirtualKey(0x45, 0);
    keybd_event(0x45, (byte)scan, 0, UIntPtr.Zero);
    System.Threading.Thread.Sleep(150);
    keybd_event(0x45, (byte)scan, 2, UIntPtr.Zero);
  }
}
'@

Start-Sleep -Milliseconds $DelayMs
[SitGraceKey]::TapE()
Write-Host "sent E (grace interact)"
