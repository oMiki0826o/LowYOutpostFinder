> 2.0.1：全圖候選搜尋的最近候選證明或逐格完成，只涉及放置嘗試；不得視為世界精確高度或最低刷怪 Y 證據。詳見 [FULL_MAP.md](FULL_MAP.md)。

# 精確免生成高度引擎：工程設計 / Exact seed-only height engine

## 2.13.0 實際可驗證的有限範圍成果

`region-certificate` 可從**原版已生成世界的存檔**證明有限半徑中所有候選起始區塊是否都已檢查，並以 Jigsaw 模板幾何核對產生最低基板／塔樓 Y 的條件式報告。這不會實作 Noise Router 的完整求值，也不會預測尚未生成的結構。必須提供匹配的版本 JAR 與未修改的離線世界。

**Finite saved-region certification is not an independent seed-only worldgen engine.** No change to the six outstanding pure seed-only requirements is claimed.


## 2.12.0 原版資源依賴分析 / Original resource dependency audit

`worldgen_contract.py` 對照原版 JAR 逐一展開 Noise Router 密度函數和噪聲參數；`structure_contract.py` 遍歷可達的 Jigsaw pool 與 NBT 模板；`certification.py` 只比較有限樣本。這些工作解決的是**輸入和資源鏈可檢驗性**，並未解決任何完整 seed-only Noise、Biome、Aquifer 或 Jigsaw RNG 模擬，也沒有新的原版世界生成對拍樣本。

Both dependency analyzers are read-only. Their hashes are useful for detecting drift across versions, NOT as a proof that a generator evaluates the same heights. Their outputs are not a replacement for Mojang runtime parity.

## 2.11.0 原版高度樣本來源 / Vanilla height witnesses

`noise_witness.py` 只從**真實儲存的原版結構**推回原版 Jigsaw 投影時的局部高度（必須同時通過 baseplate 旋轉、水平 BB 和 rigid watchtower 垂直位置檢查）。以源碼的 `projectStartToHeightmap=WORLD_SURFACE_WG` 與 `groundLevelDelta=1`，該原版觀測值是 `base_plate_y + 1`。輸出帶 seed、版號、x/z、旋轉和模板來源雜湊。可對照 C 模型的同一取樣位置；不能將這種**事後量測**冒稱從種子推算原版 Noise。

`biome_assets.py` 會展開同版本 JAR 的標籤巢狀引用，這解決了**原版生態域允許清單**的資料層問題，並未實作 BiomeSource 的抽樣函式。

下一個能真正關閉缺口的驗收方式為：

1. 在 1.21.8 完整重現 `NoiseChunkGenerator.getHeight`、`NoiseConfig` / `NoiseRouter`、`AquiferSampler` 的種子初始化和插值演算法，以相同位置對真實樣本逐筆比較，不能以 26.1.2 C 模型充當 1.21.8 精確結果。
2. 對 Minecraft 1.21.8 真實 `MultiNoiseBiomeSource` 進行同版生態域獨立對拍，再排除不合法結構。
3. 以 `StructurePoolBasedGenerator` 補齊池中所有片段的隨機選擇、轉向、連接、碰撞及 Bounding Box；不能只使用 watchtower 的相對 Y。
4. 取得使用者明確同意 EULA 後在官方原版伺服器上進行多種子、負座標、跨生態域和低 Y 樣本實測，保存世界與樣本雜湊。此步驟不能由資源 JAR 的離線核對取代。
5. 對已驗證的原始樣本給出可重現差異，區分單一版本的有限樣本對拍和完全原版等效；最後才擴大到其餘 1.21～26.x 各版。

**2026-10-13 狀態：上述 1–5 尚未完成。** 上述功能不得在 GUI 標示為已實現，也不能將近似 Y 改名為 `verified_exact`。



## v2.9.0 已達成的明確子問題 / Proven subproblem

已加入從用戶提供的 JAR 中解析 `base_plate` / `watchtower` 之 Jigsaw 連接點、在剛性連接單一 Y 差值可確定時推導塔樓相對基板 Y（不需要計算 Noise，但**需要外部真實 WORLD_SURFACE_WG**）。另有根據提供的 JAR 驗證結構放置常數，並可使用 geometry-audit 從已生成原版 NBT 比較模板起始基板 X/Z 與預測幾何；實際高度誤差也可以匯出。另已加入起始模板從對應 JAR 載入、`setCarverSeed` 隨機旋轉和 `StructureTemplate.createBox` 中心 X/Z 的 Java/Python/C 對照測試。高度仍來自未對拍的 C 模型；完整 Jigsaw 子片段與跨版本 Noise/Biome 仍不精確。詳見 [PROJECTED_START](PROJECTED_START.md)。

