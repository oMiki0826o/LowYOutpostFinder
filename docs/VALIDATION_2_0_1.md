# v2.0.1 檢驗紀錄與精確性邊界

本紀錄對應 2026-10-13 的 v2.0.1 本地原始碼修訂，主要涵蓋低記憶體的全圖放置候選搜尋。它不是原版 Minecraft 免生成精確高度引擎的認證。

## 已實際執行

- `python -m compileall -q -x '(\.build|__pycache__)' .`：成功。
- `xvfb-run -a python -m unittest discover -s tests -v`：**208 項執行，0 失敗、0 略過**。包括雙語 GUI、原版幾何、保守結果分類、全圖掃描與續跑。
- `python -m unittest discover -s tests -v`：**204 項執行，0 失敗、13 略過**；缺少可用圖形顯示的 Tk 測試依環境略過。
- `python scripts/build_region_scan.py`：獨立 C11 原生掃描器編譯成功。
- `sh build.sh /mnt/data/LowYSwampHut-main.zip`：使用使用者提供的新版 upstream ZIP 成功編譯既有近似地形核心。
- `python tests/check_placement.py bin/lowyoutpost`：5 組 signed Java long 種子候選位置參考結果全部吻合。
- `python finder.py assets-audit --version 1.21.8 --server-jar 'server (1)(1).jar' ...`：實際解析使用者提供的 1.21.8 原版資源，通過離線資源核對。
- `python finder.py full-map --version 1.21.8 --seed -123456789 --strategy nearest --top 100 --game-jar 'server (1)(1).jar' ...`：**13,733,261,721** 個可能網格中，透過距離下界僅實際檢查 **732 個**網格，證明 100 個**放置候選**在距離意義上的最近排序；沒有計算 Y。
- `python finder.py full-map --version 1.21.8 --seed 123 --strategy exhaustive --engine native --batch-regions 500000 --max-batches 1 ...`：實際檢查 **500,000 個網格**、找到 **44,077 個放置候選**，狀態正確標示 **`incomplete`**。
- 更換同一工作的 `--engine python` 並以 `--resume` 接續 10,000 個網格：已掃描 **510,000 個網格**，狀態仍為 **`incomplete`**。
- `scan_nearest()` 另與完整 Python 候選枚舉比較 **500 組隨機矩形、種子與搜尋中心**，均得到相同的最近候選結果；負座標的放置網格間隙案例另有專屬回歸測試。

## 不得混淆的宣稱

- `proven_nearest_placement_only`：只表示比過空間距離下界、找到最接近中心的種子放置候選，不是 Minecraft 實際結構高度或世界最低 Y 的證據。
- `complete`（全圖逐格）：只證明所有選定放置網格都已檢查。它不代表生態域、Noise、高度及 Jigsaw 已完成。
- `incomplete`：未檢查全部網格；目前 CSV 只是已檢查部分的最佳排名，**不可用為全圖結果**。
- 目前仍缺原版 1.21.8 完整 `NoiseChunkGenerator`、`WORLD_SURFACE_WG`、`AquiferSampler`、`BiomeSource` 與完整 Jigsaw 隨機碰撞模擬。
- 尚未以原版伺服器實際生成世界進行端到端對拍。使用者雖提供 `server.jar`，但本次**未代為同意 Minecraft EULA**。沒有產生原版真實結構世界樣本，也沒有將它冒稱為已驗證。
- 源碼發行版不包含 Mojang server.jar、已生成世界或第三方 LowYSwampHut 原始碼，使用者可以單獨提供來源檔進行建置。

詳細使用方式見 [FULL_MAP](FULL_MAP.md) 與 [ROUTES_AB](ROUTES_AB.md)。
