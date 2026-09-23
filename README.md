# MyShortCut - 檔案捷徑系統列常駐啟動工具

一個輕量、現代化、開機自動常駐於 Windows 右下角系統匣（System Tray）的捷徑管理工具。

---

## 🌟 核心特色

1. **系統列快捷選單**：點擊右下角圖示即時彈出捷徑選單，點選立即開啟檔案、應用程式或資料夾。
2. **零黑窗控制台 (No-Console)**：透過 `start_MyShortCut.vbs` 或打包後的 `MyShortCut.exe` 執行，完全不佔用 Windows 工作列 CMD 黑窗。
3. **開機自動啟動 (Auto-Start)**：內建 Windows 登錄檔開機自啟機制，開機後自動靜默縮至右下角系統列待命。
4. **直覺管理介面**：
   - 支援批次加入多個檔案。
   - 支援自訂捷徑名稱、分類、啟動參數、工作目錄。
   - 支援搜尋過濾、上下排序與隨時啟用/隱藏。
5. **發布與更新機制 (比照 Memo 工具)**：
   - `version.txt` 版本號控管。
   - `make_release.py` 一鍵產出 `Release/version.txt` 與 `Release/MyShortCut.zip`。
   - 預留 `updater.py` 自動比對與熱更換覆蓋機制。

---

## 🚀 啟動方式

- **方式一（日常推薦：無黑窗背景啟動）**：
  直接雙擊執行 `start_MyShortCut.vbs`。
- **方式二（開發測試）**：
  執行 `python main.py`。
- **方式三（開機自啟）**：
  在介面中勾選「🚀 開機自動啟動」即可。

---

## 📦 打包與發布

- **打包為獨立 EXE**：
  執行 `python build_exe.py`，將自動使用 PyInstaller 編譯出無黑窗的 `MyShortCut.exe`。
- **產出 Release 發布包**：
  執行 `python make_release.py`，將自動在 `Release/` 目錄產生 `MyShortCut.zip` 與 `version.txt`。