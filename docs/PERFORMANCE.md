# 效能指南 / Performance

## 繁體中文

### 工作量差異

* **候選搜尋**：只執行原生 Java 隨機數相容的結構放置測試，不計算區塊或地形 Y，通常很輕量。
* **近似地形高度**：對少量通過 placement 的座標計算 1.21.8 試驗性噪聲／地形樣本，CPU 明顯較重，但無須開啟遊戲。
* **原版確認高度**：需要啟動 Java 伺服器並生成、儲存候選區塊，時間與記憶體需求明顯增加，也取決於候選位置、儲存裝置與版本；目前**沒有**官方 JAR 的實測時間。
* **完全精確、免生成、跨版 Y**：尚未實作，不能提供真實速度測量。

2026-10-12 在此 Linux 容器內，世界種子 `123`，**三次執行的中位數**（已安裝並編譯 LowYSwampHut 2.0.1、關閉 C 預設生態域篩選，`--top 25`）：

| 半徑（方塊） | 候選數 | Python 候選掃描 | C 試驗性近似地形 |
| ---: | ---: | ---: | ---: |
| 8,192 | 118 | 0.0039 秒 | 0.095 秒 |
| 32,768 | 2,034 | 0.065 秒 | 1.63 秒 |
| 65,536 | 8,225 | 0.30 秒 | 8.49 秒 |

**這些不是一般玩家電腦的效能保證，也沒有量到原版生成任何區塊的時間。** C 試驗性地形使用目前 CPU 運算，主要會增加處理器負擔，並不是一直啟動 Minecraft；GUI 透過子行程工作，不應因搜尋而阻塞視窗事件迴圈。若是較舊、只有 8GB RAM 的 Mac，建議先以 8,192～16,384 半徑測試，再視結果調整。

自行測量：

```sh
python3 scripts/benchmark.py --seed 123 --radii 8192,32768,65536 --rounds 3
sh build.sh /path/to/LowYSwampHut-2.0.1.tar.gz
python3 scripts/benchmark.py --seed 123 --radii 8192,32768 --rounds 3 --native bin/lowyoutpost
```

`terrain` 優先順序是**排序**而不是精確判定；降低原版生成數量的同時可能漏掉最低 Y。要避免漏查，需逐一確認區域內所有候選，或等待具有原版對拍證據的精確演算法。

## English

Placement scanning is lightweight because it only evaluates structure placement RNG. The optional 1.21.8 experimental C terrain calculation is CPU-heavy but does **not** generate chunks. Vanilla verification launches Java and generates chunks; timings for this stage have **not** been measured against an authentic Minecraft server JAR. No exact cross-version seed-only height predictor exists in this release.

Measured on the Linux build container on 2026-10-12 with seed `123`, three-run median, native top 25 with biome gate disabled:

| Radius (blocks) | Candidates | Python placement | Experimental native terrain |
| ---: | ---: | ---: | ---: |
| 8,192 | 118 | 0.0039 s | 0.095 s |
| 32,768 | 2,034 | 0.065 s | 1.63 s |
| 65,536 | 8,225 | 0.30 s | 8.49 s |

These are observed local measurements, not forecasts for any other computer and **not** vanilla chunk-generation timings. Run `python3 scripts/benchmark.py --help` on your own system. The experimental terrain priority can omit the true lowest tower when it chooses only a finite subset to verify.
