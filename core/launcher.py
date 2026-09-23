# -*- coding: utf-8 -*-
"""
MyShortCut - 捷徑執行呼叫核心模組
"""
import os
import sys
import subprocess
import webbrowser
from typing import Tuple
from .shortcut_manager import ShortcutItem

def launch_shortcut(item: ShortcutItem) -> Tuple[bool, str]:
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

        # 4. 目錄/資料夾：直接用檔案總管開啟
        if os.path.isdir(target):
            os.startfile(target)
            return True, f"已開啟資料夾: {target}"

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