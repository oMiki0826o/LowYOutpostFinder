# LowY Outpost Finder 專案架構重構設計

## 目標

將目前散落於專案根目錄的 Python 模組整理為正式套件，讓一般使用者只需執行根目錄唯一的 `LowYOutpostFinder.py` 即可進入圖形介面，同時維持既有搜尋、驗證、原生加速、測試及發佈能力。

本次重構也處理現有 CI 暴露的 Tkinter 執行緒與測試隔離問題，但不改寫 Minecraft 放置、幾何或世界驗證演算法。

## 使用者需求與驗收條件

- 根目錄恰好只有一個 `.py` 檔：`LowYOutpostFinder.py`。
- 直接執行 `python3 LowYOutpostFinder.py` 會進入 GUI，不要求使用者輸入子命令。
- Windows 上以相同 Python 檔作為主要入口；不再要求辨識多個啟動腳本。
- 根目錄提供 `requirements.txt`，清楚記錄執行依賴。若程式只使用 Python 標準函式庫，檔案必須明確註記而不是虛構套件。
- 開發與測試依賴若存在，放在 `requirements-dev.txt`，不得混入一般使用者依賴。
- 既有 CLI 能力保留為進階入口 `python3 -m lowy_outpost_finder ...`，GUI 不透過根目錄腳本或脆弱的工作目錄假設呼叫它。
- 所有既有合理測試保留；不得為了通過重構而放寬斷言或刪除測試。
- Python 3.11 與 3.13 的跨平台 headless 測試可執行；需要真實 Tk 的測試只在具備顯示環境的工作中執行。
- 發佈 ZIP 解壓後保留相同的單一入口與完整套件。

## 選定方案

採用標準套件目錄 `lowy_outpost_finder/`。這比在 `app/` 中修改 `sys.path` 更可靠，也比合併成單一巨型 Python 檔更容易測試與維護。

套件化要消除的具體問題是：目前約三十個平級模組依賴頂層絕對匯入、GUI 以檔案路徑啟動 `finder.py`、多處以 `__file__` 假定資源位於根目錄，以及測試直接修改 `sys.path`。本方案不新增 manager、service locator 或額外框架。

## 目標目錄

```text
LowYOutpostFinder/
├── LowYOutpostFinder.py
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── CHANGELOG.md
├── LICENSE
├── VERSION
├── SHA256SUMS.txt
├── lowy_outpost_finder/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── gui.py
│   ├── gui_model.py
│   ├── explorer_gui.py
│   └── 其餘領域模組
├── scripts/
│   ├── benchmark.py
│   ├── build_native.py
│   ├── package_release.py
│   └── 其餘維護工具
├── native/
│   └── src/
│       ├── outpost_scan.c
│       └── region_scan.c
├── examples/
│   └── seeds.example.txt
├── tests/
├── docs/
└── .github/
```

根目錄可以保留版本、授權、說明、依賴、雜湊及 Git 設定等專案中繼資料；「只有一個 `.py`」不代表把所有非 Python 專案檔案隱藏起來。

## 模組與入口設計

### GUI 入口

`LowYOutpostFinder.py` 只匯入並呼叫 `lowy_outpost_finder.gui.main()`。它保持短小，不承載商業邏輯，也不修改 `sys.path`。

GUI 的背景工作保留在線程中，但所有 Tk 物件、`tk.Variable`、widget 更新及銷毀只在建立 Tcl interpreter 的主執行緒進行。背景工作只能透過 Python queue 傳遞純資料；關閉視窗時先取消輪詢、通知 worker 停止，再由主執行緒銷毀 Tk 資源。

### CLI 入口

原 `finder.py` 的解析與執行能力移入 `lowy_outpost_finder/cli.py`。`lowy_outpost_finder/__main__.py` 呼叫 `cli.main()`，使進階使用者及自動化流程可執行：

```sh
python3 -m lowy_outpost_finder --help
```

GUI 啟動 CLI 工作時使用 `sys.executable -m lowy_outpost_finder`，不再拼接根目錄 `finder.py` 的絕對路徑。

### 匯入與資源路徑

- 套件內匯入一律使用明確相對匯入，例如 `from .versions import check_version`。
- 測試從 `lowy_outpost_finder` 匯入，不再把根目錄塞入 `sys.path` 來模擬套件。
- 原生執行檔、C 原始碼與專案根目錄以單一小型路徑模組定義；只有確實需要專案外部資源的模組依賴它。
- 執行產物仍輸出至忽略追蹤的 `bin/` 或 `.build/`，source、generated 與 release artifact 保持分離。

## 依賴策略

