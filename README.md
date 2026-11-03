# LowYOutpostFinder

![Version](https://img.shields.io/badge/version-2.0.1-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tech](https://img.shields.io/badge/stack-Python%20%2B%20C11-lightgrey)
![Minecraft](https://img.shields.io/badge/minecraft%20Java-1.21.8-orange)

[中文](#中文) | [English](#english)

---

## 中文

### 目錄

- [關於](#關於)
- [功能](#功能)
- [安裝](#安裝)
- [使用方式](#使用方式)
- [授權](#授權)

### 關於

LowYOutpostFinder 是 Minecraft Java 版的低 Y 掠奪者前哨站搜尋工具, 由 Python GUI/CLI 與選用的 C11 高度估算器組成. 預設開啟簡潔的黑白介面, 讓使用者只需輸入種子碼, 設定高度門檻, 搜尋範圍及結果數量, 就能搜尋近似低 Y 前哨站.

**重要限制:** 預設模式使用實驗性的地形高度推算, 結果狀態為 `estimated_only`, **不是** Minecraft 原版已生成的真實前哨站. 目前的環狀搜尋找到指定數量後會提前停止, 雖然會依水平距離排序已找到的結果, 但**不能保證它們是全世界最近的 N 個符合條件的前哨站**. 如需確認實際生成和 Y, 請使用進階模式讀取已生成世界, 或執行原版伺服器驗證.

專案版本請以根目錄 [VERSION](VERSION) 為準. 高度估算目前僅支援 **Minecraft Java 1.21.8**; 其他版本的放置候選或存檔驗證功能依各模式實作而定.

### 功能

- 預設黑白 GUI, 支援繁體中文與 English, 右上角設定可開啟原有進階搜尋模式.
- 依種子搜尋低 Y 近似候選, 預設結構中心 **Y < -37**, 搜尋中心 **(0,0)**, 搜尋半徑 **30,000,000 方塊**, 輸出 **25 筆**.
- 首次啟動時在背景檢查並嘗試編譯 C11 高度估算器; 已編譯且通過協定檢查時會直接重用.
- 搜尋結果依搜尋中心的水平距離排序, 顯示版本, 種子, 序號, X, 估算 Y, Z, 兩種距離, 區塊座標與證據狀態, 並可匯出 CSV.
- 提供執行紀錄, 停止搜尋, 唯一結果檔名及原生掃描的診斷資料.
- 進階模式保留放置候選, 全圖掃描, 已生成世界 NBT 讀取, 原版伺服器驗證及其餘既有工具.

### 安裝

需要 **Python 3.11+** 和 Tkinter. 第一次自動編譯 C 高度估算器時, 電腦還需要 **Git, CMake, C11 編譯器以及網路連線**. 程式會下載固定 Git commit 的 MIT 授權 LowYSwampHut 原始碼並自行建置, 不會自動以管理員權限安裝系統工具, 也不會在 C 引擎失敗時偷偷退回只有 X/Z 的搜尋.

```bash
git clone https://github.com/oMiki0826o/LowYOutpostFinder.git
cd LowYOutpostFinder
python3 LowYOutpostFinder.py
```

Windows 可使用 `py LowYOutpostFinder.py`, 但目前自動編譯的原生端到端 CI 驗證主要涵蓋 macOS 與 Ubuntu. 在 macOS 上缺少編譯器時需先安裝 Xcode Command Line Tools 與 CMake; Ubuntu 則需要 Git, CMake 與 C 編譯工具. 若環境不足, GUI 會顯示原因與重新嘗試入口.

不需要另外下載 Minecraft server JAR 來使用預設的近似搜尋. 原版伺服器驗證模式另有自己的需求與授權確認流程.

### 使用方式

1. 執行 `LowYOutpostFinder.py`, 在首頁輸入 Minecraft Java 世界種子.
2. 確認 **結構中心高度低於 -37** (嚴格小於, 不是基板 Y), 調整搜尋半徑和結果數量.
3. C 引擎就緒後按下開始搜尋. 搜尋中心預設為世界原點 `(0,0)`, **不一定是實際出生點**.
4. 查看搜尋結果與執行紀錄; 程式會自動在 `results/` 建立不同名稱的 CSV, 也可以另外匯出.

CSV 使用固定英文欄位, 第一列為欄名:

```csv
version,seed,index,x,estimated_y,z,distance_from_center,distance_from_origin,chunk_x,chunk_z,status
```

`estimated_y` 為估算的結構中心 Y; `distance_from_center` 與 `distance_from_origin` 單位都是方塊. `status=estimated_only` 不代表實際生成, 不能視為 `verified_tower`.

如需命令列搜尋, 可先確保 C 引擎已完成編譯, 再執行:

```bash
python3 -m lowy_outpost_finder full-map \
  --version 1.21.8 --seed 1233211234567 \
  --height-engine estimate --strategy nearest \
  --center-x 0 --center-z 0 --max-y -37 --top 25 \
  --out estimated-nearest.csv
```

其他進階模式及限制請參考 [極簡首頁指南](docs/SIMPLE_HOME.md), [架構說明](docs/ARCHITECTURE.md) 與 [CLI 使用指南](docs/USAGE.md).

### 搜尋進度及 macOS 原生編譯

簡潔首頁會顯示依「符合條件的近似候選／目標數量」計算的進度條，
例如找到 2/25 筆表示 8%，**並非已掃描全世界 8%**。
執行紀錄會顯示已掃描的 512×512 方塊前哨站生成區域數、
找到的候選數與經過時間。原生引擎尚未回報時，介面仍定期輸出
等待下一次掃描回報的心跳，但不會虛構掃描數量。

macOS Clang 的 C11 相容性修正已納入自動編譯流程：
先確認上游固定版本的常數及斷言格式，再修補一次性建置副本，
避免重新下載時覆寫使用者手動修正。完整回歸測試可使用
`python -m pytest -q tests`（GUI 測試需顯示器或 Xvfb）。

### 授權

本專案採用 [MIT License](LICENSE). C 高度估算器會使用第三方 MIT 授權的 LowYSwampHut 原始碼, 其授權與作者資訊以原始專案為準. Minecraft 為 Mojang Studios 的作品. 本專案不包含官方 Minecraft server JAR 或世界存檔.

---

## English

### Table of Contents

- [About](#about)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [License](#license)

### About

LowYOutpostFinder searches for low-Y pillager outpost candidates in Minecraft Java Edition. It combines a Python GUI/CLI with an optional C11 terrain-height estimator. The default monochrome interface lets users enter a seed, height threshold, search radius and result count without configuring the scanning engine manually.

**Important limitation:** The default mode produces experimental terrain estimates marked `estimated_only`, **not** confirmed vanilla-generated outposts. The current centre-out ring scan stops after collecting the requested number of estimates. The returned results are sorted by horizontal distance, but **this does not prove they are the globally nearest N qualifying outposts**. To confirm actual world generation and Y, use the advanced saved-world inspection or vanilla-server verification modes.

The project version is recorded in [VERSION](VERSION). Estimated-height search currently supports **Minecraft Java 1.21.8 only**. Placement and saved-world modes have their own version constraints.

### Features

- Monochrome GUI with Traditional Chinese and English; existing advanced search modes remain accessible in the top-right settings.
- Seed-derived estimated low-Y scanning, with defaults of **structure centre Y < -37**, centre **(0,0)**, **30,000,000-block radius** and **25 results**.
- First-run background setup of the C11 estimator, with reuse of a previously built scanner after protocol validation.
- Distance-ranked results showing version, seed, index, X, estimated Y, Z, two distances, chunk coordinates and evidence status, plus CSV export.
- Execution logs, search cancellation, unique output filenames and native scan diagnostics.
- Advanced tools for placement candidates, whole-map scanning, read-only world NBT inspection, vanilla-server verification and the other existing modes.

### Installation

Requires **Python 3.11+** and Tkinter. Building the estimated-height C scanner on first launch also requires **Git, CMake, a C11 compiler and internet access**. The program fetches a pinned revision of MIT-licensed LowYSwampHut source and builds it locally. It does not install privileged system packages or silently fall back to X/Z-only search if native setup fails.

```bash
git clone https://github.com/oMiki0826o/LowYOutpostFinder.git
cd LowYOutpostFinder
python3 LowYOutpostFinder.py
```

Windows users may run `py LowYOutpostFinder.py`, but end-to-end native compilation CI currently covers macOS and Ubuntu. On macOS, install Xcode Command Line Tools and CMake if missing. Ubuntu requires Git, CMake and a C compiler toolchain. The GUI explains missing prerequisites and offers a retry action.

The default estimated-height workflow does not require a Minecraft server JAR. Vanilla-server verification has separate prerequisites and license acceptance requirements.

### Usage

1. Run `LowYOutpostFinder.py` and enter a Minecraft Java world seed.
2. Set the **structure centre Y below -37** threshold (strictly below, not base-plate Y), radius and number of results.
3. When the C engine is ready, start searching. The default search centre is world origin `(0,0)`, **not necessarily the actual spawn**.
4. Review results and logs. Each search creates a uniquely named CSV under `results/`; it can also be exported elsewhere.

The CSV has a stable English header:

```csv
version,seed,index,x,estimated_y,z,distance_from_center,distance_from_origin,chunk_x,chunk_z,status
```

`estimated_y` is the projected structure-centre Y. `distance_from_center` and `distance_from_origin` are measured in blocks. `status=estimated_only` does not imply generated-world evidence and must not be confused with `verified_tower`.

For CLI usage, build the C estimator first, then run:

```bash
python3 -m lowy_outpost_finder full-map \
  --version 1.21.8 --seed 1233211234567 \
  --height-engine estimate --strategy nearest \
  --center-x 0 --center-z 0 --max-y -37 --top 25 \
  --out estimated-nearest.csv
```

See [Simple Home](docs/SIMPLE_HOME.md), [Architecture](docs/ARCHITECTURE.md) and [CLI Usage](docs/USAGE.md) for advanced modes and limitations.

### Live progress and native build on macOS

The estimated-height home now shows a **determinate** progress bar for matched
candidates (found / requested, e.g. 2/25 = 8%). This is **not the fraction
of the world scanned**. The execution log also reports the actual number of
512×512-block outpost-placement regions scanned, matched candidate count and
elapsed seconds. If no new native event arrives, a timed heartbeat keeps
the UI responsive without inventing processed regions.

For macOS Clang, the pinned upstream C source's floating-point `_Static_assert`
is replaced only after checking the exact audited source expression and
IEEE-754 constant equivalence. This occurs in the disposable build copy,
so re-running automatic setup will not undo the portability fix.

Run `python -m pytest -q tests` (with a graphical display/Xvfb for GUI tests)
and `python scripts/run_headless_tests.py` for regression checks.

### License

This project is licensed under the [MIT License](LICENSE). The C height estimator uses third-party MIT-licensed LowYSwampHut source; upstream attribution and license terms are retained. Minecraft is a property of Mojang Studios. This repository does not bundle official Minecraft server JARs or saved worlds.
