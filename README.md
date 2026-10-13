# LowYOutpostFinder

![Project version](https://img.shields.io/badge/project-2.13.0-237b74)
![Python](https://img.shields.io/badge/Python-3.11%2B-35678f)
![GUI languages](https://img.shields.io/badge/GUI-繁體中文%20%7C%20English-237b74)

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

### 專案介紹

LowYOutpostFinder 是一款供 **Minecraft Java Edition 1.21 起**研究掠奪者前哨站與不祥之瓶農場使用的搜尋工具。提供繁體中文／英文桌面介面、命令列工具、原版世界存檔唯讀分析，以及可選的地形高度推算核心。

**請先區分三種結果：**

- **候選位置**：根據種子計算結構可能嘗試生成的區塊；不能保證前哨站存在，也沒有 Y。
- **近似高度**：使用可選的 LowYSwampHut C 核心，從種子推算世界生成前期的地表高度；**不是原版核實的前哨站高度**。
- **存檔驗證高度**：讀取同版本 Minecraft 已生成並儲存的結構 NBT，取得基板與塔樓片段的包圍盒 Y；不是實際掠奪者最低刷怪高度。

> **目前尚未實現跨版本、無須生成區塊、完全精確的「種子 → 實際前哨站 Y」演算法。** 另有「無世界存檔地形推算」GUI 模式，可直接由種子排序 **1.21.8 的試驗性近似高度**。不應把此模式的 Y 當成確定存在的前哨站，或已驗證的最低 Y 紀錄。

### 版本與依賴

| 能力 | 版本／條件 | 驗證程度 |
| --- | --- | --- |
| 結構放置候選計算 | Java `1.21`～`1.21.11`、`26.1`、`26.1.1`、`26.1.2`、`26.2`、`26.3` | 候選位置算法；各版原版完整生成對拍未完成 |
| 已生成存檔掃描／候選核對 | 上列版本 | NBT 解析及測試資料驗證；非各版原版端到端證明 |
| 原版臨時世界生成與高度驗證 | 列出版本；使用者提供同版官方 JAR、相容 Java | 自動執行流程已實作；尚未對各版本官方 JAR 進行端到端驗證 |
| 本機 RCON 生成核對 | 對應版本原版伺服器 | 流程已實作；仍需各版實機驗證 |
| 不預先建立存檔的 Y 推算 | **僅 1.21.8** | 外部 C 核心近似，**未完成原版高度對拍** |

Python 需 **3.11 以上**；一般搜尋、GUI 與 NBT 分析只用 Python 標準函式庫。GUI 需要 **Tkinter**；可選 C 推算則需要 CMake、C 編譯器及額外提供的 LowYSwampHut 原始碼壓縮包。

### 啟動圖形介面

解壓專案後，在根目錄執行：

```sh
# 繁體中文介面（預設）
python3 start_gui.py

# 英文介面
python3 start_gui.py --lang en-US
```

也能使用 `start_gui.command`（macOS）或 `start_gui.bat`（Windows）。Windows 若使用 `py` 啟動則為 `py start_gui.py --lang en-US`。Linux 若缺少 Tk，需透過系統套件管理員安裝（例如 `python3-tk`）。程式上方的「介面語言 / Language」選單可以在**執行中立即切換**，不會清除已填入的種子、路徑或密碼欄位；**不會**儲存密碼。

介面有六個模式：

| 模式 | 如何使用 | 輸出意義 |
| --- | --- | --- |
| 種子候選 | 指定版號、種子與搜尋半徑 | 只含 placement 候選，無高度 |
| 地形高度推算（試驗） | 選 `1.21.8`、數字種子、Y 上限、結果數；選擇外部原始碼壓縮包或先自行建置 C 核心 | 近似 `projected_surface_y`，不是已確認塔樓 Y |
| 已生成世界 | 指向含 `level.dat` 的世界資料夾 | 從原版結構資料讀取基板及塔樓片段 Y |
| 候選存檔核對 | 載入候選 CSV 與同種子、同版本世界 | 判別已確認、未生成、缺少結構或資料錯誤 |
| 原版伺服器實測 | 連接 `127.0.0.1` 的 RCON；**先備份世界** | 生成候選區塊後依 NBT 核對，會改動世界 |
| 種子原版實測 | 指定版號、種子、官方 `server.jar`，閱讀並接受 EULA | 自建隔離暫存世界、依候選生成，再擷取實際基板與瞭望塔 Y |

每個模式可預覽最多 500 筆；完整紀錄輸出 CSV。表格欄名和互動提示依介面語言切換，CSV 的欄位名稱及狀態代碼保持英文，方便使用指令或試算表處理。背景搜尋可以取消，搜尋完成前不會把不完整 CSV 當作成功結果。

### 自動原版高度驗證（不需要先建立世界存檔）

此模式從**世界種子、Java 版本與官方伺服器 JAR** 啟動隔離的暫存原版世界，透過本機 RCON 依距離出生點由近到遠逐一載入候選區塊，等待 `FULL` 區塊儲存後讀取結構片段的 NBT 包圍盒。會計算完整結構的 `structure_center_y`，預設找到第一個低於 `-37` 的已驗證前哨站後停止，並輸出 `verified_tower`；另外保留包含失敗、缺失及未生成狀態的稽核 CSV。正常結束時自動關閉伺服器並移除暫存世界。它**不需要既有世界存檔，但仍會實際生成區塊**，因此不是純種子免生成、完全精確的數學預測器。

先從官方 Minecraft 網站自行取得**所選版號**的原版伺服器 JAR，安裝該版要求的 Java，閱讀 Minecraft EULA 並自行決定是否接受。工具不附任何伺服器 JAR，也不會代替使用者接受條款。正式執行時使用 `--eula-accepted` 明確確認：

```sh
python3 finder.py seed-vanilla --version 1.21.8 --seed 123 \
  --server-jar /path/to/server.jar --eula-accepted \
  --radius 8192 --limit 20 --center-y-below -37 --out lowy-verified.csv
```

亦可在 GUI 選 **「種子原版實測」**，指定版號、種子、搜尋範圍、JAR、Java、記憶體以及逾時，勾選已閱讀並接受 EULA，再按開始。會產生 `lowy-verified.csv`（僅確認存在並通過最高 Y 條件的塔樓）與 `lowy-verified-audit.csv`（逐一候選狀態）。在 Windows GUI 強制結束處理程序時，不保證能優雅停止 Java 子行程；請自行確認沒有殘留伺服器程序。

**限制：** JAR 內的版號一致性檢查不是數位簽章驗證，務必使用可信任的官方檔案；啟動仍須與版號相容的 Java。`--limit` 至多 256，僅證明**已驗證的候選樣本**，不代表全世界最低高度；沒有命中也不能宣稱不存在低 Y 前哨站。**目前沒有在本環境使用 Mojang 官方 JAR 跑通端到端驗證**，因此正式原版執行仍須使用者自行檢查。

### 從種子直接推算近似地形 Y（選用）

此模式**不需要預先生成 Minecraft 世界，也不需要現有世界存檔**。但目前使用者提供的 LowYSwampHut 2.0.1 世界生成模型尚未對拍確認完整 Jigsaw 高度，因此只能作為低地形候選的**探索性排序**。

在 macOS／Linux 安裝 CMake 與 C 編譯器後，以另行取得的原始碼壓縮檔建置：

```sh
sh build.sh /path/to/LowYSwampHut-2.0.1.tar.gz
python3 finder.py estimate --version 1.21.8 --seed 123 \
  --radius 8192 --max-y 64 --top 25 --out approximate.csv
```

也可以直接在 GUI「地形高度推算」模式選擇該 `.tar.gz`，第一次執行時由程式呼叫 `build.sh`。Windows 的原生建置流程尚未完成驗證；可在具備 POSIX shell／CMake 的環境建置。若尚未建置、也未提供壓縮包，工具會明確提示。**此試驗功能尚不接受 1.21.8 以外的版本進行高度推算。**

### 命令列：位置與世界驗證

```sh
# 任一列出的版本：計算前哨站候選；結果不含 Y
python3 finder.py candidates --version 26.3 --seed 123 \
  --radius 8192 --out candidates.csv

# 對已有的存檔掃描（完全唯讀）
python3 finder.py world --world /path/to/world --version auto \
  --max-y 0 --out saved-outposts.csv

# 核對已輸出的候選 CSV，必須符合世界種子與版號
python3 finder.py verify --world /path/to/world \
  --candidates candidates.csv --out verified.csv
```

要使用 RCON 自動生成區塊，需自行安裝同版本原版 Minecraft 伺服器，閱讀並選擇是否接受 Minecraft EULA、設定本機 RCON 並**備份世界**。RCON 未加密，請勿開放到網際網路；一次最多 256 個候選。專案不包含 Minecraft 伺服器 JAR、世界存檔、第三方 C 原始碼或已編譯的原生執行檔。

CSV 的 `placement_candidate`、`estimated_only`、`verified_tower`、`not_generated` 等狀態有不同意義。`not_generated` 不是「確定沒有前哨站」，`verified_tower` 只代表已儲存的結構片段符合檢查條件。可進一步閱讀 [架構說明](docs/ARCHITECTURE.md) 和 [驗證紀錄](docs/VALIDATION.md)。

### v2.4.0：快速預篩與實際效能檢查

可以在「種子原版實測」選擇 **`near-origin`（預設）** 或 **`terrain`（試驗）**。前者優先檢查距原點最近的候選；後者**僅限 1.21.8**，先用本機 C 核心依近似地形 Y 排序，再讓原版伺服器只生成排名前 `--limit` 個候選。`terrain` 必須先執行 `build.sh` 或指定 `--core-archive`。這能把生成區塊的工作量限制在少數候選，但**可能跳過真正更低的前哨站**，不可用來證明全區域最低 Y。

```sh
python3 finder.py seed-vanilla --version 1.21.8 --seed 123 \
  --server-jar /path/to/server.jar --eula-accepted \
  --radius 32768 --limit 20 --priority terrain \
  --core-archive /path/to/LowYSwampHut-2.0.1.tar.gz \
  --out verified.csv

# 不啟動 Minecraft；在自己的電腦測候選掃描和近似高度速度
python3 scripts/benchmark.py --seed 123 --radii 8192,32768,65536 --rounds 3
# 若先建置 C 核心：
python3 scripts/benchmark.py --seed 123 --radii 8192,32768 --native bin/lowyoutpost

# 使用真正原版驗證後的 CSV，對照同版本同種子的估測誤差
python3 height_audit.py --estimated approximate.csv --verified verified-audit.csv
```

「候選搜尋」只計算位置；「地形推算」只做 Noise/近似高度；「原版實測」會啟動 Java 並生成區塊。三者耗時與記憶體需求差異很大。詳見 [效能指南](docs/PERFORMANCE.md) 與 [精確免生成引擎規劃](docs/EXACT_SEED_ENGINE.md)。**現階段仍沒有已驗證的跨版完全精確種子→前哨站 Y 演算法。**

### v2.5.0：進階搜尋（參考 LowYSwampHut）

主視窗的 **「進階搜尋：單種子／種子清單」** 開啟新的雙語工作區。它參考使用者提供的 LowYSwampHut 2.0.1 原始碼與 README 的互動流程，但保留前哨站與女巫小屋**不同的生成模型**：

- **單種子／批次種子**：載入 UTF-8 `.txt`（每行一個十進位 seed、可有 `#` 註解，會去重），或輸入單一 seed。
- **矩形座標範圍**：以 512 方塊為一個區域、輸入 `MinX / MaxX / MinZ / MaxZ`；可重設小範圍或世界邊界。最大單次工作量為 500 萬區域；若設定整個世界邊界，會要求分段掃描，避免意外耗盡資源。
- **模式切換**：`candidates` 跨 1.21～26.3 計算放置候選但沒有 Y；`estimate` 僅 1.21.8，以使用者自行建置的 LowYSwampHut C 核心推算近似地形 Y，**不能視為真正前哨站高度**。兩者不共用 Y 的定義。
- **批次處理**：最多 16 個並行種子工作、暫停／繼續／停止、已完成種子與剩餘時間顯示；單種子候選掃描另顯示區域列進度。暫停不會凍結已開始的 C 計算，而是阻止下一份工作開始。
- **排序與匯出**：按近似 Y（僅限有 Y 的資料）、原點距離或種子排序；將所有結果匯出 CSV、僅匯出命中種子 `.txt`，或匯出純文字座標。**沒有經原版確認的 Y 時，座標文字只寫註解，不輸出虛構的 `/tp x y z`。**

使用相同功能的命令列，可用於批次腳本：

```sh
# 在座標原點附近的 -16～16 區域格（每格 512 方塊）搜尋 1.21.8 候選
python3 explorer.py --version 1.21.8 --seed 123 --min-x -16 --max-x 16 \
  --min-z -16 --max-z 16 --threads 2 --top 500 --out candidates.csv

# 批次種子 + 試驗性地形 Y（請先用 sh build.sh 編譯 C 核心）
python3 explorer.py --mode estimate --version 1.21.8 \
  --seeds-file seeds.example.txt --radius 8192 --max-y 64 \
  --threads 2 --top 25 --sort y --out approximate.csv \
  --export-seeds selected-seeds.txt --export-tp coordinates.txt
```

舊款 8GB Mac 若使用近似高度批次搜尋，建議先設定 **1～2 個並行種子工作**；使用更多程序可能增加記憶體壓力。

**和參考工具的功能差距：**這些介面與批次功能已可用，但原版前哨站 Jigsaw 放置、跨版本精確 `WORLD_SURFACE_WG`、真正的最低有效刷怪 Y 仍**未實作**。參考專案的女巫小屋 footprint 計算無法直接取代前哨站高度推導。見 [功能對照表](docs/REFERENCE_PARITY.md) 與 [精確引擎設計](docs/EXACT_SEED_ENGINE.md)。

### 測試與打包

```sh
python3 -m compileall -q .
python3 -m unittest discover -s tests -v

# 需已建置 C 核心及安裝 JDK
python3 tests/check_placement.py bin/lowyoutpost

# 產生乾淨的原始碼壓縮包（需在專案根目錄）
python3 scripts/package_release.py --output ../LowYOutpostFinder-2.13.0.zip
```

測試可檢查位置 RNG、CLI、NBT、GUI 翻譯、CSV 與已實作的 RCON 通訊流程；**不能取代原版各版本的地形高度實測**。詳見 [驗證紀錄](docs/VALIDATION.md)。

### v2.6.0：結果完整性與存檔防誤判

- 進階搜尋讀取外部 C 高度結果時，逐筆檢查 Minecraft 版本、種子、區塊座標、原版放置候選資格、搜尋邊界及 Y 範圍；拒絕重複或格式錯誤的樣本。外部資料不再能直接進入「近似 Y」結果表。
- 已生成存檔若含與索引位置不一致的 `xPos`／`zPos`，該筆會回報 `invalid_nbt`，而不是當成可信的前哨站結果。
- 保留 `estimated_only` 與 `verified_tower` 的明確區分，**未新增尚無證據的精確免生成高度能力**。

### v2.7.0：Jigsaw 起始基板旋轉與精確取樣座標

上一版的 C 地形搜尋只查詢候選區塊中心 `(chunkX*16+8, chunkZ*16+8)`，**不是 Jigsaw 原版的起始投影座標**。本版新增使用 `ChunkRandom.setCarverSeed` 的 48 位 Java RNG、四方向模板旋轉及 `StructureTemplate.createBox` 包圍盒中心的計算；可使用**同版本遊戲資源 JAR** 中的 `base_plate.nbt` 讀取真正的模板尺寸，而不再猜測模板長寬。

1. 使用者提供與所選版本相符、包含原版 `data/minecraft/...` 的遊戲資源 JAR（不是任意安裝器）；本工具僅唯讀解析必要的結構 JSON 與 NBT，不執行該 JAR。
2. 指令 `estimate --game-jar` 使用旋轉後的起始模板包圍盒中心取樣，新增 `sample_x`、`sample_z`、`rotation` 與 `projected_base_plate_y` 四個 CSV 欄位。
3. GUI「地形高度推算」及「種子原版實測」的 `terrain` 排序可指定上述遊戲 JAR。未提供 JAR 時保留舊版區塊中心預篩；不能把兩者混為一談。

```sh
sh build.sh /path/to/LowYSwampHut-2.0.1.tar.gz
python3 finder.py estimate --version 1.21.8 --seed 123 --radius 8192 \
  --game-jar /path/to/matching-game-assets.jar --max-y 100 --top 25 \
  --out projected-estimates.csv
```

此處精確的是**旋轉、基板中心的 X/Z 幾何與 Java 隨機數序列**，**不是最終的 Y**。`projected_base_plate_y = 近似 WORLD_SURFACE_WG - 1` 只依目前 C 地形模型推算。尚未完成對 1.21.8～26.x 各版真正 `NoiseChunkGenerator`、Biome/Jigsaw 全流程的原版實測對拍，也未實作塔樓片段的完整 Jigsaw 連接。結果仍標示 `estimated_only`，不可當成確認存在的前哨站、最低有效刷怪高度或全域最低紀錄。詳見 [起始結構投影細節](docs/PROJECTED_START.md)。

### v2.8.0：使用原版存檔檢查 Jigsaw 幾何與高度誤差

本版新增 **`geometry-audit`**：針對同種子、同版已生成的世界，逐筆從結構 NBT 讀取 `base_plate`，以遊戲資源 JAR 的模板尺寸與種子所計算的旋轉重建**預期 X/Z 包圍盒**。比較實際包圍盒與 `rotation`，回報幾何是否一致；也可附上包含投影座標的 C 近似結果，量測 `projected_base_plate_y - 實際 base_plate_y`。這項功能將「起始位置演算法錯誤」與「地形模型高度誤差」分開，讓後續除錯有明確證據。

```sh
# 使用遊戲資源 JAR 驗證候選放置規則（spacing/separation/salt 等）
python3 finder.py candidates --version 1.21.8 --seed 123 --radius 8192 \
  --game-jar /path/to/matching-game-assets.jar --out candidates.csv

# 需要已生成世界 + 同版遊戲資源 JAR；只讀取存檔，不會生成區塊
python3 finder.py geometry-audit --world /path/to/world \
  --candidates candidates.csv --game-jar /path/to/matching-game-assets.jar \
  --out geometry-audit.csv --summary geometry-audit.json

# 如有使用帶有 sample_x / sample_z / rotation 的估測結果，可額外比較 Y
python3 finder.py geometry-audit --world /path/to/world \
  --candidates candidates.csv --game-jar /path/to/matching-game-assets.jar \
  --estimates projected-estimates.csv --out geometry-audit.csv
```

`geometry_status=match` 代表**起始基板的水平方向與原版存檔一致**，並不是 Noise 或最終塔樓 Y 的精確性證明。無完整區塊存檔時會回報 `not_checked`；資料不一致會提供具體原因。`estimates` 必須包含原版基板取樣位置；舊版區塊中心估測不能混充。來源 JAR 僅作參數相容性檢查，無法證明檔案真實來源或其對應版號。**原版免生成 Noise／生態域／全部 Jigsaw 子結構的完全精確引擎仍尚未完成。**

### v2.9.0：從原版模板推導塔樓相對高度（條件式精確）

除了基板的起始旋轉，本版可從**同版本遊戲資源 JAR** 的 `base_plate.nbt`、`watchtower.nbt` 與 `towers.json` 讀取 Jigsaw 連接點。對支援的單一剛性塔樓連接，根據原版剛性片段的高度計算規則，求出塔樓相對於基板的固定 Y 差值。支援已辨識的垂直與水平剛性連接；如果連接點不存在、方向不適用，或可能產生不同 Y，程式會**明確拒絕**而不是猜測。

```sh
# 注意：--world-surface-wg 必須來自對應版本真正的 WORLD_SURFACE_WG。
# 此值是「使用者自行提供」，程式不會從種子算出它，也不會驗證其真實性。
python3 finder.py tower-project --version 1.21.8 --seed 123 \
  --chunk-x <前哨站候選區塊X> --chunk-z <前哨站候選區塊Z> \
  --game-jar /path/to/matching-game-assets.jar --world-surface-wg <原版取樣高度> \
  --out tower-projection.json
```

`base_min_y` 與 `tower_min_y` 在**輸入高度確實為該座標的原版高度、且該塔樓連接成功**時，才是相應剛性片段的計算結果；輸出固定標註 `conditional_on_external_worldgen_height`，絕不標示 `verified_tower`。`geometry-audit` 可額外把實際存檔塔樓高度與模板推導的相對 Y 對照，以 `tower_vertical_status` 回報 `match`、`mismatch` 或缺少模板等情況。

另修正了 Native C 搜尋的 `--max-y` 判定：**提供基板模板尺寸時**，以 `projected_base_plate_y`（近似地表 Y − 1）為門檻；未提供模板時仍沿用近似地表 Y 的篩選方式。這個修正避免低一格的基板在邊界條件被錯誤排除，**並未讓 C Noise 變得精確**。

**仍未完成：**從種子精確生成各版本 `WORLD_SURFACE_WG`、完整 Biome 過濾、完整 Jigsaw 隨機連接與碰撞，以及用真實 Mojang 伺服器對拍。請勿把條件式塔樓高度當成已確認的最低 Y 前哨站。

### v2.10.0：直接檢查原版伺服器 JAR（不需要解包）

本版已使用使用者提供的 **Minecraft Java 26.3** `server.jar` 進行原始資源實測。工具能直接讀取其內層的遊戲資料 JAR，檢查前哨站／村莊放置參數、生態域標籤、基板與瞭望塔模板，以及新版小寫 `id/properties` 的 NBT 方塊狀態。對這份 26.3 資源，基板尺寸為 **16 × 30 × 16**，瞭望塔為 **15 × 21 × 15**；原版模板中兩個水平剛性連接點都導出相同的相對 Y 位移 **0**。這些是**版本專屬的資源幾何結果**，不是從種子算出的實際塔樓高度。

```sh
python3 finder.py assets-audit --version 26.3 \
  --server-jar /path/to/server.jar --out outpost-assets.json

python3 finder.py candidates --version 26.3 --seed 123 \
  --game-jar /path/to/server.jar --radius 8192 --out candidates.csv
```

`assets-audit` 不啟動遊戲或生成區塊；輸出明確列出 JAR 宣告版本、Java 最低版本、結構參數雜湊與高度推導。**26.3 伺服器宣告要求 Java 25**；若本機只有 Java 21，`seed-vanilla` 會在啟動伺服器前顯示不相容訊息。GUI 原有的「Java 執行檔」欄位可指定相容的 Java 路徑。對其他遊戲版本只在提供**相符版本**的 JAR 且資料符合檢查時執行相同核對；不能把 26.3 的模板尺寸套用到 1.21.8。

**尚待完成：**純種子精確 `WORLD_SURFACE_WG`、全套 Noise／Biome、完整 Jigsaw 隨機連接及含碰撞的生成模擬，與實際原版世界的端到端對拍。這份 `server.jar` 目前僅完成**離線資源核對**，不是實際生成驗證。詳見 [原版資源核對](docs/SERVER_ASSETS.md)。

### v2.12.0：原版世界生成資源與 Jigsaw 資料鏈稽核

這版增加兩項純唯讀檢查，可直接選取同版 Mojang `server.jar`（支援外層 Bundler），**不需生成區塊、不需接受 EULA**：

```sh
python3 finder.py worldgen-contract --version 1.21.8 --game-jar ./server.jar --out worldgen.json
python3 finder.py jigsaw-contract --version 1.21.8 --game-jar ./server.jar --out jigsaw.json
```

- `worldgen-contract`：逐一載入 Noise Router 所需密度函數與噪聲參數，檢查缺失與循環相依、記錄 SHA-256；**尚未執行 Noise 方塊高度計算**。
- `jigsaw-contract`：從 `base_plates` 追查所有可達的 Jigsaw 結構池、NBT 模板及連接點參照；**尚未重播原版隨機選擇／拼接碰撞結果**。
- `certify-samples`：拿已生成的真實世界之 `height-witness` CSV 與近似預測 CSV 比較；必須再次讀取同版 JAR 核對模板雜湊，才會產生帶有輸入 SHA-256 的有限樣本比對報告。`--require-matches` 可在任何誤差或漏筆時中止，不會覆蓋舊報告。

```sh
python3 finder.py certify-samples --witnesses witnessed.csv --estimates estimated.csv \
  --game-jar ./server.jar --require-matches --out certification.json
```

**目前仍沒有完整、免生成的精確 Noise/Biome/Jigsaw 模擬器；資源完整性及有限樣本吻合，不等於精確世界生成。** 目前從原版 JAR 只驗證了 `1.21.8` 和 `26.3` 的資源圖。見 [驗證報告](docs/VALIDATION.md)。

### v2.11.0：原版高度取樣見證與 C 模型逐筆對拍

此版新增一條可重現的**高度對拍資料流程**，使用你提供的同版本 `server.jar` 作為資料定義來源。它不會憑空產生真實遊戲樣本：必須先用正式 Minecraft 世界生成候選區塊，再把產生的世界存檔交給工具分析。因 Minecraft 伺服器 EULA 需要使用者自行閱讀與同意，本專案不會替使用者接受授權。

從同版本世界的 `base_plate` 與 `watchtower` 結構 NBT 出發，先比對種子推算的旋轉、基板水平包圍盒及剛性塔樓垂直連接。**只有三項全部通過**，才推回該單一取樣點的 `WORLD_SURFACE_WG = base_plate_y + 1`，建立可供新 Noise 核心回歸測試使用的見證 CSV；失敗或尚未生成的候選不會被列為證據。

```sh
# 使用同版原版伺服器生成並儲存世界後（應保留其存檔）：
python3 finder.py height-witness --world ./vanilla-world \
  --candidates candidates.csv --game-jar /path/to/server.jar \
  --out height-witnesses.csv --summary height-witnesses.json --require-samples

# 可選：以先前 C 模型的輸出，逐筆比較同一 seed、座標、旋轉與 Y
python3 finder.py compare-witness --witnesses height-witnesses.csv \
  --estimates approximate.csv --out height-diffs.csv --summary height-diffs.json
```

`height-witness` 讀取世界存檔而不改動世界；`--require-samples` 會在沒有可接受的實際塔樓樣本時報錯。`compare-witness` 會列出高度差與最大誤差，但即使有限樣本全部一致，也**不表示跨版全域精確**。`assets-audit` 現在會遞迴展開原版生態域標籤（例如 `#minecraft:is_mountain`），但這僅證明同版允許哪些生態域，**尚未實作從種子生成該生態域的位置**。

本次直接讀取了使用者提供的 **1.21.8 / Java 21** 和 **26.3 / Java 25** 兩份伺服器 JAR 的資源，確認兩版的前哨站放置設定與模板尺寸符合現有核對程式；**沒有獲得真實原版世界存檔作為高度對拍樣本**，也沒有執行遊戲伺服器端到端測試。完整狀態見 [精確引擎剩餘工作](docs/EXACT_SEED_ENGINE.md) 與 [驗證報告](docs/VALIDATION.md)。

### v2.13.0：有限範圍最低 Y 的存檔完整性證明

新版 `region-certificate` 會**列舉指定半徑內全部符合放置演算法的前哨站候選**，逐一查詢已生成世界的來源區塊，不再把「只檢查前幾十個候選」當成整個範圍的最低紀錄。它同時核對 Minecraft 版本、世界種子、區塊完整狀態、模板幾何與瞭望塔垂直關係；使用者需提供**對應版本**的遊戲資源 JAR 才能核證含塔樓的結果。

```sh
python3 finder.py region-certificate \
  --world /path/to/offline-world-copy \
  --game-jar /path/to/matching-server.jar \
  --radius 8192 --max-candidates 10000 \
  --out region-report.json \
  --audit region-audit.csv \
  --pending pending-chunks.csv \
  --require-complete
```

- `region-report.json`：輸出候選總數、缺漏與錯誤數、有限範圍最低基板 Y／塔樓 Y、原點座標及證據摘要。**只有所有起始區塊均為 FULL 且所有已找到的塔樓通過模板幾何核對，才會提供 `lowest_confirmed_*`。**
- `region-audit.csv`：逐筆顯示 `absent`、`verified_tower`、`not_generated`、`not_full` 或其他不確定狀態。
- `pending-chunks.csv`：只匯出未生成／未完成的候選，可交給現有 `live` 模式分批生成；已損毀或幾何不符的區塊必須另外調查。`--require-complete` 遇到缺漏時傳回非零退出碼。

**重要限制：** 此證明只針對**已生成、離線且未修改的原版世界存檔及指定有限半徑**，並非「輸入種子即得精確 Y」、全世界最低、或最低有效掠奪者刷怪高度。它也不能驗證伺服器檔案是否經人為竄改。執行前請複製並停止修改該存檔；程式會在讀取前後檢查相關世界檔案是否改變。若範圍超過數量上限會拒絕作業，而不是隱藏截斷的候選。

### 授權

此專案**尚未指定再散布授權**，壓縮包也不包含 LICENSE。請勿將原始碼可供查看誤認為已取得開源再散布許可。Minecraft 與原始第三方 LowYSwampHut 專案分別遵守其各自的權利與授權條款；本工具不是 Mojang 官方作品。

---

## English

### Overview

LowYOutpostFinder helps research **pillager outposts and ominous-bottle farms in Minecraft Java Edition 1.21 and later**. It includes a Traditional Chinese / English desktop GUI, a CLI, read-only Anvil/NBT world inspection, and an optional seed-based terrain estimation backend.

**Three fundamentally different results must not be confused:**

- **Placement candidates** are chunks where the placement algorithm attempts an outpost. They have no confirmed structure and no Y value.
- **Approximate surface height** is computed from a seed using an optional LowYSwampHut-based C backend. It is **not a vanilla-verified tower height**.
- **Verified saved height** comes from the bounding boxes of structure pieces recorded in generated and saved chunks. It is not the lowest viable pillager-spawning Y.

> **An exact, cross-version, seed-to-real-outpost-Y predictor that requires no generated chunks has not yet been implemented.** An additional mode offers a no-save-needed **experimental approximate height** workflow for **Java 1.21.8 only**. Its output must never be presented as confirmed outpost locations or record-breaking minimum Y values.

### Version support and requirements

| Capability | Versions / requirements | Verification level |
| --- | --- | --- |
| Placement candidate calculations | `1.21`–`1.21.11`, `26.1`, `26.1.1`, `26.1.2`, `26.2`, `26.3` | Placement algorithm; not a complete vanilla per-version end-to-end test |
| Saved world scan / CSV verification | Versions listed above | Tested NBT parsing and fixtures; per-version vanilla generation remains unverified |
| On-demand temporary vanilla world and height verification | Listed versions; matching official JAR and compatible Java needed | Automated workflow implemented, not fully tested against Mojang JARs |
| Local server generation and checks | Matching vanilla server version | Workflow implemented; further in-game validation required |
| Seed-only approximate Y | **1.21.8 only** | External experimental C backend; no exact height validation |

The application needs **Python 3.11+**. The normal CLI, GUI, and NBT reader require only the Python standard library; desktop operation needs **Tkinter**. The optional native estimator needs CMake, a C compiler, and a separately supplied LowYSwampHut source archive.

### Launch the GUI

From the extracted project root:

```sh
# Traditional Chinese (default)
python3 start_gui.py

# English UI
python3 start_gui.py --lang en-US
```

Alternatively launch `start_gui.command` on macOS or `start_gui.bat` on Windows. On Windows you can also use `py start_gui.py --lang en-US`. Some Linux systems require a separate `python3-tk` package. Use the **Interface language / English** drop-down in the running app to switch languages immediately; the current seed, file paths, and password entry are preserved, and the password is **never saved**.

The six GUI modes are:

| Mode | Input | Meaning of output |
| --- | --- | --- |
| Seed candidates | Java version, seed, radius | Placement-only candidates, no Y |
| Terrain estimate (experimental) | **1.21.8** seed, radius, maximum Y, result limit, optional external C source archive | Approximate `projected_surface_y`, **not** confirmed tower Y |
| Generated worlds | World directory containing `level.dat` | Saved base plate / tower bounding-box heights |
| Verify candidate CSV | Same-seed, same-version candidate CSV and saved world | Confirmed, missing, not generated or invalid status per candidate |
| Vanilla server verification | Localhost RCON, **backed-up world** | Generates and saves candidate chunks before checking their NBT |
| Seed-to-vanilla verification | Exact version, seed, official `server.jar`, informed EULA acceptance | Creates isolated temporary world, generates candidates, then reads saved base-plate/tower Y |

A table previews up to 500 rows; the complete results are saved to CSV. Visible headings and prompts follow the chosen GUI language. CSV column names and status codes intentionally remain stable English identifiers for interoperability. Searches run in a cancellable subprocess and do not publish a partial CSV as a successful result.

### On-demand vanilla height verification (no existing world save required)

This mode launches the **matching official vanilla server JAR** in an isolated temporary folder, creates a world from your seed, loads candidate chunks using loopback-only RCON, waits for saved `FULL` chunks, and reads the **actual recorded** base-plate / watchtower NBT bounding boxes. It outputs confirmed towers sorted by saved base-plate Y, plus an audit CSV with absent, incomplete and timeout statuses. Under normal shutdown the disposable world is deleted. **Chunk generation really happens; this is not an exact mathematical seed-only noise/Jigsaw emulator.**

Obtain the appropriate vanilla server JAR from Minecraft's official distribution, install a Java runtime compatible with that release, read the Minecraft EULA, and explicitly decide whether to accept it. Nothing is bundled or accepted on your behalf:

```sh
python3 finder.py seed-vanilla --version 1.21.8 --seed 123 \
  --server-jar /path/to/server.jar --eula-accepted \
  --radius 8192 --limit 20 --max-y 0 --out lowy-verified.csv
```

You can instead select **Seed-to-vanilla verification** in the GUI, set the version, numeric seed, radius, JAR, Java executable, heap and timeouts, and check the informed EULA acceptance checkbox. `lowy-verified.csv` contains only confirmed towers satisfying the Y threshold, while `lowy-verified-audit.csv` reports every checked candidate. Force-terminating the GUI worker on Windows may leave the child Java server alive; check your processes after cancellation.

**Limitations:** JAR version metadata is checked, but its authenticity is not cryptographically verified: only run an official trusted distribution. The JVM must match the game version. The verification cap is 256 candidate chunks per run, so the lowest verified sample is **not** a proof of the globally lowest outpost. No Mojang server JAR was available in the test environment to complete an authentic end-to-end run; per-version game testing is still required.

### Estimate terrain Y directly from a seed (optional)

This workflow **does not require a pre-generated world or existing saved chunks**, but the supplied LowYSwampHut 2.0.1 world-generation model has **not** been verified as an exact outpost/Jigsaw-height oracle. Treat the results as an **exploratory ranking** only.

On macOS/Linux with a C compiler and CMake:

```sh
sh build.sh /path/to/LowYSwampHut-2.0.1.tar.gz
python3 finder.py estimate --version 1.21.8 --seed 123 \
  --radius 8192 --max-y 64 --top 25 --out approximate.csv
```

You can also select that `.tar.gz` archive in the GUI's *Terrain estimate* mode, which invokes the build script if needed. Native building on Windows has not been validated; a POSIX shell and CMake environment are required. Missing native dependencies result in an explicit error. **Other versions are not accepted for seed-only Y estimation.**

### CLI: candidates and saved-world verification

```sh
# Any listed candidate version (no Y)
python3 finder.py candidates --version 26.3 --seed 123 \
  --radius 8192 --out candidates.csv

# Scan existing world data (read-only)
python3 finder.py world --world /path/to/world --version auto \
  --max-y 0 --out saved-outposts.csv

# Cross-check candidate CSV against the matching save
python3 finder.py verify --world /path/to/world \
  --candidates candidates.csv --out verified.csv
```

For RCON-assisted generation, provide a matching vanilla Minecraft server, review and independently accept the Minecraft EULA if appropriate, configure **localhost-only** RCON, and **back up the world** first. RCON is unencrypted and must not be made public. Each batch is limited to 256 candidates. No server JARs, saved worlds, third-party C source, or native executables are bundled.

CSV classifications such as `placement_candidate`, `estimated_only`, `verified_tower`, and `not_generated` are not interchangeable. In particular, `not_generated` does **not** mean the outpost cannot appear, and `verified_tower` refers to persisted structure pieces, not current block integrity or actual spawn rates. See the [architecture](docs/ARCHITECTURE.md) and [validation report](docs/VALIDATION.md).

### v2.4.0: fast pre-ranking and measured performance

**Seed-to-vanilla verification** can prioritize `near-origin` (default) or `terrain` (experimental, **Java 1.21.8 only**). Terrain priority ranks candidates by unverified projected surface Y using the optional native C backend and generates only the first `--limit` candidates in Minecraft. Supply `--core-archive` or build the C backend first. **This can miss true lower-Y towers and does not prove a regional minimum.**

```sh
python3 finder.py seed-vanilla --version 1.21.8 --seed 123 \
  --server-jar /path/to/server.jar --eula-accepted \
  --radius 32768 --limit 20 --priority terrain \
  --core-archive /path/to/LowYSwampHut-2.0.1.tar.gz \
  --out verified.csv

# Benchmark without launching Minecraft
python3 scripts/benchmark.py --seed 123 --radii 8192,32768,65536 --rounds 3
python3 scripts/benchmark.py --seed 123 --radii 8192,32768 --native bin/lowyoutpost

# Compare estimates with actual saved tower bounding boxes
python3 height_audit.py --estimated approximate.csv --verified verified-audit.csv
```

Candidate placement, experimental terrain sampling, and real vanilla generation have substantially different resource costs. See [performance](docs/PERFORMANCE.md) and the [exact seed-only engine design](docs/EXACT_SEED_ENGINE.md). **An exact, cross-version, no-chunk-generation outpost-Y predictor remains unimplemented and unverified.**

### v2.5.0: Advanced explorer (inspired by LowYSwampHut)

The main window now offers **Advanced explorer: Single / Batch**, using the interaction model from the supplied LowYSwampHut 2.0.1 sources while **not** assuming that the outpost and swamp-hut height algorithms are interchangeable.

- **Single seed / seed list**: numeric Java signed-long seeds; an UTF-8 `.txt` file with one seed per line; comments and duplicate seeds handled.
- **Rectangular boundaries**: 512-block region indices `MinX/MaxX/MinZ/MaxZ`, default area reset, and a world-boundary reset. Searches are capped at 5 million regions per invocation: whole-world scans must be split.
- **Two clearly separated outputs**: `candidates` for 1.21–26.3 produces placement attempts **without Y**; `estimate` for **1.21.8 only** produces experimental approximate surface Y with the optional user-supplied native backend. **Neither mode proves that an outpost spawns.**
- **Batch workflow**: up to 16 concurrent seed workers, pause/resume/stop, progress by finished seed plus remaining-time estimate. Single-seed placement mode also shows region-row progress. Pause waits between native sampling jobs rather than suspending a running C job.
- **Sorting/exports**: sort by approximate Y (only for rows with Y), origin distance, or seed. Export CSV, seed-only text list, and coordinate notes. **Only vanilla-verified saved structure rows can produce literal `/tp x y z` commands**; provisional rows contain coordinate comments instead.

```sh
python3 explorer.py --version 1.21.8 --seed 123 \
  --min-x -16 --max-x 16 --min-z -16 --max-z 16 \
  --top 500 --out candidates.csv

# Build the optional 1.21.8 terrain sampler with sh build.sh first
python3 explorer.py --mode estimate --version 1.21.8 \
  --seeds-file seeds.example.txt --radius 8192 --max-y 64 \
  --threads 2 --top 25 --sort y --out approximate.csv \
  --export-seeds selected-seeds.txt --export-tp coordinates.txt
```

On an older Mac with 8 GB RAM, start with **1–2 parallel seed workers** for native terrain jobs to avoid memory pressure.

**Not equivalent to the reference's full capabilities:** exact Jigsaw position/Y, version-specific `WORLD_SURFACE_WG`, true viable pillager spawn minimum and no-chunk vanilla-equivalent outpost generation are **not implemented**. See the [feature comparison](docs/REFERENCE_PARITY.md) and [exact-engine roadmap](docs/EXACT_SEED_ENGINE.md).

### v2.6.0: Native result and saved-world integrity

- Experimental native output is now checked per row against the selected Java version, world seed, candidate-placement algorithm, chunk/block coordinates, search radius and Y bounds. Malformed, duplicate or unexpected rows are rejected rather than shown as plausible estimates.
- Saved chunk coordinates (`xPos`/`zPos`) are cross-checked when present; mismatches are reported as `invalid_nbt`.
- This improves trustworthiness of the existing workflow; **exact, no-chunk-generation, cross-version Jigsaw height prediction is still not implemented**.

### Tests and source packaging

```sh
python3 -m compileall -q .
python3 -m unittest discover -s tests -v

# Requires a built C scanner and the JDK
python3 tests/check_placement.py bin/lowyoutpost

# Clean source-only ZIP; run from the project root
python3 scripts/package_release.py --output ../LowYOutpostFinder-2.13.0.zip
```

The test suite covers placement RNG, CLI parsing, NBT data, translated GUI, CSV safety and implemented RCON protocol behavior. **It does not replace per-release vanilla terrain and structure-height tests.** See [validation details](docs/VALIDATION.md).

### v2.7.0: Jigsaw baseplate rotation and correct X/Z projection

The previous native estimator sampled the **candidate chunk center**, not the Jigsaw start-piece position. This release reproduces `ChunkRandom.setCarverSeed`, the four `BlockRotation` values, and the rotated start-template bounding-box center. An optional **matching game assets JAR** supplies the actual `base_plate.nbt` dimensions instead of a hard-coded assumption. The JAR is read as data, never executed.

Use `finder.py estimate --game-jar /path/to/matching-game-assets.jar` (or the new GUI field) to produce the extra `sample_x`, `sample_z`, `rotation` and `projected_base_plate_y` columns. The `seed-vanilla --priority terrain` mode can also use the same JAR to improve candidate ordering. Without an assets JAR, the original chunk-center exploratory estimate is retained.

```sh
sh build.sh /path/to/LowYSwampHut-2.0.1.tar.gz
python3 finder.py estimate --version 1.21.8 --seed 123 --radius 8192 \
  --game-jar /path/to/matching-game-assets.jar --max-y 100 --top 25 \
  --out projected-estimates.csv
```

**Exactness is limited to rotation and X/Z geometry, not Y**: `projected_base_plate_y` is derived from the **experimental** height model (projected `WORLD_SURFACE_WG - 1`). This is **not** a confirmed tower, verified Minecraft height, mob spawn Y, or exhaustive lowest-outpost result. Full version-specific Noise/Biome/Jigsaw parity and in-game comparisons remain incomplete. See [Jigsaw start projection](docs/PROJECTED_START.md).

### v2.8.0: Audit saved Jigsaw geometry and seed-height error

The new **`geometry-audit`** command reads the **actual saved** `base_plate` structure piece, reconstructs the expected rotation and horizontal bounding box from the seed and template dimensions, and distinguishes a rotation/footprint mismatch from an estimated Y-model error. It neither creates chunks nor certifies the terrain model as exact.

```sh
python3 finder.py candidates --version 1.21.8 --seed 123 --radius 8192 \
  --game-jar /path/to/matching-game-assets.jar --out candidates.csv
python3 finder.py geometry-audit --world /path/to/world \
  --candidates candidates.csv --game-jar /path/to/matching-game-assets.jar \
  --out geometry-audit.csv --summary geometry-audit.json
# Optional: compare an estimate CSV with sample_x/sample_z/rotation and projected_base_plate_y
python3 finder.py geometry-audit --world /path/to/world \
  --candidates candidates.csv --game-jar /path/to/matching-game-assets.jar \
  --estimates projected-estimates.csv --out geometry-audit.csv
```

`geometry_status=match` confirms the **saved horizontal start-piece geometry** for that candidate only. `height_error` is estimate minus saved baseplate Y; no measured height is extrapolated to other versions. The optional game JAR check checks vanilla placement parameters against the built-in algorithm but cannot authenticate the archive or its claimed release. **Exact biome/noise generation and full seed-only Jigsaw tower simulation remain incomplete.**

### v2.9.0: Template-derived tower Y relationship (conditional precision)

The tool now reads the version-matched `base_plate.nbt`, `watchtower.nbt`, and `towers.json` to derive the invariant **rigid Jigsaw vertical offset** of the primary watchtower where supported. Known vertical and horizontal rigid connectors are handled; incompatible or ambiguous connectors are rejected instead of guessed.

```sh
# --world-surface-wg must be supplied externally from the SAME VERSION's
# world-generation height oracle, sampled at the projected X/Z position.
python3 finder.py tower-project --version 1.21.8 --seed 123 \
  --chunk-x <candidate-chunk-x> --chunk-z <candidate-chunk-z> \
  --game-jar /path/to/matching-game-assets.jar --world-surface-wg <height> \
  --out tower-projection.json
```

This **does not compute `WORLD_SURFACE_WG` from a seed**. `base_min_y` and `tower_min_y` are conditional results, not certified generated towers. Output classification is always `conditional_on_external_worldgen_height`. The read-only `geometry-audit` additionally checks the saved watchtower's vertical bounding box against the template-derived base/tower relationship. The native `--max-y` cutoff now applies to approximate **baseplate Y** when the original template dimensions are supplied, fixing the one-block boundary error; when dimensions are absent it still applies to approximate terrain Y.

**Remaining requirements:** an exact version-specific Noise/Biome engine, complete Jigsaw random placement/collision handling, and real Mojang server parity datasets. This is not a full no-chunk-generation, cross-version exact-Y solver.

### v2.10.0: Inspect official server bundles directly

The asset reader now accepts an ordinary versioned `server.jar` **without manually extracting its nested game-data JAR**. It inspects structure placement sets, the outpost biome tag, compressed templates and the modern lowercase `id/properties` palette schema. The user-provided **Java Edition 26.3** bundle was inspected: baseplate **16 × 30 × 16**, primary watchtower **15 × 21 × 15**, and a **zero-block conditional vertical offset** from the two horizontally aligned rigid connectors. These are version-specific template facts, **not real-world seed height calculations**.

```sh
python3 finder.py assets-audit --version 26.3 \
  --server-jar /path/to/server.jar --out outpost-assets.json

python3 finder.py candidates --version 26.3 --seed 123 \
  --game-jar /path/to/server.jar --radius 8192 --out candidates.csv
```

The offline audit does not launch Minecraft or generate chunks. The supplied 26.3 JAR declares a **Java 25** runtime requirement. `seed-vanilla` now checks the selected Java executable before launching the game; use the GUI's existing Java executable field to select a compatible installed runtime. Other versions need **matching assets**, not the 26.3 template dimensions.

**Still unimplemented:** an exact seed-only Noise/Biome/`WORLD_SURFACE_WG` engine, complete random Jigsaw placement and collision simulation, and a genuine end-to-end vanilla world comparison. **Offline inspection of the supplied 26.3 JAR is not a Minecraft generation test.** See [server assets documentation](docs/SERVER_ASSETS.md).

### v2.12.0: Vanilla worldgen and Jigsaw resource graph audits

Two new read-only checks inspect matching Mojang `server.jar` files (including bundled game archives). Neither generates chunks nor accepts the Minecraft EULA:

```sh
python3 finder.py worldgen-contract --version 1.21.8 --game-jar ./server.jar --out worldgen.json
python3 finder.py jigsaw-contract --version 1.21.8 --game-jar ./server.jar --out jigsaw.json
```

- `worldgen-contract` follows Noise Router references, validates density/noise asset dependencies and cycles, and records source SHA-256 digests. **It does not evaluate Noise to produce a height.**
- `jigsaw-contract` checks reachable outpost template pools, template NBT and Jigsaw connector references. **It does not replay vanilla Jigsaw RNG, attachment or collision.**
- `certify-samples` checks height witnesses against estimated CSV values while independently reading a matching game JAR. The input files are hashed; `--require-matches` rejects missing or differing predictions without overwriting earlier reports.

```sh
python3 finder.py certify-samples --witnesses witnessed.csv --estimates estimated.csv \
  --game-jar ./server.jar --require-matches --out certification.json
```

**An exact cross-version seed-only Noise/Biome/Jigsaw engine is still not implemented.** Vanilla asset graphs were inspected for the supplied `1.21.8` and `26.3` JARs only. See [validation](docs/VALIDATION.md) for evidence and limitations.

### v2.11.0: vanilla height witnesses and per-sample native comparisons

The new **height witness** workflow helps validate a future exact terrain engine against real Minecraft output. It never invents vanilla samples: the user must first generate and save chunks using the matching game version, then supply that world save. Minecraft server EULA acceptance is always the user's own decision.

The tool verifies the original saved baseplate/tower, the seed-derived rotation and horizontal footprint, and the tower's rigid vertical connection. **Only samples that pass all checks** produce a reconstructed local heightmap observation (`WORLD_SURFACE_WG = base_plate_y + 1`). Missing, incomplete, or mismatched structures are excluded.

```sh
python3 finder.py height-witness --world ./vanilla-world \
  --candidates candidates.csv --game-jar /path/to/server.jar \
  --out height-witnesses.csv --summary height-witnesses.json --require-samples

python3 finder.py compare-witness --witnesses height-witnesses.csv \
  --estimates approximate.csv --out height-diffs.csv --summary height-diffs.json
```

Both commands are read-only with respect to worlds. Comparisons require matching version, seed, sample coordinates and rotation. Even zero error across a finite set of observations **does not establish global or cross-version exactness**. `assets-audit` now recursively expands vanilla biome tags but does not independently sample the biome at a seed-derived position.

The supplied **1.21.8 (Java 21)** and **26.3 (Java 25)** bundled server assets were inspected offline. No actual vanilla world-generation end-to-end test or original saved-world height corpus has been executed or obtained for this release. See [the engine roadmap](docs/EXACT_SEED_ENGINE.md) and [validation report](docs/VALIDATION.md).

### v2.13.0: Finite-area minimum-Y saved-world certificate

The new `region-certificate` command enumerates **every placement candidate** within a specified radius and inspects the corresponding original saved chunk. It refuses to promote a partial sample to a region-wide minimum. For a matching original-game asset JAR, it also checks the saved baseplate rotation/footprint and the watchtower's vertical relationship.

```sh
python3 finder.py region-certificate \
  --world /path/to/offline-world-copy \
  --game-jar /path/to/matching-server.jar \
  --radius 8192 --max-candidates 10000 \
  --out region-report.json --audit region-audit.csv \
  --pending pending-chunks.csv --require-complete
```

The JSON report contains the number of candidate starts, examined/missing origins, all status counts, and the lowest certified baseplate/watchtower Y **only when all origin chunks are complete and all discovered towers pass template geometry checks**. The audit CSV preserves all candidate outcomes. The pending CSV lists only ungenerated or not-yet-FULL candidates for optional subsequent `live` generation. Unexpected, damaged, or geometrically inconsistent chunks are not silently considered absent. A strict incomplete run returns a nonzero exit status while retaining its diagnostic report.

**Scope:** This is a finite-area audit of an **offline, unmodified saved vanilla world**. It neither independently predicts ungenerated terrain from a seed, nor proves an entire world's global minimum, nor determines the minimum pillager spawn Y. The tool checks relevant world files for concurrent changes and rejects attempts to overwrite critical saved-world data. Authenticity of the original save remains a prerequisite, not something its SHA-256 report can establish.

### License

**No redistribution license has been selected for this project.** There is no LICENSE file in the source archive. Readable source does not imply an open-source reuse or redistribution grant. Minecraft and the separately supplied LowYSwampHut project remain subject to their respective terms and rights. This is not an official Mojang product.
