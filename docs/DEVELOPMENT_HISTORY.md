# Changelog

## 2.13.0 — 2026-10-13

- Implemented **finite-area saved-world minimum-Y certification** that enumerates all seed-derived candidate origin chunks in a user-bounded radius; no silent sampling/truncation.
- Added strict matching-version template geometry and rigid watchtower checks. Missing or invalid chunks prevent any certified minimum; a partial scan reports observed heights only.
- Added `--pending` export to drive subsequent exact vanilla generation of missing FULL chunks, as distinct from corrupted/ambiguous data.
- Added safeguards for concurrent world file modification, inadvertent world-save overwrite, output path collisions and oversized scans.
- Added thirteen new test-first regression cases and updated bilingual usage/reference documents.
- **The independent precise 1.21–26.x seed-only Noise/Biome/Jigsaw engine is still NOT implemented; the new certificate applies only to a saved, verified finite region.**


## 2.12.0 — 2026-10-13

- Added bounded, version-checked Noise Router dependency traversal (`worldgen-contract`) with cycle detection and deterministic source digests. No new height predictor is claimed.
- Added reachable Jigsaw template-pool and NBT dependency traversal (`jigsaw-contract`), including all four original 1.21.8 / 26.3 outpost pools and eleven template files; no replay or collision simulation is claimed.
- Added `certify-samples` with matching JAR provenance, finite-sample status, and content-hashed input reports.
- Fixed a real data-loss bug: `height-witness --require-samples` and `compare-witness --require-samples` now fail before overwriting existing reports when no samples exist.
- Added regression tests, bilingual README explanations and original JAR contract fixtures.
- Exact biome noise sampling, `WORLD_SURFACE_WG`, full Jigsaw simulation, no-generation precise Y and vanilla world end-to-end parity remain incomplete.

## 2.11.0 — 2026-10-13

- Added `height-witness` to derive a single-sample WORLD_SURFACE_WG value only when a saved vanilla Jigsaw start passes horizontal and vertical geometry checks; insufficient evidence is never promoted to an exact result.
- Added `compare-witness` for strict seed/version/sample-position comparison of tentative native heights against measured saved vanilla Jigsaw bases. Emits signed errors and completeness statistics.
- Added recursive, bounded, cycle-safe expansion of nested original biome tags inside `assets-audit`, with validation tests for missing/cyclic tags.
- Performed offline asset checks for the user-supplied Minecraft Java 1.21.8 (Java 21) and 26.3 (Java 25) server bundles.
- Added regression tests and updated bilingual documentation. No complete seed-only Noise/Biome/Jigsaw simulation, nor original end-to-end Minecraft world parity, is claimed.


## 2.10.0 — 2026-10-13

- Read worldgen JSON and compressed NBT directly from the single embedded game JAR inside a versioned Minecraft `server.jar`, with bounded decompression and mismatch checks.
- Fixed the modern 26.3 lowercase `id/properties` NBT palette interpretation and horizontal rigid connector Y offset; preserved legacy template support.
- Added `assets-audit` CLI for version-scoped placement, biome-tag, baseplate, and tower metadata verification without running the server.
- Added Java runtime version preflight and checked the official 26.3 `world_version=5023` against world saves.
- Used the user-provided Minecraft Java 26.3 JAR for an actual offline assets inspection. No full Java 25 server run or seed-only exact world height was verified.
- Kept English and Traditional Chinese GUI and README, and added regression tests and documentation of the remaining limits.


## 2.9.0 — 2026-10-13

- Added `tower_geometry.py` to parse vanilla NBT jigsaw connectors and a singleton rigid watchtower list pool; derive a conditional vertical tower-to-base offset, rejecting ambiguous layouts.
- Added `finder.py tower-project` for computing conditional base/tower Y from an **externally supplied exact WORLD_SURFACE_WG** value, without asserting that any tower naturally generates.
- Extended `geometry-audit` with an actual-saved-tower-vs-template vertical check (`tower_vertical_status`) when compatible resources are present.
- Fixed native `--max-y` one-block cutoff for the projected baseplate when template dimensions are provided (test-first reproduction).
- Kept bilingual README and GUI; still no source-only exact Noise/Biome simulation or official vanilla end-to-end parity.


## 2.8.0 — 2026-10-13

- Added a reproducible `geometry-audit` CLI comparing saved Jigsaw baseplate NBT with seed-derived rotation, horizontal footprint and supplied template dimensions.
- Added optional estimate-vs-saved-height comparison with strict sample-coordinate checks; report incomplete or mismatched cases without declaring exact terrain generation.
- Added optional `candidates --game-jar` preflight validation of outpost and village structure set placement parameters; refuse incompatible version assets rather than silently returning misleading candidate positions.
- Added eight test-first cases covering rotated bounding boxes, incompatible assets, geometry mismatches, and model Y error; retained bilingual README and UI.
- Still missing full 1.21–26.x seed-only Noise/Biome/Jigsaw tower height equivalence and original Mojang server ground-truth datasets.


## 2.7.0 — 2026-10-13

