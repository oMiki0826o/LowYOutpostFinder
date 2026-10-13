# A／B 雙路線操作與精確性說明

這份文件對應 LowYOutpostFinder **2.0.0 工程版**。它明確區分從種子可獨立計算的事實，以及必須經由原版世界生成才能確認的高度；使用者不需閱讀原始碼也能判斷 CSV 的可信度。

## 路線 A：由原版 Minecraft 實際生成並核對

最可靠的 Y 來源是**同版原版伺服器已儲存的結構 NBT**。程式會從種子求候選、依距指定中心最近的順序挑選，透過使用者已同意 EULA 的 Minecraft 伺服器生成候選區塊，等待存檔變成 FULL，再驗證基板、塔樓與結構包圍盒。`verified_tower` 只確認存檔內有符合資料條件的結構，**並非**經驗證的最低有效刷怪 Y。

執行前可先檢查 JAR 與 Java 是否相容（此步驟**不啟動世界**）：

```sh
python3 finder.py server-check --version 1.21.8 \
  --server-jar /path/to/server.jar --java java --out results/server-check.json
```

這會核對封包宣告的版本、結構放置參數與 Java 主版本，並將 JAR SHA-256 保存供後續差異追蹤；**無法**驗證檔案是否來自官方、亦不表示已完成生成測試。

執行前須自行閱讀並接受 Minecraft EULA，並備妥 Java 21 與**可信任的 1.21.8** 原版 `server.jar`。請勿執行陌生人提供的可執行 JAR。

```sh
python3 finder.py seed-vanilla \
  --version 1.21.8 --seed 123 --server-jar /path/to/server.jar \
  --java java --eula-accepted --radius 8192 \
  --center-x 0 --center-z 0 --limit 20 --offset 0 \
  --center-y-below -37 --max-y 0 --sort-by base-y \
  --out results/verified.csv \
  --audit results/audit.csv \
  --checkpoint results/progress.csv \
  --summary results/summary.json
```

只有**本人確實接受 EULA** 時才能加入 `--eula-accepted`；程式不會代替你同意。這個模式每次都建立並清理獨立暫存世界；`progress.csv` 只保留稽核快照，不包含可恢復的完整世界，不能拿它直接續跑。

如已擁有可連線的同版原版伺服器，建議先備份世界，再使用 `search-live`。這個模式可保留世界、反覆執行並讀取已儲存的候選（不是無條件信任上次 progress.csv）：

```sh
export MINECRAFT_RCON_PASSWORD='your-local-rcon-password'
python3 finder.py search-live \
  --world /path/to/offline-world-folder --radius 8192 \
  --center-x -1024 --center-z 2048 --limit 50 --offset 0 \
  --center-y-below -37 --sort-by tower-y \
  --audit results/server-audit.csv --checkpoint results/server-progress.csv \
  --summary results/server-summary.json --out results/server-hits.csv
```

**請避免直接掃描在線上正在修改的世界檔案**。上述 `--world` 必須對應實際伺服器正在儲存的世界目錄，且來源、遊戲版本和種子必須一致。指令會更動該世界；不可將離線世界副本當成 RCON 正在儲存的目錄，否則會因不同步得到錯誤結果。只有純 `world` 或 `verify` 模式適合離線備份副本。

如果搜尋進行到一半中斷，`-progress.csv` 會保留本次已處理的稽核紀錄（下次重新執行時會重新建立；請先複製舊紀錄）；對同一持續存在的伺服器世界重新執行時，程式會**重新檢查已存檔區塊**，避免重複生成。`--offset` 可以從依距離排列的第 N 個候選開始掃描，適合分批覆蓋同一有限範圍；因前面的候選被略過，該分頁**不會宣稱找到距中心最近的前哨站**。

`--sort-by base-y` 或 `tower-y` **只會排序已驗證結果**，不改變伺服器生成順序，也不證明未掃描的候選沒有更低的 Y。

## 路線 B：不生成區塊的可驗證起始幾何

純種子預測已實作的範圍包括：**原版結構放置嘗試座標**、讀取同版 JAR 的前哨站模板尺寸、模擬原版 Jigsaw 起始旋轉，以及推導原版會呼叫 `WORLD_SURFACE_WG` 的 X/Z 取樣位置。這些都不需要真正生成區塊。

```sh
python3 finder.py seed-geometry \
  --version 1.21.8 --seed 123 --radius 8192 \
  --center-x -1024 --center-z 2048 \
  --game-jar /path/to/server.jar --out results/geometry.csv
```

`geometry.csv` 的 `rotation`、`sample_x`、`sample_z` 是**起始幾何位置**。`classification=seed_geometry_only` 表示還沒有產生／驗證以下資訊：是否能通過原版生態域判定、是否真的能生成結構、正確的 `WORLD_SURFACE_WG`、基板 Y、塔樓 Y 和掠奪者實際生成高度。

如要得到**試驗性的 Y**，可以另外用 `estimate`，但它使用外部 C 核心的近似地形，不是原版精確 Y；不能把估測結果當成已確定的低 Y 前哨站。

## 如何判斷最低 Y 是否已證明？

`summary.json` 區分兩種主張：

- `nearest_status=nearest_proven_within_radius`：若所有**比首個合格塔樓更靠近搜尋中心**的候選都經過確認，才表示有限搜尋範圍內距該中心最近的合格塔樓已獲得證據。
- `lowest_status=lowest_verified_within_radius`：只有**指定半徑內全部候選**都被逐一核對，且不存在逾時、資料錯誤或未解決候選，才可聲稱取得該有限範圍內的最低高度。此處「最低」是符合設定門檻、在已確認塔樓的基板高度意義上；不是世界全域最低，也不是刷怪高度。
- `not_proven`：只做了部分位置、按近似地形抽樣、使用 `--offset`、遇到不完整候選等情況。即使存在很多 `verified_tower`，也不能升級成完整範圍的最低高度證明。

`distance_sq` 是相對**世界原點**的距離平方；`search_distance_sq` 才是相對**自訂搜尋中心**的距離平方。搜尋區域是以中心為準的**正方形**（X、Z 各自 ± radius），不是圓形半徑。

## 尚未實作或尚未完成獨立原版驗證

1. Minecraft 1.21.8 的完全原版等效 NoiseRouter、Aquifer、BiomeSource 求值器。
2. 不生成區塊、只用世界種子取得精確 `WORLD_SURFACE_WG` Y。
3. 全部 Jigsaw 片段隨機選取、旋轉、連接、空間碰撞的原版等效模擬。
4. 以 1.21.8 原版伺服器產生真實世界的端到端、多種子對拍。此版未自動接受 Minecraft EULA，不能宣稱已執行。
5. 全支援版本精確 Noise/生態域的逐版對拍。
6. 掠奪者實際生成範圍與農場產量的驗證。

原版資源 JSON 的成功解析以及 Java 亂數單元測試，都不能取代這些工作。**2.0.0 是可執行的 A/B 雙路線工程版，並非已實現完全精確免生成的最終 Y 引擎。**
