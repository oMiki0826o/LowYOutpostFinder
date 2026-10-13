# LowY Outpost Finder

**v2.0.1 全圖搜尋／A/B 工程版**：原版存檔高度驗證（A）及不生成區塊的起始模板幾何（B）。**B 尚不能單靠種子算出精確 Y**。

![Version](https://img.shields.io/badge/version-2.0.1-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/Python-3.11%2B-lightgrey)
![Minecraft](https://img.shields.io/badge/Minecraft_Java-1.21.8_Example-orange)

[繁體中文](#繁體中文) | [English](#english)

---

## 繁體中文

LowY Outpost Finder 是一款 **Minecraft Java 版掠奪者前哨站研究工具**。它能從世界種子列出可能生成的前哨站位置，或在你提供真實世界存檔、同版本原版伺服器的情況下確認塔樓高度。適合研究低高度前哨站及不祥之瓶農場選址。

**必須區分候選、近似與確認：**

| 結果 | 可以確認的內容 |
| --- | --- |
| `placement_candidate` | 符合結構候選放置公式；不代表前哨站確定存在，沒有 Y |
| `estimated_only` | 外部 C 核心推算的 **1.21.8 試驗性高度**，未通過原版等效驗證 |
| `verified_tower` | 從同版已生成並儲存的世界 NBT 確認前哨站基板與瞭望塔 |

目前**尚不能不生成完整區塊、只靠種子精確求出所有前哨站的 Y**。`structure_center_y` 是結構包圍盒中心，不等於最低可刷怪高度。查找距原點最近的合格前哨站，亦不等於查找全世界最低高度。

### 安裝

需要 **Python 3.11 以上**。桌面介面需要 Tkinter。只掃描候選位置不需要 Java 或外部 C 函式庫；原版 1.21.8 驗證另需 Java 21、可信任的同版本 `server.jar`，以及自行閱讀並同意 Minecraft EULA。

```sh
git clone https://github.com/oMiki0826o/LowYOutpostFinder.git
cd LowYOutpostFinder
python3 start_gui.py
```

Windows 可用 `py start_gui.py` 或雙擊 `start_gui.bat`，macOS 可用 `start_gui.command`。如果使用本次修復 ZIP，請直接解壓縮後開啟含 `finder.py` 的資料夾；此 ZIP 並未自動更新 GitHub main。

### v2.0.1：不生成區塊的全圖搜尋

本版新增 **X/Z ±29,999,984 方塊全世界範圍**的種子候選搜尋。搜尋的是**前哨站結構放置嘗試點**，而不是已確認生成的結構或塔樓 Y。一般使用者應先選快速「全圖最近候選」，該模式利用每個放置網格的最小可能距離，證明輸出的前 N 筆是**整個指定區域內最接近中心的放置候選**，無須走訪數十億個不可能更近的網格，也無須生成區塊。

```sh
# 全世界快速找最近 100 個放置候選，通常不必安裝 C 或 Java
python3 finder.py full-map --version 1.21.8 --seed 123 \
  --strategy nearest --top 100 --out results/nearest.csv

# 全世界逐格盤點（可能耗時很久，單工作、分批、可中斷續跑）
python3 scripts/build_region_scan.py
python3 finder.py full-map --version 1.21.8 --seed 123 \
  --strategy exhaustive --engine auto --batch-regions 500000 \
  --cpu-rest-ms 150 --top 100 --out results/exhaustive.csv

# 使用**相同的**輸出檔案及查詢參數繼續中斷前的掃描
python3 finder.py full-map --version 1.21.8 --seed 123 \
  --strategy exhaustive --resume --engine auto \
  --out results/exhaustive.csv
```

`nearest.csv` 與 `exhaustive.csv` 只保留最近的 N 筆，另有 `.state.json` 明確記錄證明或完成狀態；逐格模式沒有跑完時會顯示 `incomplete`，**不能宣稱已盤點全世界**。低記憶體需求來自有限筆數保留及單工作執行，不代表逐格搜索的總 CPU 工作量小。

在 GUI 選擇「**全圖候選（免生成）**」，可切換 `nearest`／`exhaustive`、CPU 休息時間、編譯過的原生掃描器以及逐格續跑。完整範例與限制見 [全圖搜尋教學](docs/FULL_MAP.md)。

### v2.0.0 雙路線重點

- **A（原版驗證）**：可自訂搜尋中心、分批 `--offset`、保存逐筆稽核進度、依已確認基板／塔樓 Y 排序，輸出範圍完整性 JSON。RCON 驗證會實際生成區塊。
- **B（純種子可驗證部分）**：新增 `seed-geometry`，使用同版本 Minecraft 資源 JAR 精確計算 Jigsaw 基板旋轉及高度圖取樣 X/Z，不需要生成區塊，但**不計算原版 Noise／Biome／Jigsaw 的最終 Y**。
- **限制**：未完成跨版本完整純種子精確 Y、原版實際高度端到端對拍；不應把近似地表高度或 geometry 視為確認塔樓。

詳見 [A/B 雙路線說明與操作範例](docs/ROUTES_AB.md)。 另外參閱 [v2 實際測試紀錄與限制](docs/VALIDATION_V2.md)。

原版 JAR 與 Java 版本預檢（**不啟動**伺服器、不接受 EULA）：

```sh
python3 finder.py server-check --version 1.21.8 \
  --server-jar /path/to/server.jar --java java --out server-check.json
```

GUI 可直接顯示原版候選逐筆驗證進度（來自實際 `[已檢查/候選數]` 訊息），而非虛構百分比。

### GUI 快速開始

1. 選擇「**種子候選**」，版號 `1.21.8`、種子 `123`、半徑 `8192`，按「開始搜尋」。此模式只輸出候選位置。
2. 選擇「**已生成世界**」，指定含 `level.dat` 與 `region/` 的離線世界副本，便能讀取已保存的前哨站高度。
3. 選擇「**種子原版實測**」，提供相容 Java、所選版本的官方伺服器 JAR；自行閱讀並同意 EULA 後才勾選。此模式會實際建立暫存世界並生成區塊。
4. 在 GUI 上可以分別指定「**最高 Y**」（基板 Y 上限，含等號）和「**完整結構中心 Y**」（嚴格小於）。兩項都符合時才提早停止驗證。
5. 「**搜尋結果／執行紀錄**」分頁能查看 CSV 結果及執行訊息；成功時自動收合搜尋設定，仍可按「展開搜尋設定」還原。點「**使用教學**」或按 F1 可查看內建指南。Ctrl+Enter 可以開始搜尋。

### 命令列範例

純種子 Jigsaw 起始幾何（需同版本 `server.jar`，不生成世界）：

```sh
python3 finder.py seed-geometry --version 1.21.8 --seed 123 --radius 8192 \
  --center-x -1024 --center-z 2048 --game-jar /path/to/server.jar --out geometry.csv
```

`geometry.csv` 無任何已確認 Y。要自行尋找其他地點，`candidates` 與 `seed-vanilla` 亦支援 `--center-x`、`--center-z`。正式驗證可選 `--sort-by base-y`、`--summary`、`--checkpoint`；搜尋分頁可用 `--offset`。

只列候選（快速，不生成世界）：

```sh
python3 finder.py candidates --version 1.21.8 --seed 123 --radius 8192 --out candidates.csv
```

已有離線世界存檔（唯讀）：

```sh
python3 finder.py world --world /path/to/world-copy --max-y 0 --out saved-outposts.csv
```

建立臨時原版世界、確認塔樓高度（**僅在自行接受 EULA 後**）：

```sh
python3 finder.py seed-vanilla --version 1.21.8 --seed 123 \
  --server-jar /path/to/server.jar --java java --eula-accepted \
  --radius 8192 --limit 10 --center-y-below -37 --max-y 0 \
  --out verified.csv
```

同時輸出 `verified-audit.csv`，顯示其他候選的核對狀態。`--limit` 只限制已檢查的筆數；沒有命中不能證明整個世界沒有符合條件的前哨站。

完整的雙語介面教學與錯誤處理請參考 [使用教學](docs/USAGE.md)。原理與實際限制另見 [架構說明](docs/ARCHITECTURE.md)、[精確引擎限制](docs/EXACT_SEED_ENGINE.md)、[驗證紀錄](docs/VALIDATION.md)。

### 授權

本專案採用 [MIT 授權](LICENSE)。Minecraft 屬於 Mojang Studios；本專案非官方產品，且 ZIP 不包含官方 Minecraft 伺服器、世界檔案或 LowYSwampHut 原始碼。

---

## English

LowY Outpost Finder is a **Minecraft Java Edition pillager outpost research tool**. It lists seed-derived placement candidates and, when provided with a generated world or a matching vanilla server, reads saved outpost tower heights. It is intended for investigating low-altitude outposts and ominous bottle farm locations.

**Confidence levels are different:**

| Classification | Evidence |
| --- | --- |
| `placement_candidate` | Placement formula only; no structure or Y is proven |
| `estimated_only` | Experimental 1.21.8 approximation from an external C core; not vanilla-equivalent |
| `verified_tower` | A watchtower and base plate identified in saved, generated Minecraft NBT |

The tool **cannot yet derive exact outpost Y solely from a seed without generating chunks**. `structure_center_y` refers to the bounding-box center, not the lowest valid mob spawn altitude. Finding the nearest passing outpost is not finding the world's globally lowest-Y outpost.

### Install

Requires **Python 3.11+** and Tkinter for the GUI. Placement scanning needs no Java or native tools. Minecraft 1.21.8 vanilla verification requires Java 21, a trusted matching `server.jar`, and your own acceptance of the Minecraft EULA.

```sh
git clone https://github.com/oMiki0826o/LowYOutpostFinder.git
cd LowYOutpostFinder
python3 start_gui.py --lang en-US
```

On Windows use `py start_gui.py` or `start_gui.bat`; on macOS use `start_gui.command`. If using this fixed ZIP, open the extracted project directory containing `finder.py`; this package does not modify GitHub main.

### v2.0.0 A/B workflows

Route A validates saved Minecraft structures after generating candidate chunks in a matching original server. A checkpoint CSV records examined candidates and a JSON summary distinguishes sampled Y rankings from an exhaustive finite-region minimum. Route B (`seed-geometry`) computes placement and rotated start-template sampling X/Z without generating chunks, **not final biome, WORLD_SURFACE_WG Y or tower Y**. See [A/B workflow guide](docs/ROUTES_AB.md) for commands, evidence statuses, and remaining limitations.

### Quick GUI walkthrough

1. Choose **Seed candidates**, version `1.21.8`, seed `123`, radius `8192`, then **Start search**. This yields placement candidates only.
2. Choose **Generated worlds** and browse to an offline world copy containing `level.dat` and `region/` to read persisted tower heights.
3. Choose **Seed-to-vanilla verification**, provide compatible Java and a matching official server JAR. Check EULA consent only after reading and accepting it. This mode generates temporary chunks.
4. **Maximum Y** filters the base-plate Y inclusively, while **Structure center Y** filters with strict less-than. Both configured thresholds must pass before early stopping.
5. Use **Results / Logs** tabs to inspect output. On success, the search form collapses for extra result space; expand it again at any time. Press F1 for the in-app guide or Ctrl+Enter to start.

### Command line

Placement candidates only (no world generation):

```sh
python3 finder.py candidates --version 1.21.8 --seed 123 --radius 8192 --out candidates.csv
```

Saved-world inspection (read-only):

```sh
python3 finder.py world --world /path/to/world-copy --max-y 0 --out saved-outposts.csv
```

Vanilla world verification (**only after personally accepting the EULA**):

```sh
python3 finder.py seed-vanilla --version 1.21.8 --seed 123 \
  --server-jar /path/to/server.jar --java java --eula-accepted \
  --radius 8192 --limit 10 --center-y-below -37 --max-y 0 \
  --out verified.csv
```

`verified-audit.csv` includes every examined candidate status. `--limit` restricts the sample; an empty result does not prove absence from the entire world.

See the [user guide](docs/USAGE.md), [architecture](docs/ARCHITECTURE.md), [exact-worldgen limitations](docs/EXACT_SEED_ENGINE.md) and [validation history](docs/VALIDATION.md) for further details.

### License

This project uses the [MIT License](LICENSE). Minecraft belongs to Mojang Studios. Neither official server JARs/worlds nor LowYSwampHut sources are bundled here.

### Full-map placement search (v2.0.1)

Use `python3 finder.py full-map --version 1.21.8 --seed 123 --strategy nearest --top 100 --out nearest.csv` to prove the nearest *placement attempts* in the entire world border without generating chunks. It prunes distant cells using admissible geometric distance bounds. For a literal scan of every cell, use `--strategy exhaustive`; build the optional single-threaded C11 accelerator with `python3 scripts/build_region_scan.py`, and resume checkpoints with `--resume` and the same output path/parameters. A full traversal spans 13,733,261,721 possible placement cells and can take substantial time. Neither mode calculates biomes, exact terrain, verified towers, or Y. See [Full-map guide](docs/FULL_MAP.md).
