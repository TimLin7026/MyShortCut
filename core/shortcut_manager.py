# -*- coding: utf-8 -*-
"""
MyShortCut - 捷徑資料模型與管理核心模組 (強化資料夾自動分類與使用頻率統計)
"""
import os
import sys
import json
import uuid
import time
from typing import List, Dict, Optional

def get_app_dir() -> str:
    """取得應用程式根目錄 (相容 PyInstaller --onefile 模式)"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 程式副檔名定義
PROGRAM_EXTS = {
    ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".msi", ".lnk",
    ".com", ".py", ".jar", ".appx"
}

def guess_category(target_path: str) -> str:
    """依據檔案路徑智慧推斷分類 (程式 | 文件 | 資料夾)"""
    if not target_path:
        return "資料夾"
    
    clean_path = target_path.strip().strip('"').strip("'")
    clean_lower = clean_path.lower()
    
    # 網址或系統協定
    if clean_lower.startswith(("http://", "https://")):
        return "文件"
    if clean_lower.startswith(("ms-settings:", "shell:")):
        return "程式"

    # 目錄/資料夾判定：是目錄、以斜線結尾、或是無副檔名的路徑 (如 D:\Document\DSC\月會)
    ext = os.path.splitext(clean_lower)[1]
    if os.path.isdir(clean_path) or clean_lower.endswith(("\\", "/")) or ext == "":
        return "資料夾"

    if ext in PROGRAM_EXTS:
        return "程式"
    return "文件"


class ShortcutItem:
    def __init__(
        self,
        name: str,
        target_path: str,
        arguments: str = "",
        working_dir: str = "",
        item_id: str = None,
        category: str = "",
        enabled: bool = True,
        pinned: bool = False,
        order: int = 0,
        launch_count: int = 0,
        last_launched_at: str = ""
    ):
        self.id = item_id or str(uuid.uuid4())[:8]
        self.name = name.strip()
        self.target_path = target_path.strip()
        self.arguments = arguments.strip()
        self.working_dir = working_dir.strip()
        # 自動智慧推斷分類
        self.category = category.strip() or guess_category(self.target_path)
        self.enabled = enabled
        self.pinned = pinned
        self.order = order
        self.launch_count = launch_count
        self.last_launched_at = last_launched_at

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "target_path": self.target_path,
            "arguments": self.arguments,
            "working_dir": self.working_dir,
            "category": self.category,
            "enabled": self.enabled,
            "pinned": self.pinned,
            "order": self.order,
            "launch_count": self.launch_count,
            "last_launched_at": self.last_launched_at
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ShortcutItem":
        target = data.get("target_path", "")
        cat = data.get("category", "")
        # 自動校正資料夾分類與舊版常用分類
        clean_target = target.strip().strip('"').strip("'")
        ext = os.path.splitext(clean_target.lower())[1]
        if os.path.isdir(clean_target) or ext == "" or cat in ["常用", "", None]:
            cat = guess_category(clean_target)

        return cls(
            name=data.get("name", ""),
            target_path=target,
            arguments=data.get("arguments", ""),
            working_dir=data.get("working_dir", ""),
            item_id=data.get("id"),
            category=cat,
            enabled=data.get("enabled", True),
            pinned=data.get("pinned", False),
            order=data.get("order", 0),
            launch_count=data.get("launch_count", 0),
            last_launched_at=data.get("last_launched_at", "")
        )

    def exists(self) -> bool:
        if not self.target_path:
            return False
        if self.target_path.startswith(("http://", "https://", "ms-settings:", "shell:")):
            return True
        return os.path.exists(self.target_path)


class ShortcutManager:
    def __init__(self, data_file: str = None):
        if data_file is None:
            base_dir = get_app_dir()
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            data_file = os.path.join(data_dir, "shortcuts.json")
        self.data_file = data_file
        self.items: List[ShortcutItem] = []
        self.sort_by_frequency: bool = False
        self.window_height_mode: str = "half"
        self.auto_hide_on_lose_focus: bool = True
        self.open_folder_in_tab: bool = True
        self.load()

    def load(self):
        """從 JSON 檔案載入捷徑清單與設定"""
        if not os.path.exists(self.data_file):
            self.items = []
            return

        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = data.get("config", {})
                self.sort_by_frequency = config.get("sort_by_frequency", False)
                self.window_height_mode = config.get("window_height_mode", "half")
                self.auto_hide_on_lose_focus = config.get("auto_hide_on_lose_focus", True)
                self.open_folder_in_tab = config.get("open_folder_in_tab", True)
                
                raw_items = data.get("shortcuts", [])
                self.items = [ShortcutItem.from_dict(item) for item in raw_items]
                self._apply_sorting()
        except Exception as e:
            print(f"[ERROR] 載入捷徑清單失敗: {e}")
            self.items = []

    def save(self):
        """將捷徑清單與設定儲存至 JSON 檔案"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            data = {
                "version": "1.2",
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "config": {
                    "sort_by_frequency": self.sort_by_frequency,
                    "window_height_mode": self.window_height_mode,
                    "auto_hide_on_lose_focus": self.auto_hide_on_lose_focus,
                    "open_folder_in_tab": self.open_folder_in_tab
                },
                "shortcuts": [item.to_dict() for item in self.items]
            }
            temp_file = self.data_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if os.path.exists(self.data_file):
                os.remove(self.data_file)
            os.rename(temp_file, self.data_file)
        except Exception as e:
            print(f"[ERROR] 儲存捷徑清單失敗: {e}")

    def _apply_sorting(self):
        """排序：置頂項目 (pinned=True) 永遠優先排在最前"""
        if self.sort_by_frequency:
            self.items.sort(key=lambda x: (0 if x.pinned else 1, -x.launch_count, x.order))
        else:
            self.items.sort(key=lambda x: (0 if x.pinned else 1, x.order))

    def set_sort_by_frequency(self, enabled: bool):
        self.sort_by_frequency = enabled
        self._apply_sorting()
        self.save()

    def set_window_height_mode(self, mode: str):
        if mode in ["half", "full"]:
            self.window_height_mode = mode
            self.save()

    def get_window_height_mode(self) -> str:
        return getattr(self, "window_height_mode", "half")

    def set_auto_hide_on_lose_focus(self, enabled: bool):
        self.auto_hide_on_lose_focus = enabled
        self.save()

    def get_auto_hide_on_lose_focus(self) -> bool:
        return getattr(self, "auto_hide_on_lose_focus", True)

    def set_open_folder_in_tab(self, enabled: bool):
        self.open_folder_in_tab = enabled
        self.save()

    def get_open_folder_in_tab(self) -> bool:
        return getattr(self, "open_folder_in_tab", True)

    def record_launch(self, item_id: str):
        item = self.get_by_id(item_id)
        if item:
            item.launch_count += 1
            item.last_launched_at = time.strftime("%Y-%m-%d %H:%M:%S")
            self._apply_sorting()
            self.save()

    def toggle_pin(self, item_id: str) -> bool:
        """切換置頂狀態"""
        item = self.get_by_id(item_id)
        if not item:
            return False
        item.pinned = not item.pinned
        self._apply_sorting()
        self._reindex_order()
        self.save()
        return True

    def get_all(self) -> List[ShortcutItem]:
        self._apply_sorting()
        return list(self.items)

    def get_enabled(self) -> List[ShortcutItem]:
        self._apply_sorting()
        return [item for item in self.items if item.enabled]

    @staticmethod
    def _normalize_path(path: str) -> str:
        """標準化路徑以進行精準重複比對 (消除大小寫與斜線差異)"""
        if not path:
            return ""
        clean = path.strip().strip('"').strip("'")
        if clean.startswith(("http://", "https://", "ms-settings:", "shell:")):
            return clean.lower()
        return os.path.normcase(os.path.normpath(clean))

    def find_duplicate(self, target_path: str, exclude_id: Optional[str] = None) -> Optional[ShortcutItem]:
        """尋找是否已存在相同目標路徑的捷徑 (可排除自身 ID)"""
        norm_target = self._normalize_path(target_path)
        if not norm_target:
            return None
        for item in self.items:
            if exclude_id and item.id == exclude_id:
                continue
            if self._normalize_path(item.target_path) == norm_target:
                return item
        return None

    def get_by_id(self, item_id: str) -> Optional[ShortcutItem]:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def add_item(self, item: ShortcutItem) -> ShortcutItem:
        if not item.order:
            item.order = len(self.items)
        self.items.append(item)
        self._apply_sorting()
        self.save()
        return item

    def update_item(self, item_id: str, **kwargs) -> bool:
        item = self.get_by_id(item_id)
        if not item:
            return False
        for k, v in kwargs.items():
            if hasattr(item, k):
                setattr(item, k, v)
        self._apply_sorting()
        self.save()
        return True

    def delete_item(self, item_id: str) -> bool:
        item = self.get_by_id(item_id)
        if not item:
            return False
        self.items.remove(item)
        self._reindex_order()
        self.save()
        return True

    def move_up(self, item_id: str) -> bool:
        idx = next((i for i, x in enumerate(self.items) if x.id == item_id), None)
        if idx is None or idx == 0:
            return False
        # 非置頂項目不能越界移動到置頂項目上方
        if self.items[idx - 1].pinned and not self.items[idx].pinned:
            return False
        self.items[idx], self.items[idx - 1] = self.items[idx - 1], self.items[idx]
        self._reindex_order()
        self.save()
        return True

    def move_down(self, item_id: str) -> bool:
        idx = next((i for i, x in enumerate(self.items) if x.id == item_id), None)
        if idx is None or idx >= len(self.items) - 1:
            return False
        # 置頂項目不能越界移動到非置頂項目下方
        if self.items[idx].pinned and not self.items[idx + 1].pinned:
            return False
        self.items[idx], self.items[idx + 1] = self.items[idx + 1], self.items[idx]
        self._reindex_order()
        self.save()
        return True

    def _reindex_order(self):
        for i, item in enumerate(self.items):
            item.order = i