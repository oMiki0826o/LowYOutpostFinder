# v2.0.0 實際驗證紀錄

本文件只記錄 **2026-10-13 在目前容器環境真的執行過的檢查**，不把先前測試或使用者未授權的原版生成列為成功。

## 程式測試

- `python3 -m compileall -q -x '(\.build|__pycache__)' .`：成功。
- `python3 -m unittest discover -s tests -v`：179 項，**0 失敗、12 略過**（無 GUI 顯示器）。
- `xvfb-run -a python3 -m unittest discover -s tests -v`：182 項，**0 失敗、0 略過**，其中包含繁體中文／英文 GUI 及 2.0 新增回歸測試。
- `python3 scripts/build_native.py terrain /mnt/data/LowYSwampHut-2.0.1.tar.gz`：CMake 與 C 搜尋器編譯成功；外部原始碼不包含於發布 ZIP。
- `python3 tests/check_placement.py bin/lowyoutpost`：五組種子（0、123、-1、Long.MIN、Long.MAX）Java 隨機數候選位置對照通過。

## 用實際提供的原版 Minecraft JAR 核對

提供的 1.21.8 `server (1).jar`（宣告 DataVersion 4440，Java 21）使用以下命令完成**不啟動伺服器的資源驗證**：

```sh
python3 -m lowy_outpost_finder server-check --version 1.21.8 --server-jar '/mnt/data/server (1).jar' --java java --out /mnt/data/lowy_build/v2_real_preflight.json
python3 -m lowy_outpost_finder assets-audit --version 1.21.8 --server-jar '/mnt/data/server (1).jar' --out /mnt/data/lowy_build/v2_assets_1218.json
python3 -m lowy_outpost_finder seed-geometry --version 1.21.8 --seed 123 --radius 8192 --game-jar '/mnt/data/server (1).jar' --out /mnt/data/lowy_build/v2_seed_geometry_real.csv
python3 -m lowy_outpost_finder estimate --version 1.21.8 --seed 123 --radius 2048 --max-y 64 --top 3 --game-jar '/mnt/data/server (1).jar' --out /mnt/data/lowy_build/v2_approx.csv
```

- 預檢：JAR 宣告 Minecraft 1.21.8、要求 Java 21；目前 Java 21；放置參數符合搜尋器內建公式。**此結果不等於 JAR 來源簽章驗證**。
- 模板旋轉／高度圖取樣 X/Z：seed 123、8192 方塊正方形區域，輸出 118 筆放置候選幾何（另有標題列）；輸出**不含 Y**。
- 試驗性 C 近似：輸出 3 筆 `estimated_only`，**不能當成原版實測 Y**。
- 使用 26.3 `server.jar` 的 `seed-geometry` 亦成功輸出 11 筆樣本；**未**在 Java 21 直接執行 26.3。`server-check` 正確拒絕 26.3：需要 Java 25，當前為 Java 21。

## 未測項目與證據界線

- 沒有替使用者接受 Minecraft EULA，也**沒有啟動原版 Minecraft 伺服器並實際生成任何區塊**。因此「種子 → 原版伺服器 → 儲存存檔 → 核對塔樓 Y」端到端測試**未完成**。
- 新增的 `--checkpoint`、`--offset`、`--sort-by`、`--summary` 經隔離的假 RCON／自製 NBT 單元測試；不等於在實際 Minecraft 伺服器的運作測試。
- 不生成區塊、直接求**精確** `WORLD_SURFACE_WG`、Biome、Aquifer、完整 Jigsaw 子結構及實際最低刷怪 Y，均**尚未實作**。2.0.0 的純種子引擎只涵蓋結構放置及起始幾何。
- 本地 Linux 容器測試通過**不等於** GitHub Actions 的 Windows/macOS/Linux CI 已經在這個提交上通過。尚未推送 GitHub；CI 綠燈有待實際提交後確認。

## 測試結果解讀

從**同版原版 JAR 讀取資產**不代表已經重現世界生成演算法。單元測試對幾何運算的正確性有幫助，但不能證明尚未實作的 Noise/生態域求值器。只靠已生成世界內的結構 BB，可可靠地核對該存檔已保存的 Y，卻不能用此方式推論全世界未生成的位置。
