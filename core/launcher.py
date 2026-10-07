# -*- coding: utf-8 -*-
"""
MyShortCut - 捷徑執行呼叫核心模組 (支援 Windows 檔案總管現有視窗開新分頁)
"""
import os
import sys
import time
import threading
import ctypes
from ctypes import wintypes
import subprocess
import webbrowser
import urllib.parse
from typing import Tuple, Optional

import win32gui
import win32con
import win32process
import win32clipboard

from .shortcut_manager import ShortcutItem

VK_MENU = 0x12
VK_CONTROL = 0x11
VK_T = 0x54
VK_D = 0x44
VK_L = 0x4C
VK_V = 0x56
VK_RETURN = 0x0D
KEYEVENTF_KEYUP = 0x0002

def _find_explorer_hwnd() -> Optional[int]:
    """尋找當前存在的 Windows 檔案總管頂層視窗 HWND"""
    found_hwnd = None
    def enum_cb(hwnd, _):
        nonlocal found_hwnd
        if win32gui.IsWindowVisible(hwnd):
            cls_name = win32gui.GetClassName(hwnd)
            if cls_name == "CabinetWClass":
                found_hwnd = hwnd
                return False
        return True
    try:
        win32gui.EnumWindows(enum_cb, None)
    except Exception:
        pass
    return found_hwnd

def _bring_window_to_foreground(hwnd: int):
    """將指定視窗喚醒至前景並取得焦點"""
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    else:
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

    try:
        fore_hwnd = win32gui.GetForegroundWindow()
        fore_thread, _ = win32process.GetWindowThreadProcessId(fore_hwnd)
        app_thread = win32process.GetCurrentThreadId()
        if fore_thread != app_thread:
            win32process.AttachThreadInput(fore_thread, app_thread, True)
            win32gui.SetForegroundWindow(hwnd)
            win32process.AttachThreadInput(fore_thread, app_thread, False)
        else:
            win32gui.SetForegroundWindow(hwnd)
    except Exception:
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass

def _press_key_combo(mod_vk: int, key_vk: int):
    """模擬發送組合鍵 (例如 Ctrl + T, Alt + D, Ctrl + V)"""
    ctypes.windll.user32.keybd_event(mod_vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(key_vk, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(key_vk, 0, KEYEVENTF_KEYUP, 0)
    ctypes.windll.user32.keybd_event(mod_vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)

def _press_single_key(key_vk: int):
    """模擬發送單一按鍵 (例如 Enter)"""
    ctypes.windll.user32.keybd_event(key_vk, 0, 0, 0)
    time.sleep(0.04)
    ctypes.windll.user32.keybd_event(key_vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.04)

def _set_clipboard_with_backup(text: str) -> Optional[str]:
    """將文字寫入剪貼簿並傳回原本的剪貼簿內容"""
    old_text = None
    try:
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            old_text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
    except Exception:
        pass

    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
        win32clipboard.CloseClipboard()
    except Exception:
        pass

    return old_text

def _delayed_restore_clipboard(old_text: Optional[str], delay_sec: float = 0.8):
    """延遲還原使用者原本的剪貼簿內容 (非同步執行，不阻礙主線程)"""
    if old_text is None:
        return
    def _worker():
        time.sleep(delay_sec)
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, old_text)
            win32clipboard.CloseClipboard()
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()

def _find_existing_tab_for_path(target_path: str) -> Optional[Tuple[int, str]]:
    """
    檢查目前所有已開啟的檔案總管分頁，若已有相同路徑的分頁，回傳 (hwnd, tab_name)；否則回傳 None。
    嚴格過濾幽靈視窗與無效 HWND。
    """
    target_norm = os.path.normpath(target_path).lower()
    try:
        import win32com.client
        shell_app = win32com.client.Dispatch("Shell.Application")
        for w in shell_app.Windows():
            try:
                hwnd = getattr(w, "HWND", None)
                if not hwnd or not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                    continue

                url = getattr(w, "LocationURL", "")
                if url.startswith("file:///"):
                    raw_path = url[8:]
                    decoded_path = urllib.parse.unquote(raw_path).replace("/", "\\")
                    if os.path.normpath(decoded_path).lower() == target_norm:
                        tab_name = getattr(w, "LocationName", "")
                        return hwnd, tab_name
            except Exception:
                continue
    except Exception:
        pass
    return None

def _switch_to_tab(hwnd: int, tab_name: str, folder_name: str) -> bool:
    """
    將檔案總管視窗帶到前景，並切換至名為 tab_name (或 folder_name) 的分頁。
    """
    # 1. 喚醒檔案總管視窗至前景
    _bring_window_to_foreground(hwnd)
    time.sleep(0.08)

    # 2. 檢查目前頂層視窗標題，若已經是該分頁，直接完成
    current_title = win32gui.GetWindowText(hwnd)
    name_to_match = tab_name or folder_name
    if name_to_match and name_to_match.lower() in current_title.lower():
        return True

    # 3. 透過 PowerShell + UI Automation 切換 TabItem
    clean_name = name_to_match.replace("'", "''")
    clean_folder = folder_name.replace("'", "''")
    ps_script = f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
try {{
    $el = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]{hwnd})
    if ($el) {{
        $cond = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::TabItem
        )
        $tabs = $el.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
        foreach ($t in $tabs) {{
            $n = $t.Current.Name
            if ($n -eq '{clean_name}' -or $n -eq '{clean_folder}') {{
                $pattern = $t.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
                $pattern.Select()
                break
            }}
        }}
    }}
}} catch {{}}
"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=1.5
        )
        return True
    except Exception:
        return False

