# Changelog

## Unreleased — 2026-10-13（專案架構與啟動流程重構）

- 根目錄收旂為唯一 `LowYOutpostFinder.py` GUI 啟動檔；進階 CLI 改為 `python -m lowy_outpost_finder`。
- 應用程式移入 `lowy_outpost_finder/` 正式套件，統一路徑解析與子程序入口。
- 原生原始碼收旂至 `native/src/`，建置統一為 `scripts/build_native.py`，並新增零第三方依賴清單。
- 分離 headless 與 Linux Xvfb Tk 測試，避免 macOS/Python 3.13 的 Tcl 非主執行緒回收問題。
- AI 協作文件集中在已忽略的 `data/`，並從發布封裝明確排除。

## 2.0.1 — 2026-10-13（全圖候選搜尋與低資源使用）

- 新增 `full-map --strategy nearest`：針對整張地圖以放置網格的距離下界證明最近 N 個候選，不必掃描全世界每一個網格，也不生成 Minecraft 區塊。
- 新增 `full-map --strategy exhaustive`：世界邊界內 13,733,261,721 個候選網格的逐格搜尋，分批且常數級結果儲存，提供原子 JSON 檢查點／續跑／CPU 休息間隔。
- 額外支援使用者提供的 `LowYSwampHut-main.zip` 做為既有地形近似核心的編譯來源；ZIP 展開會拒絕路徑穿越、符號連結與超大檔案。
- 新增純 C11、單執行緒原生掃描器 `native/src/region_scan.c` 與選用建置腳本；從負座標及 signed 64-bit 種子對照 Python 參考公式。
- GUI 新增雙語全圖模式、最近或逐格策略、原生／Python 引擎、批次大小、CPU 休息、續跑與真實逐格進度。
- 修正最近候選搜尋起點落在區域網格間距空隙時的漏查，加入隨機矩形完整枚舉對照測試。
- 結果永遠是 `placement_candidate`，不推論原版 Biome、Noise、Jigsaw、實際塔樓 Y 或刷怪 Y；未宣稱完成所有精確免生成演算法。


## 2.0.0 — 2026-10-13（A/B 工程版，**非**精確免生成 Y 最終版）

- 修正自訂搜尋中心回傳的已檢查候選重新依世界原點排序、導致最近結果證明順序錯誤；實測稽核保留原驗證順序，僅匯出的人工檢視 CSV 依世界原點排序。新增可重現的紅燈→綠燈測試。
- 修正 `seed-vanilla` 在非原點中心且半徑較小時，仍用 `(0, 0)` 做候選前置檢查、誤拒絕合法候選；新增單點中心回歸測試。
- 原版執行前 `server-check`：不啟動 Minecraft，檢查 JAR 版本／放置參數／Java 主版本並輸出 SHA-256；GUI 顯示真實逐筆檢查進度。
- 路線 A：可自訂中心，按近距候選掃描；新增 `--offset` 分批、`--checkpoint` 每筆原子 CSV 快照、`--sort-by` 實測塔樓／基板高度排序及 `--summary` JSON 完整性判定。
- 路線 B：新增 `seed-geometry`，以同版原版資源 JAR 計算 Placement 候選與 Jigsaw 起始旋轉／高度圖取樣 X/Z，**不虛構 Y**。
- 修復非原點搜尋時，結果中的世界原點距離與自訂中心距離混淆問題；增加 `search_distance_sq` 欄位，不改變既有 `distance_sq` 意義。
- GUI 加入種子幾何、中心 X/Z、偏移量與已驗證結果排序，支援繁體中文／英文；擴充跨負座標與中斷後進度保留測試。
- 原版 1.21.8 JAR 離線資源核對與純種子模板座標測試；**未**執行需要 Minecraft EULA 的原版伺服器端到端世界生成。
- 精確 Noise／Biome／Aquifer、完整 Jigsaw 子片段及原版端到端對拍仍未完成；詳見 docs/ROUTES_AB.md。

## 1.0.1 — 2026-10-13

- Fixed a confirmed early-stop bug: a verified watchtower must satisfy both `structure_center_y < threshold` and `base_plate_y <= max_y` when both filters are set, including already-saved chunks.
- Added one shared acceptance predicate and an evidence-based nearest-result report. Earlier unresolved candidate chunks prevent "nearest" claims.
- Added the full structure bounding-box center and distance-squared fields to saved NBT exports, with cautious handling of invalid heights.
- Improved bilingual Tk GUI with responsive two-column mode selection, tabbed results/logs, an in-app quick guide, preview classification colors, a visible result count, collapsible search settings, and adjustable structure-center threshold.
- Corrected CI Java 21 provisioning; removed dependence on local Java versions in unit tests; made POSIX shell-fixture tests explicitly conditional; addressed Windows path/CRLF differences.
- Updated bilingual README, user manual, tests and release packaging. The precise, no-chunk-generation Noise/Biome/Jigsaw engine remains **unimplemented**.

## 1.0.0 — 2026-10-13

- First public MIT-licensed release based on previously developed 2.13.x experimental sources.
- Seed-derived placement candidates, offline NBT validation, optional experimental native height estimate, and same-version temporary vanilla-server verification.

Previous research-version entries (2.x engineering iterations before 1.0.0 public release) are preserved in [development history](docs/DEVELOPMENT_HISTORY.md). These do not denote newer public releases.
