# LowYSwampHut 2.0.1 功能對照 / Feature comparison

本表參照使用者提供的 LowYSwampHut 2.0.1 原始碼與 README；不是對外部專案品質的獨立認證。
This table compares against the user-provided LowYSwampHut 2.0.1 archive and README.

| 參考工具功能 / Reference feature | LowYOutpostFinder v2.8.0 | 註記 / Notes |
| --- | --- | --- |
| 單一世界種子搜尋 / Single seed | ✓ | 候選座標 / Placement candidates |
| 種子清單批次 / Seed-list batch | ✓ | UTF-8 text, comments, duplicate removal |
| 遊戲版本選擇 / Version selection | 部分 / Partial | Candidates: 1.21–26.3; approximate Y: 1.21.8 only |
| 矩形搜尋區域 / Rectangular area | ✓ | 512-block region indices; capped per invocation |
| 世界邊界重設 / World-boundary reset | ✓ UI | Setting whole border triggers safety cap; subdivide to scan |
| 並行執行 / Threads | 部分 / Partial | Parallel **seeds**, not multithreaded C scanning of one seed |
| 暫停／繼續／停止 / Pause/resume/stop | 部分 / Partial | Pauses before new work; in-flight native job finishes; cancellation terminates it |
| 進度與剩餘時間 / Progress + ETA | 部分 / Partial | Per seed or rectangular-row; native job gives no inner progress |
| 低 Y 篩選 / Low-Y filter | 試驗性 / Experimental | 1.21.8 **approximate surface**, not actual outpost Y |
| 依 Y 排序 / Sort by Y | 試驗性 / Experimental | Only estimated or vanilla-verified rows; never placement-only rows |
| 依原點距離排序 / Sort by distance | ✓ | Coordinate-derived |
| 匯出全部結果 / Export results | ✓ | CSV |
| 匯出命中種子 / Export seeds | ✓ | Text, unique seeds |
| `/tp x y z` / Teleport command | 僅已驗證 / Verified only | No invented Y for provisional results |
| 原版確切結構 Y / Exact generated structure Y | **未完成 / Missing** | Saved-world NBT verification exists; no seed-only exact Jigsaw engine |
| 原版生態域 + 地形 + Jigsaw 模擬 / Vanilla-equivalent worldgen | **未完成 / Missing** | Reference swamp-hut algorithm **cannot** directly model outpost Jigsaw |
| 最低有效掠奪者生成 Y / True lowest valid spawn Y | **未完成 / Missing** | Requires independent original-game spawning criteria |

## Why the height algorithm cannot simply be copied

A swamp hut is a traditional fixed-footprint structure. The supplied reference computes a footprint average using `MOTION_BLOCKING_NO_LEAVES` after carvers, then grades cave-created low terrain. A pillager outpost uses the **Jigsaw** structure type and the **`WORLD_SURFACE_WG`** projection, with a rotated start-template bounding box, ground-level adjustment, biome validation, and subsequent pieces. The type of heightmap and phase of world generation are not interchangeable. Exact seed-only outpost Y requires version-specific worldgen and Jigsaw-template parity, verified against official saved structures. A comparison of estimated pre-carver surface Y is **not** an accuracy proof.

## Search completeness and practical limits

A region rectangle represents all placements in the chosen region grid, but these are **attempt coordinates** and must pass vanilla biome and Jigsaw rules before becoming a real outpost. Candidate scans exclude placements near village **candidates**, not guaranteed actual villages. The GUI caps a single region scan at 5,000,000 regions and at most 50,000 retained rows per seed. Set a narrower area or increase the per-seed cap (to 50,000) if there are too many results; the scanner errors rather than silently truncating.

Native batch mode uses the built `bin/lowyoutpost` optional backend, which is not shipped in the source-only ZIP. Build from a separately supplied LowYSwampHut archive. Only Java 1.21.8 is exposed for experimental Y; no other version should be advertised as exact.

### v2.7.0 追加 / Addendum

已支援讀取使用者提供的遊戲資源 JAR 中原版 `base_plate.nbt` 長寬，並透過 Java RNG 得到起始投影 X/Z；**高度仍為未驗證的 Noise 推算，不能以此宣布真正的最低 Y。**

A matching assets JAR now supplies the start-template size; start-piece sample X/Z matches the independent JDK oracle. The modelled Y remains provisional.

### v2.8.0 追加 / Addendum

新增結構起始基板的原版存檔 X/Z 幾何對照、樣本 Y 誤差統計及從遊戲資源 JAR 驗證候選結構參數的功能；仍缺少精確 Noise/生態域與完整 Jigsaw 子結構。

Saved-NBT Jigsaw horizontal footprint audit and placement-parameter validation are available. No release-wide seed-only exact-height claim is made.