應用程式目前使用 Python 3.11+ 標準函式庫；Tkinter 由 Python／作業系統提供，不是可由 PyPI 安裝的相同依賴。因此：

- `requirements.txt` 以註解明確寫出「無第三方執行依賴」及 Tkinter 系統需求。
- `requirements-dev.txt` 僅在實際加入第三方開發工具時列出套件；若測試仍只使用 `unittest`，同樣以註解說明。
- Java、Minecraft server JAR 與 C 編譯器是特定功能的外部工具需求，記錄於 README，不偽裝成 pip requirements。

## 根目錄與工具整理

- 移除舊 `start_gui.py`、`start_gui.bat`、`start_gui.command`；README 統一指向 `LowYOutpostFinder.py`。
- `build.sh` 的功能合併至跨平台 `scripts/build_native.py`；不保留根目錄建置腳本。
- `src/` 更名為 `native/src/`，清楚表達其為可選原生加速器來源。
- `seeds.example.txt` 移入 `examples/`。
- `scripts/` 只放開發、建置、驗證及打包工具，不放應用程式執行模組。
- 清除未追蹤快取只限 `__pycache__` 等可重建產物；不刪除使用者資料或結果。

## 測試與 CI

### 測試分層

1. Level 1：`compileall` 驗證語法與所有匯入檔案可編譯。
2. Level 3：headless 單元測試涵蓋演算法、CLI、路徑及發佈封裝。
3. Level 4：入口、套件 CLI、GUI 與背景工作整合測試。
4. Level 5：在 Xvfb 下建立、輪詢及關閉 GUI，確認沒有 Tk 資源跨執行緒釋放。

一般 Ubuntu、Windows、macOS 矩陣只執行 headless suite。真實 Tk 測試集中在 Linux/Xvfb 工作，每個 GUI 測試程序確實結束後才進入下一個測試，避免 Tcl interpreter 留在錯誤執行緒回收。

### 重構回歸測試

- 斷言根目錄 `.py` 清單恰為 `LowYOutpostFinder.py`。
- 斷言 launcher 呼叫套件 GUI 入口。
- 以 `python -m lowy_outpost_finder --help` 驗證 CLI。
- 更新 subprocess 測試，不再尋找 `finder.py`。
- 更新發佈測試，確認 ZIP 包含 launcher、完整套件、requirements、native source，且排除 cache、秘密與 runtime 資料。
- 對 Tk worker 完成、視窗關閉與 callback 取消保留回歸測試。

## 文件與發佈

README 維持中英文主要資訊一致，並依治理模板清楚區分專案版本、Python 需求與 Minecraft 支援版本。一般使用方式首先只呈現：

```sh
python3 LowYOutpostFinder.py
```

進階 CLI 放在獨立段落。所有舊的 `finder.py`、`start_gui.py` 命令與路徑都更新為實際新入口。`CHANGELOG.md` 記錄架構變更及相容性影響；`SHA256SUMS.txt` 在最終內容穩定後重建並驗證。

發佈工具保持可重現 ZIP、UTF-8 來源檢查及解壓後內容驗證。重構本身不宣稱發布新版本、不建立 Tag 或 GitHub Release；版本調整需另行授權與確認。

## 治理規範對照

- `CORE-001`、`ENG-001`：搬移前盤點 caller、callee、路徑與測試。
- `CORE-004`：修正頂層匯入與 Tk 生命週期根因，不堆疊 `sys.path` fallback。
- `CORE-005`、`ENG-006`：只重構組織、入口及已知 CI 問題，不改世界生成演算法。
- `CORE-007`、`GIT-001`：實作與提交前檢查並保護既有工作樹。
- `ENG-002`：套件匯入方向明確，避免循環依賴。
- `ENG-003`：worker、Tk callback 與 Tcl interpreter 有完整關閉流程。
- `FMT-007`：source、runtime、generated、release artifact 分離。
- `VAL-008`、`VAL-009`：保留合理測試並執行入口、CLI、GUI、封裝回歸。
- `REL-003`、`REL-004`：依賴清單符合實際狀態，發佈 ZIP 重新開啟驗證。
- `DOC-004`：README 只保留可執行的新命令。

## 非目標與限制

- 不改變候選計算、結構判定、NBT、安全限制或結果語意。
- 不新增第三方 GUI 框架、打包器、依賴管理器或安裝程式。
- 不把 Java、Minecraft JAR、Tk 系統套件或 C 編譯器列為 pip 套件。
- 本地無顯示環境時，只能完成 headless 驗證；真實 GUI 視覺及 Linux/Xvfb 結果必須精確列為 CI 待驗證或已有證據。
- 不執行 Tag、Release 或其他正式發布動作。