**The invariant rigid tower-to-base vertical offset can be derived conditionally from compatible templates. Exact terrain height, successful complete Jigsaw generation, and final tower Y are NOT yet vanilla-verified.**

## 2.10.0 進展 / Progress

已實際檢查使用者提供的 Minecraft Java 26.3 `server.jar`：從內層 JAR 讀取結構設定、標籤及新 NBT 方塊狀態格式；能推導相容模板的水平連接相對 Y，但仍**不能計算原版 WORLD_SURFACE_WG**。相關實驗只檢查資源，未啟動伺服器。/ The supplied 26.3 server assets were inspected offline (including modern NBT palette IDs and horizontal connectors); exact seed-only terrain generation and vanilla E2E remain unverified.

## 目前的限制 / Current status

**尚未完成。** 本文件描述要達成「Java 版本 + 種子 → 不儲存／不生成完整區塊 → 精確前哨站基板與瞭望塔 Y」所缺少的原版相容性。它不是已通過測試的功能，也不等於聲稱找到負 Y 前哨站。

**Not implemented.** This design describes what would be required for accurate, no-full-chunk-generation vanilla-equivalent outpost Y. It is not a tested claim of support.

## 必須重現的生成階段 / Required calculations

1. **Placement**：依版本的 `RandomSpreadStructurePlacement`，包含 spacing/separation/salt、frequency reduction 與附近村莊候選排除。已提供候選演算法；只證明搜尋「候選」，不代表最終生成。
2. **Biomes**：各版本 MultiNoise 生態域、1.21+ 可生成前哨站的 tag，以及原版結構可否生成判定。不能僅從名稱推斷所有 1.21.x 或 26.x 必然相同。
3. **Exact `WORLD_SURFACE_WG`**：使用原版生成器 `getHeight(..., WORLD_SURFACE_WG, ...)` 相同的 noise router、aquifer 和 heightmap block predicate。**不是**讀既有區塊地表高度；不應以單一候選區塊中心 X/Z 代替 Jigsaw 模板 bounding box 中心。
4. **Jigsaw & template data**：複製對應版 `pillager_outpost/base_plates` pool、模板尺寸、隨機旋轉、地面高度修正以及從基板接上的瞭望塔片段位置。原版 `StructurePoolBasedGenerator.generate` 會根據起始片段經旋轉後的 bounding box 中心計算投影點，之後再修正 Y；因此單筆 Noise Y ≠ 塔樓實際 Y。
5. **驗證 / Validation**：對每個支援的遊戲版本使用多種正負 seed、負座標、跨生態域、極端地形，與同版 Mojang 伺服器或可觀測的原版生成結果逐筆比較位置、tower/base bounding box。任何不一致均不得標示 `verified_exact`。

## 演算法與效能 / Suggested implementation

候選掃描（快速）→ 正確的生態域／placement 過濾（快速）→ 只對有效候選做 `WORLD_SURFACE_WG` 種子高度查詢（相對耗 CPU）→ 模板旋轉與 Jigsaw 片段推導（通常小於地形花費）→ 按精確基板 Y 排序。不同世界版本以明確的版本適配層管理地形設定與模板變更，不把某版檢驗結果推廣到所有版本。

* 目標是**不進入全區塊生成／磁碟儲存流程**，但仍須實際計算局部的 Noise / 高度資訊，CPU 成本不可能是零。
* 高度查詢應保留同一世界種子的快取／Noise 設定，避免每次建置；分批工作可停止、可記錄進度。
* 先驗證單版（1.21.8），再對其他版逐一比對，不使用無證據的共用版本標籤。
* `height_audit.py` 的估測誤差統計是校準依據；有限對拍就算全部差零，也**不能**證明全域精確。

## 原始碼依據 / Source basis

使用者提供的 `minecraft-source.zip` 包含 `JigsawStructure.java`、`StructurePoolBasedGenerator.java`、`NoiseChunkGenerator.java`。已檢查 `StructurePoolBasedGenerator.generate` 使用**起始 pool 片段旋轉後 bounding box 中心** `(i,j)` 去呼叫 `chunkGenerator.getHeightOnGround`，再以 `groundLevelDelta` 平移。因此目前 `outpost_scan.c` 只對區塊中心 `(x+8,z+8)` 抽樣的結果，明確不夠精確。

The supplied Java sources show that Jigsaw projection samples at the rotated start-piece bounding-box center, not necessarily the origin chunk center. A whole-version noise, biome and Jigsaw-compatible implementation remains necessary.
