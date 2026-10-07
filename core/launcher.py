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
from typing import Tuple, Optional

import win32gui
import win32con
import win32process
import win32clipboard

from .shortcut_manager import ShortcutItem

VK_CONTROL = 0x11
VK_T = 0x54
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
    """模擬發送組合鍵 (例如 Ctrl + T, Ctrl + L, Ctrl + V)"""
    ctypes.windll.user32.keybd_event(mod_vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(key_vk, 0, 0, 0)
    time.sleep(0.04)
    ctypes.windll.user32.keybd_event(key_vk, 0, KEYEVENTF_KEYUP, 0)
    ctypes.windll.user32.keybd_event(mod_vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.04)

def _press_single_key(key_vk: int):
    """模擬發送單一按鍵 (例如 Enter)"""
    ctypes.windll.user32.keybd_event(key_vk, 0, 0, 0)
    time.sleep(0.03)
    ctypes.windll.user32.keybd_event(key_vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.03)

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

def _delayed_restore_clipboard(old_text: Optional[str], delay_sec: float = 0.5):
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

def open_folder(folder_path: str, prefer_tab: bool = True) -> Tuple[bool, str]:
    """
    開啟資料夾路徑：
    若啟用 prefer_tab 且已有開啟的檔案總管視窗，則在現有視窗開啟新分頁 (Ctrl+T)；
    否則以原生獨立視窗方式開啟。
    """
    target = os.path.normpath(folder_path.strip().strip('"').strip("'"))
    if not os.path.exists(target) or not os.path.isdir(target):
        return False, f"找不到目標資料夾: {target}"

    if prefer_tab:
        hwnd = _find_explorer_hwnd()
        if hwnd:
            try:
                # 1. 喚醒檔案總管至前景
                _bring_window_to_foreground(hwnd)
                time.sleep(0.12)

                # 2. 開新分頁 Ctrl + T
                _press_key_combo(VK_CONTROL, VK_T)
                time.sleep(0.15)

                # 3. 聚焦網址列 Ctrl + L
                _press_key_combo(VK_CONTROL, VK_L)
                time.sleep(0.1)

                # 4. 備份原剪貼簿並放入目標路徑
                old_clipboard = _set_clipboard_with_backup(target)

                # 5. 貼上路徑 Ctrl + V
                _press_key_combo(VK_CONTROL, VK_V)
                time.sleep(0.05)

                # 6. 送出 Enter 導航
                _press_single_key(VK_RETURN)

                # 7. 延遲還原剪貼簿
                _delayed_restore_clipboard(old_clipboard, delay_sec=0.5)

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