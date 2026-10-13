# 驗證紀錄 / Validation report — v2.13.0

日期 / Date: 2026-10-13

## GitHub 初始化前增量審核 / Pre-publication incremental audit

- `python3 -m compileall -q -x '(\.build|__pycache__)' .`：exit 0。
- `PYTHONPATH=.:tests python3 -m unittest -v ...`（排除需要桌面顯示的 Tk 測試）：**150 tests, 0 failures, 2 skipped**。略過項目需要未附加的可選 C backend。
- 新增回歸案例確認：未指定新中心門檻的舊內部呼叫維持相容；指定 `structure_center_y < -37` 時只輸出符合門檻的已驗證塔樓。
- `shasum -a 256 -c SHA256SUMS.txt`：修改後首次執行正確偵測 6 個舊雜湊；發布前重新產生清單並再次驗證。
- Tk GUI 測試未在本機無虛擬顯示器環境重跑；GitHub Actions 保留 Linux `xvfb` 工作。未啟動 Minecraft/Fabric 伺服器，亦未生成實際世界。

- `python3 -m unittest discover -s tests -q`：**157 cases, 0 failures, 10 skipped**；其中新增 13 項針對有限區域最低高度證明、幾何資料防誤判、世界修改中斷及待生成候選輸出。
- `sh build.sh /mnt/data/LowYSwampHut-2.0.1.tar.gz`：本機 C 核心編譯 exit 0。此核心只提供近似高度，不是精確 1.21.8 世界生成。
- `python3 tests/check_placement.py bin/lowyoutpost`：5 組 Java/原生 RNG 參考種子全數通過；證明放置座標，**不是**生態域或 Jigsaw 高度。
- `xvfb-run -a python3 -m unittest discover -s tests -p 'test_gui_*.py' -q`：**8 cases, 0 failures**，原有繁體中文／英文 GUI 冒煙驗證。
- `python3 finder.py assets-audit --version 1.21.8 --server-jar ...` 與 `jigsaw-contract`：使用上傳的 1.21.8 JAR 完成離線結構資源核對；**未執行** Java 伺服器生成世界。
- `region-certificate` 的完整與不完整分支：單元測試使用人工原版格式區塊資料與受控假件；**沒有自然生成世界存檔的端到端核證資料。**

**明確限制：** v2.13.0 實作的是由**既有且可信的原版世界存檔**回推的「有限指定半徑最低 Y 證明」。它無法從種子獨立計算 1.21～26.x 的精確 Noise、Biome、`WORLD_SURFACE_WG` 和完整 Jigsaw。先前要求的六項純種子精確生成目標**仍未完成**，絕不因本次測試成功而宣稱完成。

---

# 驗證紀錄 / Validation report — v2.12.0

日期 / Date: 2026-10-13

## 已執行的本機檢查 / Executed checks

- `python -m compileall -q -x '(\.build|__pycache__)' .`：通過 / passed。
- `python -m unittest discover -s tests -v`：**144 tests, 0 failures, 10 skipped**。解壓後因未附加可選 C 執行檔，重跑為 **144 tests, 0 failures, 12 skipped**。
- `xvfb-run -a python -m unittest discover -s tests -p 'test_gui_*.py' -v`：**8 passed**。
- `sh build.sh /mnt/data/LowYSwampHut-2.0.1.tar.gz`：C 核心重新編譯成功；此核心的 Y 僅為近似值。
- `python tests/check_placement.py bin/lowyoutpost`：**5/5 Java Random test seeds PASS**；只驗證放置候選公式。
- `finder.py worldgen-contract`：使用上傳的原版 1.21.8 JAR 找到 16 個密度函數資源、34 個 Noise 參數資源；26.3 JAR 找到 21 個密度函數資源、26 個 Noise 參數資源。**完整資源相依，不等於執行正確的 Noise 運算**。
- `finder.py jigsaw-contract`：兩份 JAR 各找到 4 個可達結構池、11 個模板與 13 個連接參照。**未實作原版 Jigsaw 隨機選擇／碰撞模擬**。
- `certify-samples`：人工測資驗證有限樣本核對、版本／雜湊不符拒絕、缺漏及不一致處理；尚無真實原版世界高度樣本。

兩份 JAR 均未納入發布檔。上傳檔 SHA-256：

- Minecraft 1.21.8: `2349d9a8f0d4be2c40e7692890ef46a4b07015e7955b075460d02793be7fbbe7`
- Minecraft 26.3: `d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64`

## 無法宣稱完成的六項核心能力 / Explicitly unverified goals

| 目標 | 真正完成狀態 | 本次取得的證據 |
| --- | --- | --- |
| 完全精確的 Noise 計算 | **未完成** | 同版原版 Noise Router 相依資源可校驗，沒有完整 Evaluator |
| 完全精確的 `WORLD_SURFACE_WG` | **未完成** | 只有條件式原版存檔見證抽取，沒有純種子高度 API |
| 原版 Biome 生成模擬 | **未完成** | 原版標籤解析；近似 native biome 模型未逐版對拍 |
| 完整 Jigsaw 隨機連接與碰撞 | **未完成** | 只核對可達模板圖與條件式主塔垂直幾何 |
| 不生成區塊取得精確塔樓 Y | **未完成** | 只可由原版生成的存檔確認或以外部提供的 WG 高度條件式推算 |
| 原版生成逐筆對拍 | **未完成** | 使用者尚未提供已生成世界；未代替使用者接受 Minecraft EULA |

