# -*- coding: utf-8 -*-
"""
MyShortCut - 檔案捷徑系統列常駐啟動器
主程式進入點 (精簡系統列選單：純功能清單)
"""
import os
import sys
import threading
from typing import Optional
import tkinter as tk
from tkinter import messagebox
from PIL import Image
import pystray
from pystray import MenuItem as item, Menu

# 載入核心模組
from core.shortcut_manager import ShortcutManager, get_app_dir
from core.launcher import launch_shortcut
from core.autostart import is_autostart_enabled, enable_autostart, disable_autostart
from core.single_instance import SingleInstanceManager
from ui.main_window import MainWindow
import updater

# 讀取版本號與目錄
BASE_DIR = get_app_dir()
VERSION_FILE = os.path.join(BASE_DIR, "version.txt")
VERSION = "v1.20261007.1"
if os.path.exists(VERSION_FILE):
    try:
        with open(VERSION_FILE, "r", encoding="utf-8-sig") as f:
            v = f.read().strip()
            if v:
                VERSION = v
    except Exception:
        pass

class MyShortCutApp:
    def __init__(self, silent_mode: bool = False, instance_mgr: Optional[SingleInstanceManager] = None):
        self.silent_mode = silent_mode
        self.instance_mgr = instance_mgr
        self.manager = ShortcutManager()
        self.tray_icon = None
        
        # 建立 UI 主視窗
        self.window = MainWindow(
            manager=self.manager,
            version=VERSION,
            on_shortcuts_updated=self.update_tray_menu
        )

        # 綁定單一實例 IPC 回調
        if self.instance_mgr:
            self.instance_mgr.on_show_request = lambda: self.window.after(0, self.window.show_window)
            self.instance_mgr.on_exit_request = lambda: self.window.after(0, self._on_exit_app)

        # 初始化托盤
        self._init_tray()

        if self.silent_mode:
            self.window.withdraw()
        else:
            self.window.show_window()

    def _init_tray(self):
        icon_path = os.path.join(BASE_DIR, "assets", "tray_icon.png")
        if os.path.exists(icon_path):
            image = Image.open(icon_path)
        else:
            image = Image.new('RGB', (64, 64), color=(33, 150, 243))

        self.tray_icon = pystray.Icon(
            "MyShortCut",
            image,
            f"MyShortCut - 檔案捷徑啟動器 ({VERSION})",
            menu=pystray.Menu(lambda: self._generate_tray_menu())
        )

        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _generate_tray_menu(self):
        """生成系統列右鍵功能選單 (純功能項目，不顯示捷徑清單)"""
        menu_items = [
            item("🛠️ 開啟捷徑管理面板", self._on_show_main_window, default=True),
            item("📊 依使用頻率排序", self._on_toggle_freq_tray, checked=lambda item: self.manager.sort_by_frequency),
            item("🚀 開機自動啟動", self._on_toggle_autostart_tray, checked=lambda item: is_autostart_enabled()),
            pystray.Menu.SEPARATOR,
            item("❌ 結束程式", self._on_exit_app)
        ]
        return menu_items

    def _on_show_main_window(self):
        self.window.after(0, self.window.show_window)

    def _on_toggle_freq_tray(self):
        new_state = not self.manager.sort_by_frequency
        self.manager.set_sort_by_frequency(new_state)
        self.window.after(0, lambda: self.window.var_freq_sort.set(new_state))
        self.window.after(0, self.window.refresh_list)
        if self.tray_icon:
            self.tray_icon.update_menu()

    def _on_toggle_autostart_tray(self):
        if is_autostart_enabled():
            disable_autostart()
        else:
            enable_autostart()
        self.window.after(0, lambda: self.window.var_autostart.set(is_autostart_enabled()))
        if self.tray_icon:
            self.tray_icon.update_menu()

    def update_tray_menu(self):
        if self.tray_icon:
            self.tray_icon.update_menu()

    def _on_exit_app(self):
        if self.instance_mgr:
            self.instance_mgr.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        self.window.after(0, self.window.destroy)

    def run(self):
        self.window.mainloop()


def main():
    try:
        updater.check_and_apply_update(target_dir=BASE_DIR, enabled=False)
    except Exception as e:
        print(f"[WARN] 更新檢查略過: {e}")

    # 單一實例檢查與接管處理
    force_replace = ("--replace" in sys.argv or "--force" in sys.argv)
    instance_mgr = SingleInstanceManager(version=VERSION)
    can_start = instance_mgr.check_and_bind(force_replace=force_replace)
    if not can_start:
        # 已有同版本實例且已通知其喚醒，當前實例安全退出
        sys.exit(0)

    silent_mode = ("--tray" in sys.argv or "--silent" in sys.argv)
    app = MyShortCutApp(silent_mode=silent_mode, instance_mgr=instance_mgr)
    app.run()


if __name__ == "__main__":
    main()