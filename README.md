# LowY Outpost Finder

Minecraft Java 版掠奪者前哨站研究工具，提供繁體中文／英文 GUI、結構位置候選搜尋、已生成世界的唯讀 NBT 核對，以及使用者明確授權後的原版伺服器驗證。

> `placement_candidate` 只表示符合放置公式，不代表前哨站必然存在，也沒有 Y。`estimated_only` 是試驗性近似。只有 `verified_tower` 是從已生成且儲存的世界證據確認。

## 最簡單的啟動方式

### macOS JAR 發布版

直接從原始碼倉庫下載對應的檔案：

- Apple M1／M2／M3／M4 等 Apple Silicon：
  [下載 ARM64 JAR](release/macos/LowYOutpostFinder-macos-arm64.jar?raw=1)
- Intel Mac：
  [下載 x86_64 JAR](release/macos/LowYOutpostFinder-macos-x86_64.jar?raw=1)

使用者只需安裝 **Java 21 以上**。JAR 已包含 Python 3.13 與 Tk GUI，
不需要另外安裝 Python、Tkinter 或 PyPI 套件。可直接雙擊 JAR，或執行：

```sh
java -jar LowYOutpostFinder-macos-arm64.jar
# Intel Mac 使用 LowYOutpostFinder-macos-x86_64.jar
```

不知道 Mac 架構時，可開啟「蘋果選單 → 關於這台 Mac」查看「晶片」或
「處理器」。首次啟動會離線展開約 100 MB 到
`~/Library/Caches/LowYOutpostFinder/`，請至少保留 150 MB 可用空間；日誌位於
`~/Library/Logs/LowYOutpostFinder/launcher.log`。

下載後可使用 [SHA256SUMS-macos.txt](release/macos/SHA256SUMS-macos.txt)
核對檔案。若 macOS
Gatekeeper 阻擋未簽署的 JAR，核對雜湊後可在 Finder 按住 Control 點擊檔案，
選擇「打開」；不需要停用系統整體安全性。

### 從原始碼啟動

從原始碼執行需要 Python 3.11 以上與 Tkinter：

```sh
python3 LowYOutpostFinder.py
```

Windows 可使用：

```powershell
py LowYOutpostFinder.py
```

根目錄唯一的 Python 檔案就是 GUI 啟動器；執行後即可在介面中操作。

## 開發與依賴

- `requirements.txt`：執行期依賴（目前為零）。
- `requirements-dev.txt`：開發期依賴（目前為零）。
- `lowy_outpost_finder/`：應用程式套件。
- `native/src/`：選用的 C11 原生掃描器。
- `scripts/`：建置、測試與發佈工具。
- `examples/`：輸入範例。
- `data/`：本機 AI 協作與私有資料，已由 Git 忽略，不會進入發布包。

完整非 GUI 測試：

```sh
python3 -m compileall -q .
python3 scripts/run_headless_tests.py
```

選用原生搜尋器：

```sh
python3 scripts/build_native.py region
python3 scripts/build_native.py terrain /path/to/LowYSwampHut-2.0.1.tar.gz
```

## 進階 CLI

GUI 是預設入口。自動化時可使用套件入口：

```sh
python3 -m lowy_outpost_finder candidates \
  --version 1.21.8 --seed 123 --radius 8192 --out candidates.csv

python3 -m lowy_outpost_finder full-map \
  --version 1.21.8 --seed 123 --strategy nearest --top 100 --out nearest.csv

python3 -m lowy_outpost_finder world \
  --world /path/to/world-copy --max-y 0 --out saved-outposts.csv
```

原版伺服器驗證需要 Java 21、版本相符且可信任的 `server.jar`，並且必須由使用者閱讀後明確接受 Minecraft EULA。專案不會偷偷代替使用者接受。

## 證據邊界

| 分類 | 能夠宣稱的內容 |
| --- | --- |
| `placement_candidate` | 結構放置公式候選；沒有生成或 Y 證據 |
| `estimated_only` | 1.21.8 試驗性地形近似；不是原版等效結果 |
| `verified_tower` | 從同版已生成世界 NBT 確認的前哨站塔樓 |

本工具尚不能在不生成區塊的前提下，只靠種子精確求出所有前哨站 Y。詳見 [架構](docs/ARCHITECTURE.md)、[使用教學](docs/USAGE.md)、[全圖搜尋](docs/FULL_MAP.md)、[精確引擎限制](docs/EXACT_SEED_ENGINE.md) 與 [驗證紀錄](docs/VALIDATION.md)。

## English quick start

Run `python LowYOutpostFinder.py` (or `py LowYOutpostFinder.py` on Windows) to open the bilingual GUI. The project has no third-party Python runtime dependencies. Advanced automation uses `python -m lowy_outpost_finder ...`.

Placement candidates do not prove that an outpost or a Y coordinate exists. Experimental estimates are not vanilla-equivalent. Only saved-world evidence classified as `verified_tower` confirms a tower. See the linked architecture and validation documents for the exact evidence boundaries.

## License

[MIT](LICENSE). Minecraft belongs to Mojang Studios. This project does not bundle official server JARs, worlds, or LowYSwampHut source code.