**驗證邊界：** 認證用的樣本雜湊證明相同輸入在本工具中被比較，不構成 Mojang 官方簽章、完整地形等效性、跨版本相容性或全球最低 Y 保證。

---

# 驗證紀錄 / Validation report — v2.11.0

日期 / Date: 2026-10-13

## 本次實際執行 / Fresh commands and results

- `python3 -m compileall -q -x '(\.build|__pycache__)' .`：exit 0 / passed.
- `python3 -m unittest discover -s tests -v`：**129 tests, 0 failures, 10 skipped**.
- `xvfb-run -a python3 -m unittest discover -s tests -p 'test_gui_*.py' -v`：**8 passed**（繁中／英文 GUI 冒煙測試）。
- `sh build.sh /mnt/data/LowYSwampHut-2.0.1.tar.gz`：exit 0；以使用者提供的原始碼重新建置可選 C 高度推算核心。
- `python3 tests/check_placement.py bin/lowyoutpost`：**5 / 5 seeds PASS**，使用獨立 Java 亂數程式對照候選位置；並非真實結構生成驗證。
- `python3 finder.py assets-audit --version 1.21.8 --server-jar '/mnt/data/server (1).jar' ...`：成功讀取使用者提供的 **1.21.8 / DataVersion 4440 / Java 21** JAR（內層完整世界生成資源）；核對 placement、村莊排除、16×30×16 基板、15×21×15 塔樓、塔樓 Y 相對位移 0，以及原版允許生成的 **12 個生態域標籤展開結果**。
- `python3 finder.py assets-audit --version 26.3 --server-jar /mnt/data/server.jar ...`：成功讀取上一輪使用者提供的 **26.3 / DataVersion 5023 / Java 25** JAR；相同資源驗證通過。此處不把資源一致推廣為世界生成演算法一致。
- `ensure_compatible_java` 預檢：**1.21.8 Java 21 = 可啟動版本**；**26.3 Java 21 = 不相容（需 Java 25）**。
- `test_noise_witness.py`（5 cases）和 `test_biome_assets.py`（4 cases）：先觀察缺少功能、循環標籤及無效高度的失敗，再實作通過。新功能的驗證資料來自人工 NBT 測試，**不是 Mojang 真實世界存檔**。

## 真實原版世界生成 / Real Minecraft world execution

**未執行。** 使用者提供原版 Minecraft JAR，但尚無使用者在本次工作中明確同意伺服器 EULA 的指示，本環境未建立 EULA 接受檔、啟動伺服器，亦未生成原版世界。Java 21 可運行 Minecraft 1.21.8 並不等於原版生成流程已測試。`height-witness` 目前只驗證人工測資的正確處理；沒有附上任何虛構的「原版成功案例」。

**Not executed.** The supplied JARs are sufficient for offline assets inspection. No EULA was accepted on behalf of the user, no vanilla test world was generated, and no real saved-structure samples were available for geometry/height parity.

## 精確性邊界 / Exactness boundary

| 要求 / Requirement | v2.11.0 實際狀態 / Verified status |
| --- | --- |
| 原版 structure_set、模板和生態域允許清單 | 同版 1.21.8 與 26.3 離線讀取核對 / matching-version assets inspected |
| 直接從種子計算候選位置 | Java RNG 對照通過；不能保證生態域和實際結構 / placement vectors validated only |
| 完全精確的獨立 Noise | **未完成** / not implemented |
| 精確 WORLD_SURFACE_WG | **僅可從真實已儲存的匹配結構推回局部參考值，無獨立計算器** / conditional reconstruction only |
| 生態域從種子抽樣 | **未完成**；只能展開同版原版標籤 / biome sampler missing |
| 所有 Jigsaw 子片段與碰撞 | **未完成**；只有起始幾何及主塔剛性垂直關係 / incomplete |
| 完全不生成區塊的精確塔樓 Y | **未完成** / not implemented |
| 真實 Minecraft 世界逐筆對拍 | CLI 與檢查器存在；**缺真實樣本** / not executed |

所有測試通過，只代表本次已實作範圍內的程式行為。**不代表跨版本、免生成的原版等效演算法已經完成。**

---

# 舊版驗證紀錄 / Previous report — v2.10.0

日期 / Date: 2026-10-13

## 2.10.0 實際執行結果 / Executed results

