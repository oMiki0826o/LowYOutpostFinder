# LowY Outpost Finder 使用教學

> 對應 2026-10-13 `main` 分支 1.0.0 為基礎之本地修復版 `2.0.1`。
> 此文件依據修復版程式碼撰寫；操作步驟是可用指令的說明，**不表示本文件作者曾在你的電腦上完成原版伺服器端到端實測**。

## 1. 這個工具能做什麼？

LowY Outpost Finder 用於研究 Minecraft Java 版低高度掠奪者前哨站。搜尋結果分成三類，**不能混為一談**：

| 結果 | 意義 | 是否證明前哨站存在？ |
| --- | --- | --- |
| `placement_candidate` | 依種子與結構放置規則計算出可能生成的位置 | 否 |
| `estimated_only` | 由額外的 C 地形核心推算高度，屬試驗性結果 | 否 |
| `verified_tower` | 從已生成、存檔的結構 NBT 識別出基板與塔樓 | 是，限對應存檔及其驗證條件 |

工具**目前不能**在完全不生成區塊的情況下，只靠種子精確取得所有前哨站 Y；亦不能保證找到世界全域最低 Y 或最低有效掠奪者刷怪 Y。

## 2. 事前準備

- Python **3.11 以上**。
- GUI 額外需要 Tkinter；沒有桌面圖形環境時請使用指令列。
- 只搜尋候選位置：**不需要** Java、Minecraft 伺服器或 C 編譯器。
- 自動原版驗證（Minecraft **1.21.8** 範例）：另外需要相容的 **Java 21**、可信任的同版本 `server.jar`，以及自行閱讀並同意 Minecraft EULA。
- 請保留足夠可用記憶體及磁碟空間；原版驗證會啟動 Java 並建立暫存世界。

從 GitHub 取得原始碼，在終端機進入專案資料夾：

```bash
git clone https://github.com/oMiki0826o/LowYOutpostFinder.git
cd LowYOutpostFinder
python3 --version
python3 finder.py --help
```

在 Windows 可將上述 `python3` 替換為 `py`，視 Python 安裝方式而定。若從 GitHub 下載 ZIP，解壓縮後進入含 `finder.py` 的資料夾即可。

## 3. 最容易使用的 GUI

開啟繁體中文介面：

```bash
python3 start_gui.py
```

直接啟動英文介面：

```bash
python3 start_gui.py --lang en-US
```

Windows 也可使用 `start_gui.bat`；macOS 提供 `start_gui.command`。介面上方可切換語言，並選擇以下模式：

| GUI 模式 | 用途 | 使用時機 |
| --- | --- | --- |
| 種子候選 | 快速列出可能的位置 | 第一次試用、沒有 JAR 時 |
| 全圖候選（免生成） | 全球最近候選證明，或可續跑的逐格盤點 | 想搜尋 X/Z 世界邊界內所有放置區域時 |
| 地形高度推算（試驗） | 1.21.8 近似高度排序 | 已另外編譯 C 核心時 |
| 已生成世界 | 讀取世界存檔的已生成前哨站 | 已有單人世界或伺服器備份時 |
| 候選存檔核對 | 對照候選 CSV 和同種子世界 | 要分辨哪些位置真的有結構時 |
| 原版伺服器實測 | 透過 RCON 生成並核對候選 | 已有本機伺服器、已備份世界時 |
| 種子原版實測 | 自動啟動臨時伺服器並確認 Y | 有可信任 `server.jar`，但沒有現成世界時 |

### GUI 第一次試用：種子候選

1. 選「種子候選」。
2. Minecraft 版本選 `1.21.8`，世界種子填入 `123`（示範用，並非低 Y 保證種子）。
3. 搜尋半徑先填 `8192`；輸出路徑設定為 `results/candidates.csv`。
4. 按開始，等待處理完成，查看預覽或 CSV。
5. **不要**將 CSV 中的候選座標與「前哨站一定存在」畫上等號。

### GUI 真正確認 Y：種子原版實測

1. 先確認 `java -version` 顯示與目標伺服器相容的 Java（1.21.8 使用 Java 21）。
2. 準備可信任的 **同版** `server.jar`；不要執行來源不明的 JAR。
3. 選「種子原版實測」，輸入版號、種子、搜尋半徑和 `server.jar` 路徑。
4. 初次測試建議 `limit=10`、`radius=8192`、`memory=2048`（MiB）。
5. 自行閱讀 Minecraft EULA 後，**只有同意才勾選**確認項。
6. 使用預設「近原點優先」；「低地形優先」是未經原版完整對拍的試驗排序，可能漏掉目標。
7. 按開始。這一模式**會真的生成區塊**，耗時與負擔遠高於候選搜尋。
8. 檢查結果 CSV，及同名的 `-audit.csv`。只有 `verified_tower` 才表示已從存檔確認塔樓。

