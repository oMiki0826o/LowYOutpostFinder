# 原版 Jigsaw 起始基板投影 / Vanilla Jigsaw start-piece projection

## 中文

**驗證範圍：Java RNG 與基板 X/Z 幾何。非 Minecraft 真實 Y 驗證。**

前哨站 `minecraft:jigsaw` 的 `start_height.absolute=0` 且 `project_start_to_heightmap=WORLD_SURFACE_WG`。

1. `Structure.Context.createChunkRandom` 使用 `CheckedRandom(0)`，先以世界種子產生兩個 `nextLong`，再以 `(cx*long1) ^ (cz*long2) ^ worldSeed` 重新播種（按 64 位溢位）。
2. `BlockRotation.random` 從 `NONE`、`CLOCKWISE_90`、`CLOCKWISE_180`、`COUNTERCLOCKWISE_90` 四方向選一。
3. 讀取使用者提供的同版 JAR 的 `data/minecraft/worldgen/structure/pillager_outpost.json`、`template_pool/pillager_outpost/base_plates.json` 與 `structure/pillager_outpost/base_plate.nbt`。僅接受單一 rigid base_plate 起始池及所要求的投影類型；拒絕不支援的資料。
4. 運用 `StructureTemplate.createBox` 相同的鏡射 NONE／中心樞紐 ORIGIN 旋轉規則，求原版 `[(minX+maxX)/2,(minZ+maxZ)/2]`（Java 整數除法朝 0 取整）。
5. 選用的 LowYSwampHut C 核心在上述 X/Z 查詢 **模型預測** 的 `WORLD_SURFACE_WG`；在原版 `PoolStructurePiece.getGroundLevelDelta()=1` 的前提下，推導 `projected_base_plate_y = height-1`。

### 仍缺少的部分

- C 核心目前不是已證實對應 1.21.8 的原版 Noise/含水層引擎；跨版參數與 JAR 版號匹配尚無完整官方對拍。
- 尚未完整模擬 Jigsaw 子模板的連接、旋轉、碰撞與最終瞭望塔 Bounding Box。
- 原版結構有效性還取決於起始位置的生態域及其他條件。試驗性生態域篩選**預設關閉**，以免因近似模型漏掉實際低 Y 候選。
- `estimated_only` 永不代表確認生成；要求確定 Y 時，必須使用同版原版伺服器或已有存檔核對。

### 自動測試

- `tests/StartProjectionOracle.java` 與 Python 的種子／旋轉／取樣座標逐筆比較。
- C scanner 與 Python 起始投影實作比較 5 組正負極端種子。
- 人工壓縮的 JAR/NBT fixture 測試讀取與拒絕資料錯誤；**不能替代真實官方 JAR/伺服器**。

## English

**Verified scope: Java RNG and X/Z start-piece geometry only. NOT a vanilla-height proof.**

For a single rigid baseplate pool with `start_height.absolute=0` and `WORLD_SURFACE_WG` projection, the context RNG calls `setCarverSeed(seed,chunkX,chunkZ)`, a random rotation is selected, and the native height model is sampled at the **rotated start template bounding box center**, not the chunk center. Java integer division truncates toward zero. The template width/depth comes from the corresponding user's game assets JAR; unrecognized data is rejected.

`projected_base_plate_y` is the modeled height minus the initial pool piece's ground-level delta (1). It is an **estimate**, not a saved-tower coordinate, and is **not** proven version-exact. Biome restrictions and the complete Jigsaw child-piece process are not yet modeled or validated for all requested versions. The user's official game JAR is never run by the metadata parser. For an actual Y, verify against a generated vanilla structure.
