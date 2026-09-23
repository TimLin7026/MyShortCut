# -*- coding: utf-8 -*-
"""
MyShortCut - Windows 原生檔案與程式原始圖示抽取模組 (支援 Alpha 自動校正)
"""
import os
import ctypes
from ctypes import wintypes
from PIL import Image, ImageTk, ImageDraw

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
shell32 = ctypes.windll.shell32

class ICONINFO(ctypes.Structure):
    _fields_ = [
        ('fIcon', wintypes.BOOL),
        ('xHotspot', wintypes.DWORD),
        ('yHotspot', wintypes.DWORD),
        ('hbmMask', wintypes.HBITMAP),
        ('hbmColor', wintypes.HBITMAP),
    ]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD),
    ]

class SHFILEINFOW(ctypes.Structure):
    _fields_ = [
        ('hIcon', wintypes.HICON),
        ('iIcon', ctypes.c_int),
        ('dwAttributes', wintypes.DWORD),
        ('szDisplayName', wintypes.WCHAR * 260),
        ('szTypeName', wintypes.WCHAR * 80),
    ]

user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(ICONINFO)]
user32.GetIconInfo.restype = wintypes.BOOL

user32.DestroyIcon.argtypes = [wintypes.HICON]
user32.DestroyIcon.restype = wintypes.BOOL

gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL

user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC

user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int

gdi32.GetDIBits.argtypes = [
    wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
    ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT
]
gdi32.GetDIBits.restype = ctypes.c_int

SHGFI_ICON = 0x000000100
SHGFI_SMALLICON = 0x000000001
SHGFI_LARGEICON = 0x000000000

class IconExtractor:
    _cache = {}

    @classmethod
    def get_file_icon(cls, file_path: str, size: int = 20) -> Image.Image:
        """
        抽取檔案、程式或捷徑的原生官方原始圖示 (回傳 PIL.Image)
        """
        if not file_path:
            return cls._get_fallback_icon(file_path, size)

        clean_path = file_path.strip().strip('"')
        cache_key = (clean_path.lower(), size)
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        img = None
        
        # 1. 若為 .lnk 快捷方式，解析真實目標
        target_path = clean_path
        if clean_path.lower().endswith('.lnk') and os.path.exists(clean_path):
            try:
                import win32com.client
                wsh = win32com.client.Dispatch("WScript.Shell")
                sc = wsh.CreateShortcut(clean_path)
                if sc.TargetPath and os.path.exists(sc.TargetPath):
                    target_path = sc.TargetPath
            except Exception:
                pass

        # 2. 針對 .exe 程式，優先使用 ExtractIconExW 抽取原生圖示
        if target_path.lower().endswith('.exe') and os.path.exists(target_path):
            try:
                hLarge = wintypes.HICON()
                hSmall = wintypes.HICON()
                res = shell32.ExtractIconExW(target_path, 0, ctypes.byref(hLarge), ctypes.byref(hSmall), 1)
                hIcon = hLarge if size > 16 else hSmall
                if not hIcon.value:
                    hIcon = hLarge if hLarge.value else hSmall

                if hIcon.value:
                    img = cls._hicon_to_image(hIcon)
                
                if hLarge.value: user32.DestroyIcon(hLarge)
                if hSmall.value: user32.DestroyIcon(hSmall)
            except Exception:
                pass

        # 3. 針對其它檔案、資料夾或 ExtractIconEx 抽取失敗者，使用 SHGetFileInfoW
        if img is None and os.path.exists(clean_path):
            try:
                sfi = SHFILEINFOW()
                flags = SHGFI_ICON | (SHGFI_LARGEICON if size > 16 else SHGFI_SMALLICON)
                res = shell32.SHGetFileInfoW(clean_path, 0, ctypes.byref(sfi), ctypes.sizeof(sfi), flags)
                if res and sfi.hIcon:
                    img = cls._hicon_to_image(sfi.hIcon)
                    user32.DestroyIcon(sfi.hIcon)
            except Exception:
                pass

        # 4. 備援圖示
        if img is None:
            img = cls._get_fallback_icon(clean_path, size)

        # 縮放至指定尺寸
        if img.size != (size, size):
            img = img.resize((size, size), Image.Resampling.LANCZOS)

        cls._cache[cache_key] = img
        return img

    @classmethod
    def get_tk_icon(cls, file_path: str, size: int = 20):
        """回傳可用於 Tkinter Treeview 的 PhotoImage"""
        img = cls.get_file_icon(file_path, size)
        return ImageTk.PhotoImage(img)

    @staticmethod
    def _hicon_to_image(hicon) -> Image.Image:
        """將 Windows 64-bit HICON 轉換為帶 Alpha 通道的 PIL Image (含全透明校正)"""
        info = ICONINFO()
        if not user32.GetIconInfo(hicon, ctypes.byref(info)):
            return Image.new("RGBA", (16, 16), (0, 0, 0, 0))

        hdc = user32.GetDC(0)
        hbm = info.hbmColor if info.hbmColor else info.hbmMask

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)

        gdi32.GetDIBits(hdc, hbm, 0, 0, None, ctypes.byref(bmi), 0)

        w = bmi.biWidth
        h = abs(bmi.biHeight) if info.hbmColor else abs(bmi.biHeight) // 2

        bmi.biWidth = w
        bmi.biHeight = -h  # top-down DIB
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(hdc, hbm, 0, h, buf, ctypes.byref(bmi), 0)

        user32.ReleaseDC(0, hdc)
        if info.hbmColor: gdi32.DeleteObject(info.hbmColor)
        if info.hbmMask: gdi32.DeleteObject(info.hbmMask)

        img = Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1)

        # 智慧 Alpha 檢測：若所有 Alpha 通道值皆為 0 (無 Alpha 之 24-bit 點陣圖)，自動轉為不透明
        alpha_channel = img.split()[-1]
        if alpha_channel.getextrema()[1] == 0:
            r, g, b, _ = img.split()
            img = Image.merge("RGBA", (r, g, b, Image.new("L", (w, h), 255)))

        return img

    @classmethod
    def _get_fallback_icon(cls, path: str, size: int) -> Image.Image:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        ext = os.path.splitext(path)[1].lower() if path else ""
        
        if os.path.isdir(path) or path.endswith(("/", "\\")):
            draw.rounded_rectangle([1, 2, size-2, size-2], radius=3, fill=(255, 193, 7, 255))
        elif ext in [".exe", ".bat", ".cmd", ".ps1"]:
            draw.rounded_rectangle([1, 1, size-2, size-2], radius=3, fill=(33, 150, 243, 255))
        else:
            draw.rounded_rectangle([2, 1, size-3, size-2], radius=2, fill=(76, 175, 80, 255))
        return img