- `python -m compileall -q -x '(\.build|__pycache__)' .`：通過 / passed.
- `python -m unittest discover -s tests -v`：**120 項測試執行，110 通過、10 略過、0 失敗** / 120 tests run, 110 passed, 10 skipped, 0 failed.
- `sh build.sh /mnt/data/LowYSwampHut-2.0.1.tar.gz`：清除複製工作樹裡舊版 CMake 快取後，編譯成功 / native build passed after clearing a stale copied CMake cache.
- `python3 tests/check_placement.py bin/lowyoutpost`：5 組 Java 亂數參考種子全數 PASS / five independent seed placement comparisons passed.
- `xvfb-run -a python -m unittest discover -s tests -p 'test_gui_*.py' -v`：8 項通過 / eight GUI smoke tests passed.
- 使用者提供的 `/mnt/data/server.jar`：讀取 `version.json` 得到 Java Edition **26.3**、DataVersion **5023**、執行環境需求 **Java 25**。從其內層 JAR 成功核對 outpost/village placement、biome tag 與原版模板；16×30×16 基板、15×21×15 瞭望塔、水平剛性連接相對 Y 位移 0。/ Inspected the user-provided 26.3 bundled server assets directly.
- `java -version`：本執行環境為 **Java 21**。相容性預檢如實回報 26.3 需要 Java 25，因此未執行原版伺服器端到端生成驗證。/ No vanilla E2E generation took place; current Java 21 is too old for the supplied Java 25-requiring server.

本次能證實的是 **26.3 原版資源的離線相容性與相對幾何運算**；未證實免生成 Noise、完整生態域／Jigsaw 檢查或最低可刷怪 Y。/ This verifies offline resource compatibility and relative geometry, **not** a complete vanilla Noise/Biome/Jigsaw/world-height engine or pillager spawn minima.

---

## 舊版紀錄 / Previous release evidence (historical)


日期 / Date: 2026-10-13

## 本次實際驗證 / Executed in this environment

```sh
# 來源為使用者提供的 LowYSwampHut 2.0.1 壓縮包
sh build.sh /mnt/data/LowYSwampHut-2.0.1.tar.gz
python3 -m compileall -q .
python3 -m unittest discover -s tests -v
python3 tests/check_placement.py bin/lowyoutpost
xvfb-run -a python3 -m unittest discover -s tests -p 'test_gui_*.py' -v
```

- C 構建：成功 / Native C build: passed.
- 全部單元測試：109 項執行，0 失敗，10 項略過（需要特定 GUI/環境的條件）。/ 109 tests, 0 failures, 10 skipped.
- Java 對照：5 種 seed（含 Long.MIN/MAX）驗證候選演算法。/ Candidate placement matched 5 independent Java reference seed runs.
- Xvfb 雙語 GUI：8 / 8 通過。/ 8 GUI smoke tests passed under Xvfb.
- 本次新增塔樓垂直連接、CLI、原生 Y 門檻回歸測試，先觀察缺少實作或邊界誤判的預期失敗，再修正通過。/ New tower-connector, CLI and native threshold tests were verified red-to-green.
- 實際 Mojang 伺服器對拍：未完成。本環境無官方伺服器檔；嘗試取得官方 1.21.8 server JAR 失敗。
- `geometry-audit` 的完整存檔測試使用**人工合成的 NBT fixture**，並非 Mojang 產生的真實世界。

## 完成與限制 / Scope and limitations

本次新增 `geometry-audit`：從原版存檔格式讀取起始基板的 `BB`、`rotation`，與 seed + template 算出的水平包圍盒逐筆比較；再選擇性比較實際基板 Y 與試驗估測值。新功能不會把小範圍的一致結果提升為跨版本精確引擎。

`candidates --game-jar` 可從選用的資源 JAR 檢查 `pillager_outposts` 與 `villages` 的結構放置數值是否符合內建演算法；**它不驗證生態域、Noise、Jigsaw 子結構或 JAR 的官方真實性／版本簽名**。

**仍缺：** 完整跨版精確 Noise/含水層/`WORLD_SURFACE_WG`、Biome、Jigsaw 隨機連接與碰撞（目前僅剛性塔樓 Y 相對位移）；官方原版世界資料的驗證樣本；掠奪者最低有效生成 Y。官方端到端結果不得虛構。

The user can run the vanilla seed-verification workflow with the matching official server, save the audited world/result CSV, and run `geometry-audit` to localize whether the discrepancy is geometry or terrain. The current source-only ZIP contains neither Mojang artifacts nor a world save.

## v2.9.0 補充 / Addendum

- `tower_geometry.py` 僅處理單一、可唯一判定 Y 的剛性主要塔樓連接；合成測試檔證明程式處理自製 NBT 資料的行為，**不等於原版 Mojang 遊戲資產或世界驗證**。
- `tower-project` 必須由外部提供**真實世界生成時**的 `WORLD_SURFACE_WG`；即使 JSON 產出成功，也不能推論從種子直接精確算高、成功生成前哨站或有效刷怪高度。
- `geometry-audit` 的高度檢查只比較實際已儲存的塔樓與基板相對 Y；資料不明時標記不支援。
- 無法於本環境下載官方伺服器 JAR（連線 DNS 不可用）；原版 1.21～26.x 實際世界對拍仍未執行。
