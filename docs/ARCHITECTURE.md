# 架構與設計取捨

這是一個偏重「可反查證據」而非純粹猜測世界結構 Y 的工具。以下說明目前實作，不是未完成的功能清單。

## 資料流程

1. `LowYOutpostFinder.py` 是根目錄唯一 GUI 入口；`python -m lowy_outpost_finder` 提供進階 CLI。兩者都只委派給 `lowy_outpost_finder/` 套件。
2. `lowy_outpost_finder/cli.py` 依種子與已採用的 `RandomSpreadStructurePlacement`、`legacy_type_1` 頻率及村莊排除規則，計算前哨站結構 *嘗試* 座標。此階段不載入遊戲地形。
3. `versions.py` 限定 UI 可選版號，並從 `level.dat` 的 `Version.Name`、`DataVersion` 取得世界版本；讀取已保存的區塊時另比對 DataVersion。
4. `nbt.py` 唯讀解壓縮、解析 NBT 和 Anvil `region/*.mca`。`cli.WorldChunks` 避免同時開啟很多 region 檔；結構片段的 Y 取自儲存於 FULL 區塊的包圍盒。
4. `live.py` 在使用者明確要求下，以 RCON 在同種子伺服器上生成候選區塊，再執行 `save-all flush`，等區塊存至磁碟後核對。使用前必須備份，非本機 RCON 未加密。
5. `i18n.py` 提供完整繁體中文／英文 GUI 訊息對照，語言切換不修改 CSV 欄位或既有表單值。`gui_model.py` 僅檢查表單和建立 CLI 參數；`gui.py` 以獨立 Python 子行程執行，視窗可取消並檢視 CSV。子行程成功後才顯示搜尋結果。

6. `vanilla_oracle.py` 新增 `seed-vanilla`：啟動使用者提供的版本相符原版 JAR，短暫建立世界並用本機 RCON 執行 `run_search_live`；透過 `try/finally` 停止 Java 與清除世界。只保留 CSV。此路徑具有原版生成階段，並非免生成的精確地形計算。
7. `native/src/outpost_scan.c` 透過另外編譯的 LowYSwampHut 核心提供僅限 1.21.8、無需世界存檔的近似地表推算；GUI 的 `estimate` 模式及 CLI 可呼叫它。CSV 明確使用 `estimated_only`，不得視為 `verified_tower`。

## 開發治理邊界

- 公開架構、使用與驗證文件放在 `docs/`。
- AI 協作規格、執行計畫與本機狀態只存於已忽略的 `data/`，不得進入 Git 或發布包。
- 重構必須保留證據分類與 fail-closed 邊界；不得將候選或近似結果升級為原版已驗證結果。
- CI 將 headless 測試與真實 Tk 測試分離；Tk 測試只在 Linux Xvfb 中以獨立程序執行。

## Jigsaw 結構的 Y 如何決定？

對照提供的 Minecraft 原始碼 `JigsawStructure#getStructurePosition` 與 `StructurePoolBasedGenerator#generate`：候選區塊先決定起始位置 `chunkX*16, 0, chunkZ*16`；接著根據 `base_plates` 池選擇起始片段與隨機旋轉，求其 Bounding Box **中心的 X/Z**；使用 `WORLD_SURFACE_WG` 查詢該處地面高度，再依起始片段的 `GroundLevelDelta` 平移起始片段。後續瞭望塔是由 Jigsaw 連接而生成的另一個片段。簡單對單一種子採樣某個方塊的地表高度，不等於實際 Base Plate Y，更不等於瞭望塔最低 Y。

`vanilla_oracle.py` 的策略是隔離啟動使用者提供的同版原版伺服器，讓**真正的原版引擎**處理 Noise、Biome、Jigsaw，再藉由 `nbt.py` 唯讀驗證存檔。它需要實際生成區塊；不能稱為不生成區塊的確定性公式解。

## 為什麼不直接顯示最低 Y？

`WORLD_SURFACE_WG` 是世界生成階段的高度圖，不是後來地形雕刻出的洞穴底部；產生最低 Y 需要版本一致的地形演算法與 Jigsaw 投影計算。現有跨版候選只保證「程式計算符合 placement 公式」，不能由此推論結構存在或塔樓低於 Y=0。對於不祥之瓶農場，實際有效刷怪高度也不同於結構 base plate 最小 Y。

## 防止誤判的設計

- CSV 使用狀態而不是布林值：`placement_candidate`、`verified_tower`、`verified_start_only`、`not_generated`、`absent`、`version_mismatch`、`invalid_region` 等具不同意義。
- 不接受跨種子、跨版本的候選 CSV 進行世界核驗；無版本的舊式 CSV 應重新生成。
- RCON 生成前再驗證候選是否符合 placement，避免無意載入 CSV 內任意座標。
- 大範圍搜尋與 RCON 批次數有上限，避免耗盡磁碟／CPU。
- 成功結果用暫存檔完成後原子置換，失敗或中斷時不發布半套 CSV。
- 無法完整解析的 region 或混版 chunk 會使 `world` 全量掃描失敗；`verify` 模式適合輸出個別位置的錯誤狀態。

## 原版對拍待辦

使用者提供受支援版本的 Mojang 原版伺服器 JAR 並遵守 EULA 後，針對各版本記錄官方版號、世界種子、區塊座標、結構片段 Bounding Box 和實際遊戲畫面，才可升級成具實證的高度搜尋器。此專案沒有先假設原版端到端測試已通過。

## 臨時伺服器的安全界線

- 版本由 `server.jar` 內的 metadata 檢查，但無法驗證下載來源真偽，不應執行不可信的 JAR。
- EULA 需由使用者明確勾選或提供 `--eula-accepted`；程式不會偷偷表示接受。
- RCON 使用隨機憑證、loopback；臨時世界放在私有的暫存目錄，正常結束時清除，CSV 在指定位置保留。
- SIGTERM（macOS/Linux）轉為清理流程；Windows 強制停止程序可能中斷 Python 清理，因此需要檢查是否有殘留 Java 子程序。
- 每次最多生成 256 筆候選；搜尋結果只代表抽樣結果，不代表已找到世界的全域最低 Y。

## v2.4 增補：前置排序、量測與對拍

`seed-vanilla --priority terrain`（1.21.8 限定）將 `core_archive` 與 `terrain` 排序傳給既有 `run_search_live`，於生成任何候選區塊前執行低地形排序。此模式可能漏掉真正最低 Y，仍然必須經由原版存檔 `verified_tower` 檢查；`near-origin` 是預設的保守順序。

`height_audit.py` 比較 `estimated_only` 與 `verified_tower` 的同一版號／種子／區塊，輸出絕對誤差、平均誤差與跳過數量，沒有虛構未驗證候選的高度。`scripts/benchmark.py` 實際量測位置與試驗性地形搜尋的耗時，不模擬、不預測原版 Java 的執行時間。

完整的免生成算法尚未加入；技術規劃與必要的版本／Jigsaw 對拍條件列於 [精確引擎設計](EXACT_SEED_ENGINE.md)。