def open_folder(folder_path: str, prefer_tab: bool = True) -> Tuple[bool, str]:
    """
    開啟資料夾路徑：
    1. 若已有相同路徑的分頁，直接將視窗帶至前景並切換至該分頁 (不開新分頁)；
    2. 若無相同分頁但啟用 prefer_tab，則在現有檔案總管開啟新分頁；
    3. 否則以原生獨立視窗方式開啟。
    """
    target = os.path.normpath(folder_path.strip().strip('"').strip("'"))
    if not os.path.exists(target) or not os.path.isdir(target):
        return False, f"找不到目標資料夾: {target}"

    # 第一優先：檢查是否已有相同路徑的分頁 (Tab Reuse)
    folder_name = os.path.basename(target) or target
    existing_tab = _find_existing_tab_for_path(target)
    if existing_tab:
        hwnd, tab_name = existing_tab
        _switch_to_tab(hwnd, tab_name, folder_name)
        return True, f"已切換至現有分頁: {target}"

    # 第二步：無重複分頁，若啟用 prefer_tab 且有開啟的檔案總管視窗，開新分頁
    if prefer_tab:
        hwnd = _find_explorer_hwnd()
        if hwnd:
            try:
                # 取得目前已有的 COM ShellWindows 數量
                shell_app = None
                before_count = 0
                try:
                    import win32com.client
                    shell_app = win32com.client.Dispatch("Shell.Application")
                    before_count = len(list(shell_app.Windows()))
                except Exception:
                    shell_app = None

                # 1. 喚醒檔案總管至前景
                _bring_window_to_foreground(hwnd)
                time.sleep(0.15)

                # 2. 開新分頁 Ctrl + T
                _press_key_combo(VK_CONTROL, VK_T)

                # 3. 軌道 A：優先嘗試 COM Navigate2 原生導向 (若能捕獲新分頁)
                navigated_by_com = False
                if shell_app is not None:
                    for _ in range(5):
                        time.sleep(0.08)
                        try:
                            current_wins = list(shell_app.Windows())
                            if len(current_wins) > before_count:
                                new_win = current_wins[-1]
                                new_win.Navigate2(target)
                                navigated_by_com = True
                                break
                        except Exception:
                            pass

                if navigated_by_com:
                    return True, f"已在現有檔案總管開啟新分頁 (COM): {target}"

                # 4. 軌道 B：強化版鍵盤時序備援 (若 COM 未回報新分頁)
                # 等待分頁與網址列 UI 完整渲染 (共約 0.35 秒)
                time.sleep(0.25)

                # 聚焦網址列：使用 Alt + D (比 Ctrl+L 更具強制性且自動全選網址)
                _press_key_combo(VK_MENU, VK_D)
                time.sleep(0.15)

                # 備份原剪貼簿並放入目標路徑
                old_clipboard = _set_clipboard_with_backup(target)

                # 貼上路徑 Ctrl + V
                _press_key_combo(VK_CONTROL, VK_V)
                # 等待 0.15 秒確保文字已完整填入網址列控制項
                time.sleep(0.15)

                # 送出 Enter 導航
                _press_single_key(VK_RETURN)

                # 延遲還原剪貼簿 (0.8 秒防護期)
                _delayed_restore_clipboard(old_clipboard, delay_sec=0.8)

                return True, f"已在現有檔案總管開啟新分頁: {target}"
            except Exception:
                # 發生異常自動降級至原生開啟
                pass

    # 無現有視窗或非分頁模式
    os.startfile(target)
    return True, f"已開啟資料夾: {target}"

def launch_shortcut(item: ShortcutItem, prefer_tab: bool = True) -> Tuple[bool, str]:
    """
    執行捷徑項目
    回傳值: (是否成功, 訊息或錯誤說明)
    """
    target = item.target_path.strip()
    if not target:
        return False, "目標路徑為空"

    try:
        # 1. 網頁網址
        if target.startswith(("http://", "https://")):
            webbrowser.open(target)
            return True, f"已開啟網址: {target}"

        # 2. 特殊 Windows shell / 設定指令
        if target.startswith(("ms-settings:", "shell:")):
            os.startfile(target)
            return True, f"已執行系統指令: {target}"

        # 3. 本地路徑檢查
        if not os.path.exists(target):
            return False, f"找不到目標檔案或路徑: {target}"

        # 4. 目錄/資料夾：支援現有檔案總管開新分頁
        if os.path.isdir(target):
            return open_folder(target, prefer_tab=prefer_tab)

        # 5. 檔案/執行檔
        working_dir = item.working_dir.strip()
        if not working_dir or not os.path.exists(working_dir):
            working_dir = os.path.dirname(os.path.abspath(target))

        # 若有額外參數且為 exe / bat / cmd / ps1 等可執行檔
        if item.arguments:
            cmd = f'"{target}" {item.arguments}'
            subprocess.Popen(cmd, cwd=working_dir, shell=True)
            return True, f"已執行程式 (帶參數): {item.name}"
        else:
            # 原生無黑窗呼叫
            os.startfile(target)
            return True, f"已啟動: {item.name}"

    except Exception as e:
        return False, f"啟動失敗: {str(e)}"