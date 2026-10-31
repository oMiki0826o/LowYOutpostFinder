# LowYOutpostFinder

![Version](https://img.shields.io/badge/version-2.0.1-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Stack](https://img.shields.io/badge/stack-Python%20%2B%20C11-lightgrey)
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

LowYOutpostFinder 是供 Minecraft Java 版世界種子研究使用的掠奪者前哨站工具. 它提供 GUI 與 CLI, 可計算結構放置候選, 掃描已儲存世界的 NBT 證據, 並為 Java 1.21.8 提供選用的低 Y 地形估算掃描.

本專案明確區分證據等級. `placement_candidate` 只證明結構放置公式的 X/Z 候選. `estimated_only` 是實驗性種子地形估算, 不是原版等效的真實高度. 只有從已生成世界資料讀取的 `verified_tower` 才能確認塔樓存在.

### 功能

- 依 Minecraft Java 結構放置規則搜尋掠奪者前哨站的 X/Z 候選.
- 提供繁體中文與 English Tk GUI, 也支援可自動化的 CLI.
- 以中心向外的 strict-nearest 模式排序結果, 收到指定數量的估算候選後停止.
- 使用選用 C11 原生掃描器進行 Java 1.21.8 的低 Y 估算, 支援工作者數設定與可續跑掃描.
- 唯讀檢查已生成世界的 NBT, 以 `verified_tower` 回報可由存檔證據確認的塔樓.
- 內建 1.21.8 前哨站資產雜湊, 可選擇以相同版本 JAR 做維護性驗證, 正常掃描不依賴 JAR.

### 安裝

從原始碼執行需要 Python 3.11 以上與 Tkinter. 專案沒有第三方 Python 執行期依賴.

```bash
git clone https://github.com/oMiki0826o/LowYOutpostFinder.git
cd LowYOutpostFinder
python3 LowYOutpostFinder.py
```

Windows 可以使用:

```powershell
py LowYOutpostFinder.py
```

原生低 Y 估算器是選用功能. 它需要 C11 編譯器, CMake, 以及使用者提供的 LowYSwampHut 原始碼封存檔:

```bash
python3 scripts/build_native.py estimate /path/to/LowYSwampHut-main.tar.gz
```

### 使用方式

啟動 GUI 後選擇模式, Java 版本與種子即可開始. 下列是常用 CLI 範例:

```bash
# 搜尋不生成區塊的前哨站放置候選.
python3 -m lowy_outpost_finder candidates \
  --version 1.21.8 --seed 1233211234567 --radius 8192 --out candidates.csv

# 以 0,0 為中心向外尋找最近的低 Y 估算候選.
# 需要先建置 bin/outpost_estimate. threads=0 代表自動選擇工作者數.
python3 -m lowy_outpost_finder full-map \
  --version 1.21.8 --seed 1233211234567 \
  --height-engine estimate --strategy nearest --center-x 0 --center-z 0 \
  --max-y -37 --top 10 --threads 0 --out estimated-nearest.csv

# 唯讀掃描既有世界存檔中的已生成前哨站證據.
python3 -m lowy_outpost_finder world \
  --world /path/to/world-copy --max-y 0 --out saved-outposts.csv

# 可選. 驗證內建 1.21.8 前哨站資產雜湊.
python3 scripts/verify_outpost_assets.py /path/to/server-1.21.8.jar
```

在上述 strict-nearest 範例中, `--max-y -37` 比較的是瞭望塔箱子層的結構中心. 前哨站的自然刷怪範圍還有垂直延伸, 不應把它誤讀為每一個刷怪方塊都在 Y < -37.

### 授權

本專案採用 [MIT License](./LICENSE). Minecraft 是 Mojang Studios 的作品. 本專案不包含官方 server JAR, 世界存檔或 LowYSwampHut 原始碼.

---

## English

### Table of Contents

- [About](#about)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [License](#license)

### About

LowYOutpostFinder is a pillager outpost research tool for Minecraft Java world seeds. It provides a GUI and CLI for structural placement candidates, saved-world NBT evidence, and an optional low-Y terrain estimate scanner for Java 1.21.8.

The project keeps its evidence levels explicit. `placement_candidate` proves only an X/Z candidate under the structure placement formula. `estimated_only` is an experimental seed-only terrain estimate, not a vanilla-equivalent actual height. Only `verified_tower`, read from generated world data, confirms that a tower exists.

### Features

- Search pillager outpost X/Z candidates from Minecraft Java structure placement rules.
- Use a bilingual Traditional Chinese and English Tk GUI, or automate the CLI.
- Rank candidates with a centre-out strict-nearest scan and stop after the requested estimate count is found.
- Run optional C11 native Java 1.21.8 low-Y estimates with configurable workers and resumable scans.
- Inspect generated-world NBT read-only and report saved-world tower evidence as `verified_tower`.
- Pin hashes for the 1.21.8 outpost assets. A matching JAR is optional for maintenance verification and is not required for ordinary scans.

### Installation

Running from source requires Python 3.11 or newer and Tkinter. The project has no third-party Python runtime dependencies.

```bash
git clone https://github.com/oMiki0826o/LowYOutpostFinder.git
cd LowYOutpostFinder
python3 LowYOutpostFinder.py
```

On Windows:

```powershell
py LowYOutpostFinder.py
```

The native low-Y estimator is optional. It needs a C11 compiler, CMake, and a user-supplied LowYSwampHut source archive:

```bash
python3 scripts/build_native.py estimate /path/to/LowYSwampHut-main.tar.gz
```

### Usage

Open the GUI, choose a mode, Java version, and seed. Common CLI examples:

```bash
# Search placement candidates without generating chunks.
python3 -m lowy_outpost_finder candidates \
  --version 1.21.8 --seed 1233211234567 --radius 8192 --out candidates.csv

# Search outward from 0,0 for the nearest low-Y estimated candidates.
# Build bin/outpost_estimate first. threads=0 selects worker count automatically.
python3 -m lowy_outpost_finder full-map \
  --version 1.21.8 --seed 1233211234567 \
  --height-engine estimate --strategy nearest --center-x 0 --center-z 0 \
  --max-y -37 --top 10 --threads 0 --out estimated-nearest.csv

# Read-only inspection of generated outpost evidence in an existing world copy.
python3 -m lowy_outpost_finder world \
  --world /path/to/world-copy --max-y 0 --out saved-outposts.csv

# Optional. Verify the pinned 1.21.8 outpost asset hashes.
python3 scripts/verify_outpost_assets.py /path/to/server-1.21.8.jar
```

In the strict-nearest example above, `--max-y -37` compares the watchtower chest-floor structure centre. The natural outpost spawning volume extends vertically, so this does not mean every spawnable block is below Y < -37.

### License

This project is licensed under the [MIT License](./LICENSE). Minecraft is a property of Mojang Studios. This project does not bundle official server JARs, worlds, or LowYSwampHut source code.
