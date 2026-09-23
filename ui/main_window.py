# -*- coding: utf-8 -*-
"""
MyShortCut - 捷徑管理主介面 (現代化極簡啟動器：大圖示大字體、路徑隱藏、集中設定)
"""
import os
import sys
import time
import threading
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional, Callable, Dict, List

from core.shortcut_manager import ShortcutManager, ShortcutItem, guess_category
from core.launcher import launch_shortcut
from core.icon_extractor import IconExtractor
from ui.edit_dialog import ShortcutEditDialog
from ui.settings_dialog import SettingsDialog
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

class MainWindow(tk.Tk):
    def __init__(self, manager: ShortcutManager, version: str = "1.0", on_shortcuts_updated: Optional[Callable] = None):
        super().__init__()
        self.manager = manager
        self.version = version
        self.on_shortcuts_updated = on_shortcuts_updated
        self._icon_refs: Dict[str, any] = {}

        self.title("MyShortCut")
        self.win_width = 440
        self.win_height = 480
        self.minsize(400, 360)
        self.configure(bg=BG_COLOR)

        # 載入視窗標題列圖示
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(base_dir, "assets", "app.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        # 定位至右下角 (上提 50px 確保狀態列完整可見)
        self._position_bottom_right()

        # 攔截關閉事件 (隱藏至系統列常駐)
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        # 綁定失去焦點事件 (支援點擊外部自動縮小至系統列)
        self.bind("<FocusOut>", self._on_focus_out)

        self._init_style()
        self._build_ui()
        self.refresh_list()

    def _position_bottom_right(self):
        """計算並將視窗放置在螢幕右下角 (支援半高 50% 與全高 100% 模式)"""
        self.update_idletasks()
        mode = self.manager.get_window_height_mode()
        work_area = get_work_area()
        if work_area:
            left, top, right, bottom = work_area
            avail_h = bottom - top
            if mode == "full":
                self.win_height = max(500, avail_h - 55)
                y = top + 10
            else:
                self.win_height = 480
                y = bottom - self.win_height - 50
            x = right - self.win_width - 15
        else:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            if mode == "full":
                self.win_height = max(500, sh - 100)
                y = 20
            else:
                self.win_height = 480
                y = sh - self.win_height - 90
            x = sw - self.win_width - 20

        x = max(0, x)
        y = max(0, y)
        self.geometry(f"{self.win_width}x{self.win_height}+{x}+{y}")

    def toggle_height_mode(self):
        """快速切換全高 (100%) 與半高 (50%) 模式"""
        current = self.manager.get_window_height_mode()
        new_mode = "full" if current == "half" else "half"
        self.manager.set_window_height_mode(new_mode)
        self._update_height_button_icon()
        self._position_bottom_right()

    def _update_height_button_icon(self):
        """更新頂部高度切換按鈕圖示"""
        if hasattr(self, "btn_toggle_height"):
            mode = self.manager.get_window_height_mode()
            self.btn_toggle_height.config(text="🗗" if mode == "full" else "🗖")

    def _init_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        
        # 表格樣式：精簡緊湊行高 26px，字體採用 9pt FONT_LIST
        style.configure("Treeview",
                        background=CARD_BG,
                        foreground=TEXT_COLOR,
                        rowheight=26,
                        font=FONT_LIST,
                        fieldbackground=CARD_BG,
                        borderwidth=0)
        style.configure("Treeview.Heading",
                        background="#ECEFF1",
                        foreground=TEXT_COLOR,
                        font=FONT_BOLD,
                        borderwidth=1)
        style.map("Treeview", background=[("selected", PRIMARY_COLOR)], foreground=[("selected", "#FFFFFF")])
        
        # 統一按鈕、輸入框與下拉選單樣式字型
        style.configure("TButton", font=FONT_BTN)
        style.configure("TEntry", font=FONT_NORMAL)
        style.configure("TCombobox", font=FONT_NORMAL)
        style.configure("TCheckbutton", font=FONT_NORMAL)

    def _build_ui(self):
        # 1. 頂部搜尋、分類與高度切換列 (搜尋輸入框 + 分類下拉選單 + 高度切換按鈕)
        top_bar = tk.Frame(self, bg=BG_COLOR, padx=10, pady=8)
        top_bar.pack(fill=tk.X)

        tk.Label(top_bar, text="🔍", font=FONT_NORMAL, bg=BG_COLOR, fg=TEXT_MUTED).pack(side=tk.LEFT, padx=(0, 2))
        
        self.var_search = tk.StringVar()
        self.var_search.trace_add("write", lambda *args: self.refresh_list())
        ent_search = ttk.Entry(top_bar, textvariable=self.var_search, font=FONT_NORMAL)
        ent_search.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.btn_toggle_height = tk.Button(
            top_bar,
            text="🗖",
            font=("Segoe UI", 8),
            relief="solid",
            bd=1,
            bg="#F5F5F5",
            fg=TEXT_COLOR,
            activebackground="#E0E0E0",
            cursor="hand2",
            padx=4,
            pady=0,
            command=self.toggle_height_mode
        )
        self.btn_toggle_height.pack(side=tk.RIGHT, padx=(2, 0), ipady=0)
        self._update_height_button_icon()

        self.var_cat_filter = tk.StringVar(value="全部分類")
        self.cbo_cat = ttk.Combobox(top_bar, textvariable=self.var_cat_filter, state="readonly", width=8, font=FONT_NORMAL)
        self.cbo_cat.pack(side=tk.RIGHT, padx=(2, 2))
        self.cbo_cat.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())

        # 2. 中間內容區 (Treeview 全寬展示)
        content_frame = tk.Frame(self, bg=BG_COLOR, padx=10, pady=0)
        content_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("category", "launch_count")
        self.tree = ttk.Treeview(content_frame, columns=cols, show="tree headings", selectmode="extended")
        
        self.tree.heading("#0", text="捷徑名稱 (圖示)")
        self.tree.heading("category", text="分類")
        self.tree.heading("launch_count", text="次數")

        self.tree.column("#0", width=300, stretch=True, anchor="w")
        self.tree.column("category", width=55, stretch=False, anchor="center")
        self.tree.column("launch_count", width=45, stretch=False, anchor="center")

        scroll = ttk.Scrollbar(content_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 事件綁定：左鍵雙擊啟動、右鍵彈出快顯選單
        self.tree.bind("<Double-1>", lambda e: self._on_launch_selected())
        self.tree.bind("<Button-3>", self._on_tree_right_click)

        # 快捷鍵綁定：Alt+↑ / ↓ 移動排序 (在 Treeview 優先攔截並 return 'break' 阻止內建跳行行為)
        def _handle_move_up(e=None):
            self._on_move_up()
            return "break"

        def _handle_move_down(e=None):
            self._on_move_down()
            return "break"

        self.tree.bind("<Alt-Up>", _handle_move_up)
        self.tree.bind("<Alt-Down>", _handle_move_down)
        self.bind("<Alt-Up>", _handle_move_up)
        self.bind("<Alt-Down>", _handle_move_down)

        # 快捷鍵綁定：Ctrl+P 切換置頂、Enter 啟動、Delete 刪除、F11 切換全高/半高
        self.tree.bind("<Control-p>", self._on_toggle_pin)
        self.tree.bind("<Control-P>", self._on_toggle_pin)
        self.bind("<Control-p>", self._on_toggle_pin)
        self.bind("<Control-P>", self._on_toggle_pin)
        self.tree.bind("<Return>", lambda e: self._on_launch_selected())
        self.tree.bind("<Delete>", lambda e: self._on_delete())
        self.bind("<F11>", lambda e: self.toggle_height_mode())
        self.tree.bind("<F11>", lambda e: self.toggle_height_mode())

        # 3. 底部雙排操作按鈕區 (Grid Uniform 絕對等寬均分)
        action_frame = tk.Frame(self, bg=BG_COLOR, padx=10, pady=6)
        action_frame.pack(fill=tk.X)

        # 第一排：選取項操作 (啟動、編輯、刪除 - 1:1:1 絕對等寬均分)
        row1 = tk.Frame(action_frame, bg=BG_COLOR)
        row1.pack(fill=tk.X, pady=(0, 4))
        for col in range(3):
            row1.columnconfigure(col, weight=1, uniform="row1_group")

        ttk.Button(row1, text="▶ 啟動選取項", command=self._on_launch_selected).grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        ttk.Button(row1, text="✏ 編輯", command=self._on_edit).grid(row=0, column=1, sticky="nsew", padx=2)
        ttk.Button(row1, text="🗑 刪除", command=self._on_delete).grid(row=0, column=2, sticky="nsew", padx=(2, 0))

        # 第二排：全域新增與設定 (新增、資料夾、批次、設定 - 1:1:1:1 絕對等寬均分)
        row2 = tk.Frame(action_frame, bg=BG_COLOR)
        row2.pack(fill=tk.X)
        for col in range(4):
            row2.columnconfigure(col, weight=1, uniform="row2_group")

        ttk.Button(row2, text="➕ 新增", command=self._on_add).grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        ttk.Button(row2, text="📂 資料夾", command=self._on_add_folder).grid(row=0, column=1, sticky="nsew", padx=2)
        ttk.Button(row2, text="📁 批次", command=self._on_batch_add).grid(row=0, column=2, sticky="nsew", padx=2)
        ttk.Button(row2, text="⚙ 設定", command=self._on_open_settings).grid(row=0, column=3, sticky="nsew", padx=(2, 0))

        # 4. 底部狀態列
        status_bar = tk.Frame(self, bg="#ECEFF1", padx=8, pady=4)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.lbl_status = tk.Label(status_bar, text="", font=FONT_SMALL, bg="#ECEFF1", fg=TEXT_COLOR)
        self.lbl_status.pack(side=tk.LEFT)

        tk.Label(status_bar, text="Ctrl+P 置頂 | Alt+↑/↓ 移動", font=FONT_SMALL, bg="#ECEFF1", fg=TEXT_MUTED).pack(side=tk.RIGHT)

    def refresh_list(self):
        query = self.var_search.get().strip().lower()
        selected_cat = self.var_cat_filter.get()
        selected_ids = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        self._icon_refs.clear()

        items = self.manager.get_all()

        # 動態更新分類下拉選單清單
        available_cats = ["全部分類"] + sorted(list(set(it.category for it in items if it.category)))
        if list(self.cbo_cat["values"]) != available_cats:
            self.cbo_cat["values"] = available_cats
            if selected_cat not in available_cats:
                self.var_cat_filter.set("全部分類")
                selected_cat = "全部分類"

        count = 0
        for item in items:
            # 1. 關鍵字搜尋過濾
            if query and query not in item.name.lower() and query not in item.target_path.lower() and query not in item.category.lower():
                continue

            # 2. 分類下拉篩選
            if selected_cat and selected_cat != "全部分類" and item.category != selected_cat:
                continue

            try:
                # 採用 18x18 精緻小圖示
                tk_icon = IconExtractor.get_tk_icon(item.target_path, size=18)
                self._icon_refs[item.id] = tk_icon
            except Exception:
                tk_icon = None

            count_str = str(item.launch_count)
            name_display = f"  📌 {item.name}" if item.pinned else f"  {item.name}"

            self.tree.insert(
                "",
                tk.END,
                iid=item.id,
                text=name_display,
                image=tk_icon if tk_icon else "",
                values=(item.category, count_str)
            )
            count += 1

        # 恢復選取狀態
        to_select = [iid for iid in selected_ids if self.tree.exists(iid)]
        if to_select:
            self.tree.selection_set(to_select)

        mode_desc = "頻率排序" if self.manager.sort_by_frequency else "自訂排序"
        self.lbl_status.config(text=f"總計 {len(items)} 個 (顯示 {count} 個) | {mode_desc}")

        if self.on_shortcuts_updated:
            self.on_shortcuts_updated()

    def _get_selected_ids(self) -> List[str]:
        return list(self.tree.selection())

    def _on_tree_right_click(self, event):
        """右鍵單擊：選取該項目並彈出快顯選單"""
        row_id = self.tree.identify_row(event.y)
        if row_id:
            # 若點擊的項目不在當前選取集合中，則改為單選該項
            if row_id not in self.tree.selection():
                self.tree.selection_set(row_id)
            self._show_context_menu(event)

    def _show_context_menu(self, event):
        """顯示右鍵快顯功能選單"""
        selected_ids = self._get_selected_ids()
        if not selected_ids:
            return

        menu = tk.Menu(self, tearoff=0, font=FONT_NORMAL)
        item = self.manager.get_by_id(selected_ids[0])
        is_pinned = item.pinned if item else False
        pin_label = "📍 取消置頂 (Ctrl+P)" if is_pinned else "📌 設為置頂 (Ctrl+P)"

        menu.add_command(label=pin_label, command=self._on_toggle_pin)
        menu.add_separator()
        menu.add_command(label="▶️ 啟動選取項 (Enter)", command=self._on_launch_selected)
        menu.add_command(label="✏️ 編輯... (雙擊/右鍵)", command=self._on_edit)
        menu.add_command(label="📂 開啟所在資料夾", command=self._on_open_target_folder)
        menu.add_separator()
        curr_mode = self.manager.get_window_height_mode()
        h_label = "📱 切換為半高模式 (F11)" if curr_mode == "full" else "🖥️ 切換為全高模式 (F11)"
        menu.add_command(label=h_label, command=self.toggle_height_mode)
        menu.add_separator()
        menu.add_command(label="🗑️ 刪除 (Delete)", command=self._on_delete)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _on_toggle_pin(self, event=None):
        """切換選取項目的置頂狀態 (支援快捷鍵 Ctrl+P)"""
        selected_ids = self._get_selected_ids()
        if not selected_ids:
            return "break"
        for item_id in selected_ids:
            self.manager.toggle_pin(item_id)
        self.refresh_list()
        return "break"

    def _on_open_target_folder(self):
        """開啟選取項目所在資料夾"""
        selected_ids = self._get_selected_ids()
        if not selected_ids:
            return
        item = self.manager.get_by_id(selected_ids[0])
        if not item:
            return
        target_path = item.target_path
        folder = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
        if os.path.exists(folder):
            os.startfile(folder)
        else:
            messagebox.showwarning("提示", f"目標路徑所屬目錄不存在：\n{folder}", parent=self)

    def _on_add(self):
        def _save_callback(item: ShortcutItem):
            self.manager.add_item(item)
            self.refresh_list()
        ShortcutEditDialog(self, None, manager=self.manager, on_save=_save_callback)

    def _on_add_folder(self):
        """快速加入資料夾捷徑 (含重複防呆)"""
        d = filedialog.askdirectory(parent=self, title="選取要加入捷徑的資料夾")
        if d:
            d_clean = os.path.normpath(d)
            base_name = os.path.basename(d_clean) or d_clean
            dup = self.manager.find_duplicate(d_clean)
            if dup:
                messagebox.showwarning(
                    "捷徑已存在",
                    f"資料夾捷徑「{base_name}」已存在於清單中（捷徑名稱：{dup.name}），無法重複加入！",
                    parent=self
                )
                return
            item = ShortcutItem(name=base_name, target_path=d_clean, category="資料夾", working_dir=d_clean)
            self.manager.add_item(item)
            self.refresh_list()
            messagebox.showinfo("成功", f"已成功加入資料夾捷徑「{base_name}」！", parent=self)

    def _on_batch_add(self):
        """批次加入檔案捷徑 (自動過濾已存在的重複項目)"""
        files = filedialog.askopenfilenames(
            parent=self,
            title="選取要加入捷徑的檔案 (可多選)",
            filetypes=[("所有檔案與程式", "*.*"), ("執行檔 / 捷徑", "*.exe;*.lnk;*.bat;*.cmd"), ("各類文件", "*.docx;*.xlsx;*.pdf;*.txt;*.md")]
        )
        if files:
            added_count = 0
            skipped_count = 0
            for f in files:
                f_clean = os.path.normpath(f)
                if self.manager.find_duplicate(f_clean):
                    skipped_count += 1
                    continue
                base_name = os.path.splitext(os.path.basename(f_clean))[0]
                cat = guess_category(f_clean)
                item = ShortcutItem(name=base_name, target_path=f_clean, category=cat, working_dir=os.path.dirname(f_clean))
                self.manager.add_item(item)
                added_count += 1

            self.refresh_list()
            if added_count > 0 and skipped_count > 0:
                messagebox.showinfo("批次加入完成", f"已成功加入 {added_count} 個新捷徑！\n\n（已自動略過 {skipped_count} 個已存在的重複項目）", parent=self)
            elif added_count > 0 and skipped_count == 0:
                messagebox.showinfo("批次加入完成", f"已成功批次加入 {added_count} 個捷徑（已自動智慧分類）！", parent=self)
            else:
                messagebox.showinfo("提示", f"選取的 {skipped_count} 個檔案皆已存在於捷徑清單中，未重複加入。", parent=self)

    def _on_open_settings(self):
        """開啟偏好設定對話框"""
        def _on_changed():
            self._update_height_button_icon()
            self._position_bottom_right()
            self.refresh_list()
        SettingsDialog(self, self.manager, self.version, on_settings_changed=_on_changed)

    def _on_edit(self):
        selected_ids = self._get_selected_ids()
        if not selected_ids:
            messagebox.showwarning("提示", "請先選取要編輯的捷徑！", parent=self)
            return
        item_id = selected_ids[0]
        item = self.manager.get_by_id(item_id)
        if not item:
            return

        def _save_callback(updated_item: ShortcutItem):
            self.manager.update_item(
                item_id,
                name=updated_item.name,
                target_path=updated_item.target_path,
                arguments=updated_item.arguments,
                working_dir=updated_item.working_dir,
                category=updated_item.category,
                pinned=updated_item.pinned,
                enabled=updated_item.enabled
            )
            self.refresh_list()

        ShortcutEditDialog(self, item, manager=self.manager, on_save=_save_callback)

    def _on_delete(self):
        selected_ids = self._get_selected_ids()
        if not selected_ids:
            messagebox.showwarning("提示", "請先選取要刪除的捷徑！", parent=self)
            return

        if len(selected_ids) == 1:
            item = self.manager.get_by_id(selected_ids[0])
            msg = f"確定要刪除捷徑「{item.name if item else selected_ids[0]}」嗎？"
        else:
            msg = f"確定要刪除選取的 {len(selected_ids)} 個捷徑嗎？"

        if messagebox.askyesno("確認刪除", msg, parent=self):
            for item_id in selected_ids:
                self.manager.delete_item(item_id)
            self.refresh_list()

    def _on_move_up(self):
        if self.manager.sort_by_frequency:
            self.lbl_status.config(text="⚠️ 目前已啟用「依使用頻率排序」，無法手動移動。請至 [⚙️ 設定] 取消勾選。")
            return
        selected_ids = self._get_selected_ids()
        if selected_ids and self.manager.move_up(selected_ids[0]):
            self.refresh_list()
            self.tree.selection_set(selected_ids[0])
            self.tree.focus(selected_ids[0])
            self.tree.see(selected_ids[0])

    def _on_move_down(self):
        if self.manager.sort_by_frequency:
            self.lbl_status.config(text="⚠️ 目前已啟用「依使用頻率排序」，無法手動移動。請至 [⚙️ 設定] 取消勾選。")
            return
        selected_ids = self._get_selected_ids()
        if selected_ids and self.manager.move_down(selected_ids[0]):
            self.refresh_list()
            self.tree.selection_set(selected_ids[0])
            self.tree.focus(selected_ids[0])
            self.tree.see(selected_ids[0])

    def _on_launch_selected(self):
        """啟動選取的所有捷徑 (多選時依序背景啟動，每項間隔 0.3 秒 delay time)"""
        selected_ids = self._get_selected_ids()
        if not selected_ids:
            return

        # 單一項目直接啟動
        if len(selected_ids) == 1:
            item = self.manager.get_by_id(selected_ids[0])
            if item:
                ok, msg = launch_shortcut(item)
                if ok:
                    self.manager.record_launch(item.id)
                    self.refresh_list()
                else:
                    messagebox.showerror("啟動失敗", msg, parent=self)
            return

        # 多選項目：背景執行緒依序啟動 (帶 0.3 秒延遲時間)
        def _batch_worker():
            total = len(selected_ids)
            success_count = 0
            for i, item_id in enumerate(selected_ids):
                item = self.manager.get_by_id(item_id)
                if item:
                    self.after(0, lambda idx=i+1, n=item.name: self.lbl_status.config(
                        text=f"🚀 正在依序啟動 ({idx}/{total}): {n}..."
                    ))
                    ok, _ = launch_shortcut(item)
                    if ok:
                        success_count += 1
                        self.manager.record_launch(item.id)
                        self.after(0, self.refresh_list)
                
                # 若不是最後一個，等待 0.3 秒延遲時間
                if i < total - 1:
                    time.sleep(0.3)

            self.after(0, lambda: self.lbl_status.config(
                text=f"✅ 已完成批次啟動 {success_count}/{total} 個捷徑！"
            ))

        threading.Thread(target=_batch_worker, daemon=True).start()

    def show_window(self):
        """從系統列還原並定位至右下角顯示"""
        self._position_bottom_right()
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide_to_tray(self):
        """隱藏至系統匣"""
        self.withdraw()

    def _on_focus_out(self, event):
        """主視窗失去焦點事件處理 (非同步防抖檢查)"""
        # 僅在主視窗本身或內部焦點變動時觸發檢查
        if not self.manager.get_auto_hide_on_lose_focus():
            return
        # 設定 150ms 短延遲，讓焦點轉移與子視窗狀態穩定後再檢查
        self.after(150, self._check_focus_and_hide)

    def _check_focus_and_hide(self):
        """精確檢查焦點是否確實離開本程式，並具備多重防誤縮保護"""
        # 1. 若功能未開啟或視窗已隱藏，不處理
        if not self.manager.get_auto_hide_on_lose_focus():
            return
        if not self.winfo_viewable():
            return

        # 2. 防誤縮第一道：檢查是否有開啟中的子對話框 (如編輯/設定視窗、檔案選擇器等)
        try:
            for child in self.winfo_children():
                if isinstance(child, tk.Toplevel) and child.winfo_exists() and child.winfo_viewable():
                    return
        except Exception:
            pass

        # 3. 防誤縮第二道：檢查 Tkinter 內部元件焦點
        try:
            focused_widget = self.focus_get()
            if focused_widget is not None:
                # 焦點仍在主視窗或其內部元件上
                return
        except Exception:
            pass

        # 4. 防誤縮第三道：透過 Windows API 檢查當前的前景視窗 PID
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd:
                pid = wintypes.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == os.getpid():
                    # 前景視窗仍屬於本行程 (例如系統訊息框、選單等)
                    return
        except Exception:
            pass

        # 5. 確認焦點已確實切換至外部應用程式，自動隱藏至系統列
        self.hide_to_tray()