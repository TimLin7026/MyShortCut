# -*- coding: utf-8 -*-
"""
MyShortCut - Windows 開機自啟動管理模組
"""
import os
import sys
import winreg

APP_REG_NAME = "MyShortCut"
RUN_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

def get_launch_command() -> str:
    """取得開機自啟動執行指令（無黑窗模式）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包後的 exe
        exe_path = os.path.abspath(sys.executable)
        return f'"{exe_path}" --tray'
    else:
        # Python 原始碼模式：尋找同目錄下的 pythonw.exe
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_py = os.path.join(base_dir, "main.py")
        
        # 取得 pythonw.exe
        py_dir = os.path.dirname(sys.executable)
        pythonw_exe = os.path.join(py_dir, "pythonw.exe")
        if not os.path.exists(pythonw_exe):
            pythonw_exe = sys.executable
            
        return f'"{pythonw_exe}" "{main_py}" --tray'

def is_autostart_enabled() -> bool:
    """檢查開機自啟動是否已啟用"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_REG_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_REG_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"[WARN] 查詢開機自啟動狀態失敗: {e}")
        return False

def enable_autostart() -> bool:
    """啟用開機自啟動"""
    cmd = get_launch_command()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_REG_NAME, 0, winreg.REG_SZ, cmd)
        return True
    except Exception as e:
        print(f"[ERROR] 設定開機自啟動失敗: {e}")
        return False

def disable_autostart() -> bool:
    """停用開機自啟動"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_REG_NAME)
        return True
    except FileNotFoundError:
        return True  # 本來就沒有
    except Exception as e:
        print(f"[ERROR] 移除開機自啟動失敗: {e}")
        return False