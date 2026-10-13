# 全圖搜尋：使用方式與演算法說明

LowYOutpostFinder 2.0.1 的全圖模式**不啟動 Minecraft、不生成地圖、不需要存檔或接受 EULA**，只由 Java 世界種子推導前哨站的 **placement 候選**。它不會確認生態域是否允許該結構，也**不能提供實際塔樓 Y**。這是功能邊界，不是搜尋錯誤。

## 一分鐘操作

在專案根目錄執行：

```sh
python3 -m lowy_outpost_finder full-map --seed 123 --version 1.21.8 \
  --strategy nearest --center-x 0 --center-z 0 --top 100 \
  --out results/nearest.csv
```

指令遍歷**必要的** 512×512 方塊結構放置網格，以每格內可能起始座標的距離下界，排除無法擠入前 100 名的其他區域。即使世界非常大，通常只需檢查數千格。結果 CSV 的 `classification` 固定為 `placement_candidate`；`distance_sq` 為與自訂搜尋中心的水平距離平方。

查閱 `results/nearest.state.json`：

- `status=proven_nearest_placement_only`：前 N 個候選在**結構放置公式的意義**上已證明是指定搜尋區域最近者，不是全部世界結構真實存在的證據。
- `visited_regions`：實際運算的網格數量；遠小於全部可能網格數屬正常情況。
- `maximum_retained_distance_sq`：目前第 N 個候選的距離平方。
- `nearest_lower_bound_sq`：未走訪網格中距離下界最小值，必須嚴格大於第 N 名的距離平方才能使用提前停止的最近候選證明。

**不要將這個檔案當成「最低 Y」榜單。** 種子候選沒有可信賴的 Y。

## 完整逐格模式

若想查遍所有 X/Z 世界邊界內的 placement 網格，使用：

```sh
# 可選。macOS / Linux 需要 Xcode CLT 或 cc/clang；Windows 需要 MinGW gcc/clang。
python3 scripts/build_native.py region

# 舊有的地形近似模式也可選用 LowYSwampHut-main.zip 編譯：
# python3 scripts/build_native.py terrain /path/to/LowYSwampHut-main.zip

python3 -m lowy_outpost_finder full-map --seed 123 --version 1.21.8 \
  --strategy exhaustive --engine auto --top 100 \
  --batch-regions 500000 --cpu-rest-ms 150 \
  --out results/all-cells.csv
```

`--engine auto` 有 `bin/region_scan`（Windows 為 `.exe`）時使用單執行緒純 C11 加速器；否則回退 Python，速度會明顯降低。此模式仍只輸出**最近的 100 筆候選**，不將數億筆候選全部寫入磁碟。

掃描 X/Z 兩軸完整範圍，實際要處理 **13,733,261,721 個放置網格**。在一般電腦上，這不是瞬間完成的工作；大量批次仍會耗費處理器時間。`--cpu-rest-ms` 只會在每批之後暫停一段時間，降低持續占用，不會減少總計算工作。

全圖掃描會持續更新：

- `results/all-cells.csv`：目前排名前 100 的候選，尚未完成時只是局部結果。
- `results/all-cells.state.json`：掃描參數摘要、`processed_regions`、`total_regions`、`placement_candidates`、`status`。

**只有 `status=complete` 才代表已走訪所選範圍內的全部放置網格**。中斷前保存的狀態會是 `incomplete`。想繼續，只需要相同參數與路徑：

```sh
python3 -m lowy_outpost_finder full-map --seed 123 --version 1.21.8 \
  --strategy exhaustive --engine auto --resume \
  --out results/all-cells.csv
```

檢查點允許調整 `--batch-regions`、`--cpu-rest-ms`、`--engine`，不允許在同一工作中修改種子、版本、搜索邊界、搜尋中心或前 N 筆數。已存在結果時，不加 `--resume` 不會覆蓋資料。

## 只搜尋世界的一塊區域

```sh
python3 -m lowy_outpost_finder full-map --version 1.21.8 --seed -123456 \
  --x-min -100000 --x-max -50000 --z-min 20000 --z-max 90000 \
  --center-x -75000 --center-z 55000 --top 50 \
  --strategy nearest --out results/rectangle.csv
```

矩形邊界與搜尋中心都必須在有效前哨站起始方塊範圍 ±29,999,984 內。負數請保留符號。兩種模式會把超過世界邊界的候選排除。

## GUI 操作

1. 在專案目錄執行 `python3 LowYOutpostFinder.py`，選擇「全圖候選（免生成）」。
2. 選 Minecraft 版本、種子，以及可選的中心 X/Z；「只保留最近 N 筆候選」推薦先設 100。
3. 預設 `nearest`：不必設 Java、JAR、Y、記憶體與續跑。按開始後可預覽 CSV。
4. 如果需要盤點全部網格，切到 `exhaustive`；建議先執行可選 C 掃描器建置，並保留 `auto` 引擎。
5. 要從中斷處繼續，使用原本的 CSV 輸出路徑、相同種子與中心，選 `exhaustive` 並勾選「續跑」。
6. 有效的暫停方法是按「停止」：會在目前批次邊界保留已提交檢查點（強制結束不保證當批完成）。

## 效能及安全

- 全圖最近候選以幾何剪枝快速結束；全圖逐格是完整工作量，不會謊稱可免代價即時完成。
- GUI 使用子行程，Python／C 掃描器均為單工作執行，避免同時占用多個 CPU 核心；記憶體主要與 `--top` 筆數、最近模式的小型搜尋前緣有關。
- 建議低效能電腦使用 `--top 100`、`--engine auto`、`--batch-regions 500000`、`--cpu-rest-ms 150`。純 Python 逐格掃描可運作但可能非常慢。
- 以原子檔案方式儲存檢查點與 CSV；如果在兩次原子寫入間崩潰，可透過 `--resume` 由檢查點重新寫出 CSV。
- 不寫入任何世界檔案，也不會連接網路。僅 `seed-vanilla`／`search-live` 等原版驗證模式會生成世界或連接伺服器。

## 與真正「最低 Y」的差別

這一版仍**沒有**完全精確的 `NoiseChunkGenerator`、`WORLD_SURFACE_WG`、`BiomeSource`、`AquiferSampler` 以及完整 Jigsaw 隨機拼裝與碰撞的免生成模型。原版驗證路線 A 可使用本人接受 EULA 後的同版伺服器，實際生成區塊再驗證存檔 Y；近似地形路線 B 不可當作真實高度。即使全圖逐格搜尋已完成，也只是全圖 placement 候選的集合與最近排名。

## English quick reference

- **Whole-world nearest placement, no chunks:** `python3 -m lowy_outpost_finder full-map --seed 123 --strategy nearest --top 100 --out nearest.csv`
- **Every placement cell, resumable:** `python3 -m lowy_outpost_finder full-map --seed 123 --strategy exhaustive --out all.csv`
- **Build optional native C11 accelerator:** `python3 scripts/build_native.py region`
- **Resume matching job:** add `--strategy exhaustive --resume` with the exact same path and query settings.
- **CPU rest:** `--cpu-rest-ms 150` (exhaustive only).
- **Proof boundary:** `proven_nearest_placement_only` proves nearest seed-derived placement candidates, not generated outposts or exact tower Y.
