# LowY Outpost Finder

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tech](https://img.shields.io/badge/stack-Python%203.11%2B-lightgrey)
![Minecraft](https://img.shields.io/badge/Minecraft%20Java-1.21.8-orange)

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

LowY Outpost Finder 是一個 Minecraft Java 版低高度掠奪者前哨站查找工具. 它先從世界種子計算前哨站候選座標, 再依候選位置到世界原點 `(0, 0)` 的距離排序. 使用同版本伺服器驗證時, 工具會逐一生成候選區塊, 讀取儲存於 Anvil NBT 的實際結構包圍盒, 並在找到 `structure_center_y < -37` 的最近前哨站後停止.

這個門檻用於尋找適合在低高度規劃不祥之瓶農場的位置. 它不保證特定農場設計的產量, 也不把候選座標或近似地形高度當成已生成的前哨站.

### 功能

- 從種子精確計算前哨站 placement 候選座標, 並套用村莊排除與 legacy frequency 規則.
- 依候選位置到 `(0, 0)` 的水平距離排序, 優先檢查最近位置.
- 從已生成世界或臨時伺服器世界讀取實際前哨站 NBT 結構資料.
- 輸出 `structure_min_y`, `structure_max_y`, `structure_center_y` 與 `distance_sq`.
- 預設找到第一個 `structure_center_y < -37` 的已驗證塔樓後停止, 並清除本工具新增的 force-load ticket.
- 明確區分 `placement_candidate`, `estimated_only`, `verified_tower` 與未生成狀態.

### 安裝

需求:

- Python 3.11 或更新版本.
- Minecraft Java 1.21.8 實際驗證需要 Java 21 與可信任的同版本 `server.jar`.
- 使用伺服器驗證前, 必須自行閱讀並接受 [Minecraft EULA](https://www.minecraft.net/eula).

```bash
git clone https://github.com/oMiki0826o/LowYOutpostFinder.git
cd LowYOutpostFinder
python3 finder.py --help
```

專案核心只使用 Python 標準函式庫. 可選的 C 地形近似後端需要 CMake 與 C 編譯器, 但不是近原點實際驗證流程的必要條件.

### 使用方式

只靠種子輸出 placement 候選, 不生成世界, 也不提供最終 Y:

```bash
python3 finder.py candidates \
  --version 1.21.8 \
  --seed 123 \
  --radius 8192 \
  --out candidates.csv
```

使用可信任的 1.21.8 伺服器 JAR 建立隔離的臨時世界, 依距離逐一驗證, 並在結構中心低於 `-37` 時停止:

```bash
python3 finder.py seed-vanilla \
  --version 1.21.8 \
  --seed 123 \
  --server-jar /path/to/server.jar \
  --java java \
  --eula-accepted \
  --radius 8192 \
  --limit 50 \
  --center-y-below -37 \
  --out verified.csv
```

搜尋會另外保留 audit CSV, 用來辨識已確認塔樓, 無結構, 未生成, 逾時或資料錯誤. `--limit` 只限制本次檢查的候選數量, 沒有命中不代表整個世界不存在符合條件的前哨站.

啟動圖形介面:

```bash
python3 start_gui.py
```

完整架構, 驗證證據與精確性邊界請參閱 [架構說明](docs/ARCHITECTURE.md), [驗證紀錄](docs/VALIDATION.md) 與 [精確種子引擎限制](docs/EXACT_SEED_ENGINE.md).

### 授權

本專案採用 MIT License 授權, 詳見 [LICENSE](./LICENSE).

Minecraft 是 Mojang Studios 的商標與作品. 本專案不是 Mojang 官方產品, 也不包含 Minecraft 伺服器 JAR 或第三方 LowYSwampHut 原始碼.

---

## English

### Table of Contents

- [About](#about)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [License](#license)

### About

LowY Outpost Finder locates low-altitude pillager outposts for Minecraft Java Edition. It derives placement candidates from a world seed, orders them by horizontal distance from `(0, 0)`, and can verify them one at a time with a matching server. Verified runs read the persisted Anvil NBT structure bounds and stop at the nearest outpost whose `structure_center_y` is below `-37`.

The threshold is intended to help plan low-altitude ominous bottle farms. It does not guarantee the output of a particular farm design, and the program never presents a placement candidate or an approximate terrain value as a generated outpost.

### Features

- Derives outpost placement candidates from a seed with village exclusion and legacy frequency checks.
- Orders candidates by horizontal distance from `(0, 0)` so the nearest locations are checked first.
- Reads actual outpost structure data from generated saves or an isolated temporary server world.
- Exports `structure_min_y`, `structure_max_y`, `structure_center_y`, and `distance_sq`.
- Stops after the first verified tower below the configured center threshold and releases force-load tickets created by the tool.
- Keeps `placement_candidate`, `estimated_only`, `verified_tower`, and incomplete states distinct.

### Installation

Requirements:

- Python 3.11 or newer.
- Minecraft Java 1.21.8 verification requires Java 21 and a trusted matching `server.jar`.
- Read and accept the [Minecraft EULA](https://www.minecraft.net/eula) before using server verification.

```bash
git clone https://github.com/oMiki0826o/LowYOutpostFinder.git
cd LowYOutpostFinder
python3 finder.py --help
```

The core application uses only the Python standard library. The optional approximate C terrain backend requires CMake and a C compiler, but it is not required for nearest-origin server verification.

### Usage

Export seed-derived placement candidates without generating a world or claiming a final Y coordinate:

```bash
python3 finder.py candidates \
  --version 1.21.8 \
  --seed 123 \
  --radius 8192 \
  --out candidates.csv
```

Create an isolated temporary world with a trusted 1.21.8 server JAR, verify candidates in distance order, and stop below center Y `-37`:

```bash
python3 finder.py seed-vanilla \
  --version 1.21.8 \
  --seed 123 \
  --server-jar /path/to/server.jar \
  --java java \
  --eula-accepted \
  --radius 8192 \
  --limit 50 \
  --center-y-below -37 \
  --out verified.csv
```

An audit CSV records confirmed towers, absent structures, incomplete chunks, timeouts, and invalid data. `--limit` bounds only the candidates checked in that run. No match does not prove that the world contains no eligible outpost.

Launch the graphical interface:

```bash
python3 start_gui.py
```

See [Architecture](docs/ARCHITECTURE.md), [Validation](docs/VALIDATION.md), and [Exact seed engine limitations](docs/EXACT_SEED_ENGINE.md) for implementation details and evidence boundaries.

### License

This project is licensed under the MIT License, see [LICENSE](./LICENSE).

Minecraft is a trademark and product of Mojang Studios. This project is not an official Mojang product and does not include a Minecraft server JAR or third-party LowYSwampHut source code.
