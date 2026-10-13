# 原版伺服器資源核對 / Vanilla server asset inspection

## 中文

從 Minecraft Java 1.21 起的版本，官方伺服器 JAR 可能是一個啟動包，真正的遊戲資源放在 `META-INF/versions/<版本>/server-<版本>.jar`。本工具會在記憶體中開啟該內層資料，不會執行檔案，也不會修改使用者的 `server.jar`。

執行 `python3 -m lowy_outpost_finder assets-audit --version 26.3 --server-jar /path/to/server.jar --out metadata.json`，可以檢查相符版本的前哨站放置設定、村莊排除設定、生態域標籤、Jigsaw 基板與瞭望塔尺寸，以及單一確定的剛性高度差。程式會拒絕不一致的 JAR 宣告版本與無法解析的資源。

提供的 26.3 `server.jar` 之 `version.json` 宣告 Java 25、世界 DataVersion 5023；基板模板為 16×30×16、瞭望塔 15×21×15，剛性連接高度位移為 0。輸出與檔案雜湊記錄在個別核對報告中。

這不表示成功生成前哨站，更不表示 `WORLD_SURFACE_WG` 高度已經求得。若要原版逐筆驗證，需要使用者先閱讀並同意 Minecraft EULA，再以 Java 25 與該 JAR 執行 `seed-vanilla`；**本次執行環境只有 Java 21，未執行端到端測試**。本工具無法驗證使用者提供的 JAR 是否經過竄改，雜湊只能辨識本次讀取的實際資源。

## English

Modern versioned Minecraft server JARs may bundle their game data in one nested file at `META-INF/versions/<version>/server-<version>.jar`. The tool opens that game data in memory, without execution or modifying the JAR.

Run `python3 -m lowy_outpost_finder assets-audit --version 26.3 --server-jar /path/to/server.jar --out metadata.json` to check the versioned structure sets, biome tag, base/tower template dimensions and supported rigid connector vertical offset. Incompatible version metadata and unknown resource layouts are rejected rather than guessed.

The provided 26.3 archive declares Java 25 and world DataVersion 5023. Its baseplate is 16×30×16, watchtower 15×21×15 and conditional vertical connector offset 0.

This **does not** prove that an outpost generates or give the exact `WORLD_SURFACE_WG` height. A vanilla end-to-end run would require explicit EULA acceptance and a Java 25 runtime, which was not available here (Java 21 only). A resource hash is not a digital-signature authentication of the archive's origin.
