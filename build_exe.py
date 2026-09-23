# -*- coding: utf-8 -*-
"""
MyShortCut - PyInstaller 一鍵無黑窗打包腳本 (含檔案佔用容錯保護)
"""
import os
import sys
import time
import shutil
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_PY = os.path.join(BASE_DIR, "main.py")
ICON_PATH = os.path.join(BASE_DIR, "assets", "app.ico")
DIST_DIR = os.path.join(BASE_DIR, "dist")
BUILD_DIR = os.path.join(BASE_DIR, "build")

def build():
    print("=" * 50)
    print("[INFO] 開始打包 MyShortCut.exe (無黑窗模式)...")
    print("=" * 50)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name", "MyShortCut",
        f"--icon={ICON_PATH}",
        f"--add-data=assets;assets",
        "--clean",
        MAIN_PY
    ]

    print(f"執行指令: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR)

    if result.returncode == 0:
        built_exe = os.path.join(DIST_DIR, "MyShortCut.exe")
        target_exe = os.path.join(BASE_DIR, "MyShortCut.exe")
        if os.path.exists(built_exe):
            try:
                shutil.copy2(built_exe, target_exe)
                print(f"[SUCCESS] 打包完成！已輸出至: {target_exe}")
            except PermissionError:
                # 檔案正被運行中的程式佔用，重命名為 .old 進行熱更換
                old_exe = target_exe + f".old_{int(time.time())}"
                try:
                    os.rename(target_exe, old_exe)
                    shutil.copy2(built_exe, target_exe)
                    print(f"[SUCCESS] 熱更換完成！已成功覆蓋至: {target_exe}")
                except Exception as e:
                    print(f"[WARN] 目標檔案被佔用無法覆蓋，產出位於: {built_exe} ({e})")
    else:
        print("[ERROR] 打包失敗，請檢查錯誤訊息。")

if __name__ == "__main__":
    build()