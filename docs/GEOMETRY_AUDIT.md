# Jigsaw 起始幾何對拍 / Jigsaw start geometry audit

## 中文

`geometry-audit` 是一次性的差異驗證，不是新的原版 Noise 引擎。需要來自同一世界種子的候選 CSV、包含 `level.dat` 和 `region/` 的原版存檔，以及所選版本的遊戲資源 JAR。建議先備份世界存檔；工具只讀取檔案。

運作步驟：先確認世界版本與 seed，再讀取基板結構 `BB` 與 `rotation`，根據 seed、候選 chunk 以及 JAR 中的基板尺寸推導預期旋轉與 X/Z footprint；兩者逐項比較。若選用 `--estimates`，只接受能提供 `sample_x`、`sample_z`、`rotation`、`projected_base_plate_y` 的 `estimated_only` 結果；取樣座標或旋轉不一致時不計算 Y 誤差。

報告中的 `height_error` 定義為「模型推算的基板 Y－原版儲存的基板 Y」。`geometry_status=match` 僅說明該筆資料的幾何吻合，`full_version_height_exact=false` 固定表示尚未達成跨版本 Noise/結構生成的充分證據。人工 NBT 測試資料不可當成原版實測。

**下一個需要實作的核心**是與原版等價的 Noise router、含水層及 `WORLD_SURFACE_WG`，再核對 Jigsaw 子結構連接後的瞭望塔片段；必須使用官方伺服器的真實生成案例對拍。工具不會將少數成功案例外推為全部版本精確。

## English

`geometry-audit` is a differential verification step, not an implementation of Minecraft's full terrain generator. It needs a candidate CSV, a corresponding generated world, and a matching assets JAR. It reads saved baseplate `BB`/rotation and compares them with the predicted seed-dependent footprint. An optional estimated CSV must include explicit sample X/Z and rotation to avoid confusing old chunk-center samples with the actual Jigsaw projection.

`height_error = predicted_base_plate_y − saved_base_plate_y`. A geometry match checks only one generated sample and cannot prove noise accuracy or global minimum Y. Real Mojang-generated verification data is still needed to establish original-game equivalence.
