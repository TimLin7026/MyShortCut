import os
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional
from core.shortcut_manager import ShortcutManager, ShortcutItem, guess_category
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

class ShortcutEditDialog(tk.Toplevel):
    def __init__(self, parent, item: Optional[ShortcutItem] = None, manager: Optional[ShortcutManager] = None, on_save=None):
        super().__init__(parent)
        self.item = item
        self.manager = manager
        self.on_save = on_save
        self.result = None

        self.title("編輯捷徑" if item else "新增捷徑")
        self.win_w = 480
        self.win_h = 430
        self.minsize(440, 400)
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
        """將新增/編輯視窗定位於螢幕右下角安全區域，具備邊界碰撞防呆"""
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

        title_text = "✏️ 編輯捷徑設定" if self.item else "➕ 新增檔案/資料夾捷徑"
        tk.Label(container, text=title_text, font=FONT_TITLE, bg=BG_COLOR, fg=PRIMARY_COLOR).pack(anchor="w", pady=(0, 15))

        form_frame = tk.Frame(container, bg=BG_COLOR)
        form_frame.pack(fill=tk.BOTH, expand=True)
        form_frame.columnconfigure(1, weight=1)

        # 1. 捷徑名稱
        tk.Label(form_frame, text="捷徑名稱 *:", font=FONT_BOLD, bg=BG_COLOR, fg=TEXT_COLOR).grid(row=0, column=0, sticky="w", pady=6)
        self.var_name = tk.StringVar(value=self.item.name if self.item else "")
        self.ent_name = ttk.Entry(form_frame, textvariable=self.var_name, font=FONT_NORMAL)
        self.ent_name.grid(row=0, column=1, columnspan=2, sticky="we", pady=6, padx=(10, 0))

        # 2. 目標路徑 (含選檔案/選資料夾雙按鈕)
        tk.Label(form_frame, text="目標路徑 *:", font=FONT_BOLD, bg=BG_COLOR, fg=TEXT_COLOR).grid(row=1, column=0, sticky="w", pady=6)
        self.var_path = tk.StringVar(value=self.item.target_path if self.item else "")
        self.ent_path = ttk.Entry(form_frame, textvariable=self.var_path, font=FONT_NORMAL)
        self.ent_path.grid(row=1, column=1, sticky="we", pady=6, padx=(10, 5))

        # 按鈕容器 (選檔案... 與 選資料夾...)
        btn_box = tk.Frame(form_frame, bg=BG_COLOR)
        btn_box.grid(row=1, column=2, sticky="e", pady=6)
        ttk.Button(btn_box, text="選檔案...", width=9, command=self._browse_file).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(btn_box, text="選資料夾...", width=10, command=self._browse_folder).pack(side=tk.LEFT)

        # 3. 分類標籤
        tk.Label(form_frame, text="分類標籤:", font=FONT_BOLD, bg=BG_COLOR, fg=TEXT_COLOR).grid(row=2, column=0, sticky="w", pady=6)
        init_cat = guess_category(self.item.target_path) if self.item else "資料夾"
        self.var_category = tk.StringVar(value=init_cat)
        self.cbo_cat = ttk.Combobox(form_frame, textvariable=self.var_category, font=FONT_NORMAL, values=["程式", "文件", "資料夾"], state="readonly")
        self.cbo_cat.grid(row=2, column=1, columnspan=2, sticky="we", pady=6, padx=(10, 0))

        # 監聽目標路徑變更，即時自動切換分類
        self.var_path.trace_add("write", self._on_path_changed)

        # 4. 執行參數 (選填)
        tk.Label(form_frame, text="執行參數:", font=FONT_NORMAL, bg=BG_COLOR, fg=TEXT_MUTED).grid(row=3, column=0, sticky="w", pady=6)
        self.var_args = tk.StringVar(value=self.item.arguments if self.item else "")
        self.ent_args = ttk.Entry(form_frame, textvariable=self.var_args, font=FONT_NORMAL)
        self.ent_args.grid(row=3, column=1, columnspan=2, sticky="we", pady=6, padx=(10, 0))

        # 5. 工作目錄 (選填)
        tk.Label(form_frame, text="工作目錄:", font=FONT_NORMAL, bg=BG_COLOR, fg=TEXT_MUTED).grid(row=4, column=0, sticky="w", pady=6)
        self.var_workdir = tk.StringVar(value=self.item.working_dir if self.item else "")
        self.ent_workdir = ttk.Entry(form_frame, textvariable=self.var_workdir, font=FONT_NORMAL)
        self.ent_workdir.grid(row=4, column=1, sticky="we", pady=6, padx=(10, 5))
        ttk.Button(form_frame, text="選目錄...", width=10, command=self._browse_workdir).grid(row=4, column=2, sticky="e", pady=6)

        # 6. 固定置頂
        self.var_pinned = tk.BooleanVar(value=self.item.pinned if self.item else False)
        self.chk_pinned = ttk.Checkbutton(form_frame, text="📌 固定置頂 (永遠排列在清單最前方)", variable=self.var_pinned)
        self.chk_pinned.grid(row=5, column=1, columnspan=2, sticky="w", pady=6, padx=(10, 0))

        # 底部按鈕
        btn_bar = tk.Frame(container, bg=BG_COLOR)
        btn_bar.pack(fill=tk.X, pady=(15, 0))

        ttk.Button(btn_bar, text="取消", width=10, command=self.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_bar, text="儲存", width=12, command=self._save).pack(side=tk.RIGHT, padx=5)

    def _on_path_changed(self, *args):
        """路徑輸入時即時連動分類"""
        p = self.var_path.get().strip()
        if p:
            cat = guess_category(p)
            self.var_category.set(cat)

    def _get_initial_dir(self) -> Optional[str]:
        """計算瀏覽器預設開啟目錄"""
        curr = self.var_path.get().strip().strip('"').strip("'")
        if curr:
            if os.path.isdir(curr):
                return curr
            d = os.path.dirname(curr)
            if os.path.exists(d):
                return d
        workdir = self.var_workdir.get().strip().strip('"').strip("'")
        if workdir and os.path.exists(workdir):
            return workdir
        return None

    def _browse_file(self):
        """選取目標檔案/程式：預設定位在當前目錄"""
        init_dir = self._get_initial_dir()
        f = filedialog.askopenfilename(
            parent=self,
            title="選取目標檔案/程式",
            initialdir=init_dir,
            filetypes=[
                ("所有檔案與程式", "*.*"),
                ("執行檔 / 捷徑", "*.exe;*.lnk;*.bat;*.cmd;*.ps1;*.vbs"),
                ("各類文件", "*.docx;*.xlsx;*.pptx;*.pdf;*.txt;*.md;*.csv")
            ]
        )
        if f:
            f_clean = os.path.normpath(f)
            self.var_path.set(f_clean)
            if not self.var_name.get():
                base = os.path.splitext(os.path.basename(f_clean))[0]
                self.var_name.set(base)
            if not self.var_workdir.get():
                self.var_workdir.set(os.path.dirname(f_clean))
            self.var_category.set(guess_category(f_clean))

    def _browse_folder(self):
        """選取目標資料夾：預設定位在當前目錄"""
        init_dir = self._get_initial_dir()
        d = filedialog.askdirectory(
            parent=self,
            title="選取目標資料夾",
            initialdir=init_dir
        )
        if d:
            d_clean = os.path.normpath(d)
            self.var_path.set(d_clean)
            if not self.var_name.get():
                base = os.path.basename(d_clean) or d_clean
                self.var_name.set(base)
            if not self.var_workdir.get():
                self.var_workdir.set(d_clean)
            self.var_category.set("資料夾")

    def _browse_workdir(self):
        curr = self.var_workdir.get().strip().strip('"').strip("'")
        init_dir = curr if (curr and os.path.exists(curr)) else self._get_initial_dir()
        d = filedialog.askdirectory(parent=self, title="選取工作目錄", initialdir=init_dir)
        if d:
            self.var_workdir.set(os.path.normpath(d))

    def _save(self):
        name = self.var_name.get().strip()
        path = self.var_path.get().strip()
        if not name:
            messagebox.showwarning("提示", "請輸入捷徑名稱！", parent=self)
            self.ent_name.focus()
            return
        if not path:
            messagebox.showwarning("提示", "請輸入或選擇目標路徑！", parent=self)
            self.ent_path.focus()
            return

        # 防呆檢查：避免加入重複的目標路徑
        if self.manager:
            dup = self.manager.find_duplicate(path, exclude_id=self.item.id if self.item else None)
            if dup:
                messagebox.showwarning(
                    "已存在相同捷徑",
                    f"此目標路徑已存在於捷徑「{dup.name}」中！\n\n路徑：\n{path}\n\n無法重複加入相同目標路徑的捷徑。",
                    parent=self
                )
                self.ent_path.focus()
                return

        cat = self.var_category.get().strip() or guess_category(path)
        args = self.var_args.get().strip()
        workdir = self.var_workdir.get().strip()
        pinned = self.var_pinned.get()

        if self.item:
            self.item.name = name
            self.item.target_path = path
            self.item.category = cat
            self.item.arguments = args
            self.item.working_dir = workdir
            self.item.pinned = pinned
            self.result = self.item
        else:
            self.result = ShortcutItem(
                name=name,
                target_path=path,
                arguments=args,
                working_dir=workdir,
                category=cat,
                pinned=pinned
            )

        if self.on_save:
            self.on_save(self.result)
        self.destroy()