GUI 預設的完整結構中心判定為 `structure_center_y < -37`。這個數字是工具的搜尋門檻，**不是**原版定義的有效刷怪高度，也不代表使用者必須採用它。

## 4. 命令列操作

### A. 只搜尋候選座標（最快）

```bash
python3 finder.py candidates \
  --version 1.21.8 \
  --seed 123 \
  --radius 8192 \
  --out candidates.csv
```

這個指令不啟動 Minecraft，也不計算確定的 Y。

### 全圖候選（不用生成世界）

```sh
python3 finder.py full-map --version 1.21.8 --seed 123 \
  --strategy nearest --top 100 --out results/world-nearest.csv
```

這個模式用距離下界證明全世界最近的**placement 候選**，不是原版實際低 Y 前哨站。完整逐格盤點與低 CPU 使用、檢查點續跑，請閱讀 [全圖搜尋教學](FULL_MAP.md)。

### B. 搜尋既有世界存檔（唯讀）

先使用**離線世界副本**，路徑必須指向包含 `level.dat` 和 `region/` 的世界資料夾。

```bash
python3 finder.py world \
  --world /path/to/world-copy \
  --max-y 0 \
  --out saved-outposts.csv
```

這是以存檔中存在的結構為對象；未生成的地方不會憑空出現結果。

### C. 對照候選 CSV 與世界

```bash
python3 finder.py verify \
  --world /path/to/world-copy \
  --candidates candidates.csv \
  --out verified-candidates.csv
```

CSV 的種子與版號必須和世界一致。`not_generated`、`absent`、`invalid_nbt`、`version_mismatch` 等狀態的含義不同，不要把未生成視為結構不存在。

### D. 種子原版實測（會啟動 Minecraft）

```bash
java -version
python3 finder.py seed-vanilla \
  --version 1.21.8 \
  --seed 123 \
  --server-jar /path/to/server.jar \
  --java java \
  --eula-accepted \
  --radius 8192 \
  --limit 10 \
  --center-y-below -37 \
  --memory 2048 \
  --out lowy-verified.csv
```

**只有在自行閱讀並接受 EULA 後**才加入 `--eula-accepted`。執行時程式會建立暫存世界並生成候選區塊，正常結束時刪除該暫存世界；結果保留在 CSV。

相關輸出：

- `lowy-verified.csv`：符合輸出條件且已確認的塔樓；可能只有表頭。
- `lowy-verified-audit.csv`：包含每筆檢查狀態、失敗或逾時資訊。

`--limit 10` 只核對最多 10 個候選，**沒找到不等於該世界或指定半徑內不存在**低 Y 前哨站。

### E. 選用近似地形模式

要先提供合法取得的 LowYSwampHut 2.0.1 原始碼壓縮檔，並在 macOS/Linux 安裝 CMake、C 編譯器：

```bash
sh build.sh /path/to/LowYSwampHut-2.0.1.tar.gz
python3 finder.py estimate \
  --version 1.21.8 \
  --seed 123 \
  --radius 8192 \
  --max-y 64 \
  --top 25 \
  --out estimated.csv
```

此模式是**試驗性近似高度**，不是已驗證的原版塔樓高度。Windows 的原生建置仍存在跨平台限制，不建議視為已支援的免設定功能。

## 5. 如何理解輸出

- `x`、`z`：工具採用的候選座標；不是每個方塊、塔樓中心或有效刷怪點的保證定位。
- `base_plate_y`：已確認基板片段的最低 Y（有值時）。
- `watchtower_min_y`、`watchtower_max_y`：已確認瞭望塔片段包圍盒的垂直範圍。
- `structure_min_y`、`structure_max_y`：所有儲存結構片段包圍盒的聯集垂直範圍。
- `structure_center_y`：`(structure_min_y + structure_max_y) / 2`，**不是掠奪者最低有效刷怪 Y**。
- `distance_sq`：到世界原點 `(0,0)` 的水平距離平方，用於排序。
- `status`：結果是否有真實存檔證據的關鍵欄位。

