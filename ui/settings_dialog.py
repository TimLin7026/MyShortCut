import os
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional
from core.shortcut_manager import ShortcutManager
from core.autostart import is_autostart_enabled, enable_autostart, disable_autostart
from ui.styles import *

class RECT(ctypes.Structure):
    _fields_ = [
        ('left', wintypes.LONG),
        ('top', wintypes.LONG),
        ('right', wintypes.LONG),
        ('bottom', wintypes.LONG)
    ]

def get_work_area():
    rect = RECT()
    SPI_GETWORKAREA = 0x0030
    if ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
        return rect.left, rect.top, rect.right, rect.bottom
    return None

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, manager: ShortcutManager, version: str, on_settings_changed: Optional[Callable] = None):
        super().__init__(parent)
        self.manager = manager
        self.version = version
        self.on_settings_changed = on_settings_changed

        self.title("偏好設定")
        self.win_w = 480
        self.win_h = 500
        self.minsize(440, 460)
        self.configure(bg=BG_COLOR)
        self.transient(parent)
        self.grab_set()

        # 載入視窗標題列圖示
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(base_dir, "assets", "app.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        # 定位至右下角 (含螢幕邊界碰撞防呆)
        self._position_bottom_right()
        self._build_ui()

    def _position_bottom_right(self):
        """將設定視窗定位於螢幕右下角安全區域，具備邊界碰撞防呆"""
        self.update_idletasks()
        w = self.win_w
        h = self.win_h
        work_area = get_work_area()
        if work_area:
            left, top, right, bottom = work_area
            x = right - w - 20
            y = bottom - h - 55
            # 嚴格邊界碰撞防呆
            x = max(left + 10, min(x, right - w - 10))
            y = max(top + 10, min(y, bottom - h - 10))
        else:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = max(10, sw - w - 30)
            y = max(10, sh - h - 90)

        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        container = tk.Frame(self, bg=BG_COLOR, padx=20, pady=15)
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(container, text="⚙️ 軟體偏好設定", font=FONT_TITLE, bg=BG_COLOR, fg=PRIMARY_COLOR).pack(anchor="w", pady=(0, 12))

        # 1. 視窗預設高度卡片
        card_h = tk.LabelFrame(container, text=" 視窗預設高度 ", font=FONT_BOLD, bg=CARD_BG, fg=TEXT_COLOR, padx=15, pady=10)
        card_h.pack(fill=tk.X, pady=(0, 10))

        self.var_height_mode = tk.StringVar(value=self.manager.get_window_height_mode())
        rdo_half = tk.Radiobutton(
            card_h,
            text="📱 半高模式 (螢幕高度 50%，預設高約 480px)",
            variable=self.var_height_mode,
            value="half",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_COLOR,
            activebackground=CARD_BG,
            activeforeground=TEXT_COLOR,
            selectcolor="#FFFFFF",
            wraplength=420,
            justify="left",
            anchor="w",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self._on_change_height_mode
        )
        rdo_half.pack(fill=tk.X, anchor="w", pady=(0, 6))

        rdo_full = tk.Radiobutton(
            card_h,
            text="🖥 全高模式 (螢幕高度 100%，縱向延伸清單)",
            variable=self.var_height_mode,
            value="full",
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_COLOR,
            activebackground=CARD_BG,
            activeforeground=TEXT_COLOR,
            selectcolor="#FFFFFF",
            wraplength=420,
            justify="left",
            anchor="w",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self._on_change_height_mode
        )
        rdo_full.pack(fill=tk.X, anchor="w", pady=(0, 2))

        # 2. 功能開關卡片
        card = tk.LabelFrame(container, text=" 功能開關 ", font=FONT_BOLD, bg=CARD_BG, fg=TEXT_COLOR, padx=15, pady=10)
        card.pack(fill=tk.X, pady=(0, 10))

        # 資料夾分頁開啟開關
        self.var_folder_tab = tk.BooleanVar(value=self.manager.get_open_folder_in_tab())
        chk_folder_tab = tk.Checkbutton(
            card,
            text="📁 資料夾於現有檔案總管開新分頁 (若已開啟視窗則自動分頁)",
            variable=self.var_folder_tab,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_COLOR,
            activebackground=CARD_BG,
            activeforeground=TEXT_COLOR,
            selectcolor="#FFFFFF",
            wraplength=410,
            justify="left",
            anchor="w",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self._on_toggle_folder_tab
        )
        chk_folder_tab.pack(fill=tk.X, anchor="w", pady=(0, 8))

        # 失去焦點自動隱藏開關
        self.var_auto_hide = tk.BooleanVar(value=self.manager.get_auto_hide_on_lose_focus())
        chk_auto_hide = tk.Checkbutton(
            card,
            text="💨 失去焦點自動隱藏 (點擊視窗外部時自動縮小至系統列)",
            variable=self.var_auto_hide,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_COLOR,
            activebackground=CARD_BG,
            activeforeground=TEXT_COLOR,
            selectcolor="#FFFFFF",
            wraplength=410,
            justify="left",
            anchor="w",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self._on_toggle_auto_hide
        )
        chk_auto_hide.pack(fill=tk.X, anchor="w", pady=(0, 8))

        # 依使用頻率排序開關
        self.var_freq = tk.BooleanVar(value=self.manager.sort_by_frequency)
        chk_freq = tk.Checkbutton(
            card,
            text="📊 依使用頻率排序 (自動將高頻點擊捷徑排列在最前)",
            variable=self.var_freq,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_COLOR,
            activebackground=CARD_BG,
            activeforeground=TEXT_COLOR,
            selectcolor="#FFFFFF",
            wraplength=410,
            justify="left",
            anchor="w",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self._on_toggle_freq
        )
        chk_freq.pack(fill=tk.X, anchor="w", pady=(0, 8))

        # 開機自啟動開關
        self.var_auto = tk.BooleanVar(value=is_autostart_enabled())
        chk_auto = tk.Checkbutton(
            card,
            text="🚀 Windows 開機自動啟動 (開機時自動於系統列常駐待命)",
            variable=self.var_auto,
            font=FONT_NORMAL,
            bg=CARD_BG,
            fg=TEXT_COLOR,
            activebackground=CARD_BG,
            activeforeground=TEXT_COLOR,
            selectcolor="#FFFFFF",
            wraplength=410,
            justify="left",
            anchor="w",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=self._on_toggle_auto
        )
        chk_auto.pack(fill=tk.X, anchor="w", pady=(0, 4))

        # 版本與資訊
        info_frame = tk.Frame(container, bg=BG_COLOR)
        info_frame.pack(fill=tk.X, pady=(8, 0))
        tk.Label(info_frame, text=f"MyShortCut 版本: {self.version}", font=FONT_SMALL, bg=BG_COLOR, fg=TEXT_MUTED).pack(side=tk.LEFT)
        ttk.Button(info_frame, text="關閉", width=10, command=self.destroy).pack(side=tk.RIGHT)

    def _on_change_height_mode(self):
        new_mode = self.var_height_mode.get()
        self.manager.set_window_height_mode(new_mode)
        if self.on_settings_changed:
            self.on_settings_changed()

    def _on_toggle_folder_tab(self):
        new_val = self.var_folder_tab.get()
        self.manager.set_open_folder_in_tab(new_val)
        if self.on_settings_changed:
            self.on_settings_changed()

    def _on_toggle_auto_hide(self):
        new_val = self.var_auto_hide.get()
        self.manager.set_auto_hide_on_lose_focus(new_val)
        if self.on_settings_changed:
            self.on_settings_changed()

    def _on_toggle_freq(self):
        new_val = self.var_freq.get()
        self.manager.set_sort_by_frequency(new_val)
        if self.on_settings_changed:
            self.on_settings_changed()

    def _on_toggle_auto(self):
        if self.var_auto.get():
            if enable_autostart():
                messagebox.showinfo("開機自啟動", "已成功啟用 Windows 開機自動啟動！", parent=self)
            else:
                self.var_auto.set(False)
                messagebox.showerror("錯誤", "啟用開機自啟動失敗，請確認權限。", parent=self)
        else:
            if disable_autostart():
                messagebox.showinfo("開機自啟動", "已關閉 Windows 開機自動啟動。", parent=self)
            else:
                self.var_auto.set(True)
                messagebox.showerror("錯誤", "關閉開機自啟動失敗。", parent=self)
        if self.on_settings_changed:
            self.on_settings_changed()