- Added baseplate template metadata reading directly from a supplied game JAR, validating the outpost structure/pool JSON and gzip NBT dimensions.
- Reproduced `setCarverSeed` 48-bit Java RNG, four rotations, and the rotated start-piece bounding box center in Python and C.
- Native projected-height output now includes sampling coordinates, rotation, and **estimated-only** baseplate Y, with no claim of original-game height parity.
- Added GUI/CLI options and English/Traditional Chinese labels for a game assets JAR; optional seed-to-vanilla terrain priority uses the improved projection.
- Added independent JDK and native/Python consistency tests; updated bilingual documentation and technical limitations.

## 2.6.0 — 2026-10-13

- Validate native height CSV against the requested Minecraft version and seed, real placement candidates, exact block/chunk coordinates, radius, Y limits and row caps; reject duplicates.
- Reject saved region entries whose embedded chunk X/Z disagrees with the expected origin position.
- Add six red-to-green regression tests for misleading native results and chunk index mismatches.
- Keep both GUI languages and precise distinctions between candidate, approximate height and verified saved tower status.
- **Exact seed-only biome/noise/Jigsaw simulation and Mojang-server parity remain unimplemented/unverified.**

## 2.5.0 — 2026-10-13

- Added bilingual single-seed / seed-list advanced explorer available from the existing GUI.
- Added placement-only searches over user-defined 512-block region rectangles with safety caps.
- Added cancellable multi-seed batches, seed progress / ETA and coordinate / seed-list exports.
- Added approximate-Y ranking via externally built 1.21.8 native sampler; never assigns a fake Y to placement candidates.
- Added Java 26.1.2 to the placement-candidate version selector.
- Added regression/GUI/CLI smoke tests and a reference-tool parity report.
- **No claim of an exact seed-only outpost-height engine or completed vanilla multi-version oracle verification.**

## 2.4.0 — 2026-10-12

- `seed-vanilla` now forwards optional `--priority terrain` and `--core-archive` to the existing 1.21.8 preliminary ranking pipeline instead of silently forcing near-origin order.
- Added a Traditional Chinese / English GUI selector for candidate priority and transparent 1.21.8 compatibility checks.
- Added `height_audit.py` for comparing experimental seed-only projected Y with saved vanilla tower base Y by matched chunk/seed/version, refusing ambiguous rows and never marking an estimator universally exact.
- Added `scripts/benchmark.py` to measure placement and optional native estimation speeds on the actual host, without predicting Minecraft world generation time.
- Added performance and exact-engine design references and new unit/GUI tests.
- Exact no-chunk-generation cross-version height calculation remains **not implemented**; no official Minecraft server JAR end-to-end tests were run.

## 2.3.0 · 2026-10-12

- 新增 `seed-vanilla` 指令及雙語 GUI 模式：自行提供官方伺服器 JAR、明確接受 EULA 後，在隔離的暫存原版世界生成候選區塊，輸出真實結構 NBT 高度及稽核結果。
- Added the `seed-vanilla` CLI and bilingual GUI mode: disposable vanilla world, explicitly accepted EULA, saved Jigsaw NBT height extraction, audited candidate statuses.
- 增加伺服器 JAR 版本一致性、回環位址限制、生成批次上限、取消時清理及新功能測試；仍未完成官方 JAR 端到端對拍。
- Added JAR version checks, loopback binding, work limits, process cleanup and regression tests. Official Mojang JAR end-to-end tests remain outstanding.

## 2.2.0 · 2026-10-12

- 新增可立即切換的繁體中文／英文 GUI，包含五種模式、輸入欄位、提示、訊息視窗、結果表格與錯誤訊息。
- Added Traditional Chinese / English GUI translations with runtime language switching, including five modes, fields, dialogs, messages, and result columns.
- 新增 GUI「地形高度推算（試驗）」模式：**1.21.8** 使用可選 C 核心，直接從種子推算**近似**地表 Y，無需既有存檔；不聲稱已驗證的前哨站高度。
- Added an optional 1.21.8 seed-only **approximate** terrain-height mode; no saved world required, but actual tower heights remain unverified.
- GUI 工作模式調整成兩列，避免英文介面在較窄視窗隱藏選項；增加回歸測試。
- Split search mode buttons into two rows so English labels remain accessible in narrow windows.
- C 輸出新增固定版號欄位 `version=1.21.8`，便於追溯地形推算資料；更新 Java 候選座標測試。
- Added `version=1.21.8` to native scanner CSV output and updated the independent Java placement oracle.
- 依 GitHub 發布文件模板重寫 README 中英文雙語章節，明確列出實際能力、操作流程、版本範圍、授權狀態及限制。
- Rewrote the README as a bilingual GitHub repository guide, distinguishing current capabilities, measured evidence and limitations.

## 2.1.0 · 2026-10-12

- 加強損毀／混版區塊回報、NBT 解壓縮限制與搜尋規模防護。
- CSV 成功後原子取代；改善 RCON 候選核對與 GUI 關閉／取消操作。
- 新增自動化測試、CI 與發行打包腳本。

## 2.0.0 · 2026-10-12

- 新增繁體中文 GUI、跨版候選搜尋、世界存檔掃描及本機 RCON 核對流程。
- 保留可選的 1.21.8 C 地形近似器。