**重要：**「距離原點最近且中心 Y 小於 -37」與「整個世界最低 Y 的前哨站」是兩種不同搜尋目標，目前預設流程做的是前者的*有限候選檢查*。

## 6. 常見問題

**Q：輸出 CSV 只有標題，為什麼？** 可能檢查候選數太少、沒有符合門檻的 `verified_tower`，或生成失敗；先開啟 `-audit.csv` 找出原因。

**Q：看到 `not_generated`？** 表示存檔中尚無可核對的已完成區塊，不等於該處永遠沒有前哨站。

**Q：出現 Java 版本錯誤？** 執行 `java -version`，並在指令使用 `--java` 指定對應版本的 Java 路徑。1.21.8 應使用 Java 21。

**Q：Tkinter 無法開啟？** 安裝適用你 Python 環境的 Tkinter，或直接改用 `finder.py` 命令列；遠端無顯示器的終端機不適合開 GUI。

**Q：為什麼花很久、CPU／記憶體很高？** `seed-vanilla` 會啟動原版伺服器並生成區塊；先用較小 `--limit` 測試，確定負載可接受後再增加。`candidates` 則不啟動伺服器。

**Q：最低 Y 會增加不祥之瓶產量嗎？** 結構高度與實際刷怪效率是兩個問題；還需要單獨確認版本專屬刷怪規則、刷怪範圍、周邊空間與農場機制。

## 7. 介面新功能與搜尋條件

- 上方雙欄搜尋模式選擇、下方「搜尋結果／執行紀錄」分頁。開始時自動切換執行紀錄，成功後自動收合設定、顯示搜尋結果；可按「展開搜尋設定」重新編輯。
- 「使用教學」或按 F1 可以在程式內查看操作簡介。Ctrl+Enter 可開始搜尋。
- `--center-y-below -37` 使用嚴格小於；`--max-y 0` 使用小於等於，**兩項有設定時必須都符合**才能提早停止。
- 成果將記錄 `nearest_status` 等證據狀態：只代表指定半徑與已完成驗證候選，不代表全球最低 Y。

## 8. 驗證指令與回報錯誤

```bash
python3 -m compileall -q .
python3 -m unittest discover -s tests -v
```

舊版 GitHub Actions 在 Ubuntu／Windows 曾失敗；修復版已調整測試及工作流程，但跨平台重新執行結果必須以實際 Actions 為準。問題回報請包含：Minecraft 版本、種子、使用模式、操作系統、Python／Java 版本、精簡的錯誤訊息與去除密碼的日誌。

## 參考

- GitHub：<https://github.com/oMiki0826o/LowYOutpostFinder>
- Minecraft EULA：<https://www.minecraft.net/eula>
- 專案內部文件：`docs/ARCHITECTURE.md`、`docs/EXACT_SEED_ENGINE.md`、`docs/VALIDATION.md`


## 8. v2.0.0：A/B 雙路線、任意搜尋中心與稽核進度

已實作的無生成查詢可透過 `seed-geometry` 指令取得原版 Jigsaw 起始模板的旋轉與 `WORLD_SURFACE_WG` X/Z 取樣座標，必須自行提供**同版本** `server.jar`；此模式不計算高度。GUI 選「種子幾何（無 Y）」，填入種子、版本、資源 JAR、半徑和 X/Z 中心即可。

實測模式可在 GUI 指定搜尋中心、分批偏移量、實測結果排序；結果旁的 `-progress.csv` 會每筆更新，而 `-summary.json` 會在完整執行完成後寫入樣本覆蓋資訊。排序為高度不代表已確認整個範圍最低，請查看 `lowest_status`。想掃描下一批候選，可改變 `offset` 並使用保存的同一世界；暫存伺服器模式每次都會刪除世界，不能恢復已生成的區塊。

`--radius` 是相對中心的**正方形** X/Z 搜尋範圍，預設 `(0,0)`。當中心改動時，CSV 同時保留 `distance_sq`（到世界原點）和 `search_distance_sq`（到搜尋中心）。進階說明與指令詳見 [ROUTES_AB.md](ROUTES_AB.md)。


### 安裝前的原版 Java 與 JAR 預檢

```sh
python3 finder.py server-check --version 1.21.8 \
  --server-jar /path/to/server.jar --java java --out results/server-check.json
```

此動作只讀取 metadata、結構放置資源、Java 版本並輸出雜湊，不會啟動伺服器，不代表 EULA 已接受或高度搜尋已通過原版端到端驗證。
