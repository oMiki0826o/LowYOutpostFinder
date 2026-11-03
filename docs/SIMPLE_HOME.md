# Simple low-Y home / 低 Y 極簡首頁

The root entry point `python3 LowYOutpostFinder.py` opens a monochrome, beginner-friendly Tk GUI.
The legacy multi-mode GUI remains available through the top-right settings menu or
`python3 -m lowy_outpost_finder.gui --mode <mode>`.

從專案根目錄執行 `python3 LowYOutpostFinder.py`，即可開啟黑白極簡搜尋介面。
右上角「設定」可啟動原有完整進階 GUI；進階模式沒有刪除。

## Defaults / 預設值

| Field | Default | Semantics |
|---|---|---|
| Minecraft version | Java 1.21.8 | Only version supported by this experimental C height model |
| World seed | Blank | Signed Java 64-bit integer, required |
| Search centre | (0,0) | World origin, **not** necessarily true spawn |
| Radius | 30,000,000 blocks | Square extent clipped to Minecraft's +/-29,999,984 border |
| Structure centre Y | Strictly below -37 | C model checks projected centre Y **<** selected threshold |
| Result count | 25 | Retains up to 25 estimated hits |
| Search mode | Native estimated nearest | Never falls back silently to placement-only X/Z |
| Export | Unique results/*.csv | Auto-save; separate raw evidence in results/.engine/ |

**Important:** C-estimated heights are `estimated_only`, NOT actual tower heights
verified by Minecraft-generated chunks. The current centre-out search stops when
it has found N estimates; **the ring-based stopping rule does not prove that
all are the globally nearest N eligible heights**. Output rows are sorted by
their exact horizontal distance among the found hits. The advanced vanilla
server mode remains available for true Y verification.

使用者看到的「結構中心低於 Y = -37」不是基板 Y <=64；
使用 C 掃描器的嚴格中心高度判定。依現有模型中心 Y = 近似基板 Y + 14，
因此整數近似基板必須 <= -52 才會通過 Y < -37。

## First-run native C compilation / 首次啟動

The GUI checks for a locally executable `bin/outpost_estimate`. If missing,
it starts a background setup thread without blocking the Tk event loop:

1. Check local Git, CMake and a C11 compiler.
2. Fetch exactly pinned MIT-licensed `M33Galaxy/LowYSwampHut` commit
   `e3431121127d8f51613041a59c4fb3dbfaefd8b1`; verify the actual checkout SHA.
3. Build with the project's existing `scripts/build_native.py estimate` workflow.
4. Reuse the executable on subsequent launches. A failed build reports the
   missing prerequisite and leaves the placement-only mode **disabled** in the
   simple home. No untrusted/unversioned binary or downloaded code is run.

### Prerequisites

- Python 3.11+ with Tkinter; no extra Python runtime dependency.
- Internet access on first build (GitHub) and local Git.
- CMake + C11 compiler. On macOS 12.7 Intel, Xcode Command Line Tools and
  CMake must already be installed. On Ubuntu, Git, CMake and build-essential.
- No automatic privileged package installs. When a system tool is absent,
  the GUI explains what is needed; no background auto-install of toolchains.
- Windows source builds are still experimental; tested release binaries are
  a separate future packaging task.
- The C source is from a third-party MIT-licensed project (M33Galaxy,
  SunnySlopes); preserve its attribution and review upstream when updating.

**This is a one-command launcher, not a claim that a bare Python installation
without any compiler can build native C.** A fully self-contained binary
release would need separately tested per-platform compiled artifacts.

## CSV schema / CSV 欄位

The first row always uses these stable English field names (no explanatory
rows before the header):

```csv
version,seed,index,x,estimated_y,z,distance_from_center,distance_from_origin,chunk_x,chunk_z,status
```

- `index`: starts at 1 and ranks returned hits by horizontal distance from
  selected centre; tied distances break by X then Z.
- `estimated_y`: projected **structure centre Y**, never a substitute
  for actual vanilla height.
- `distance_from_center` and `distance_from_origin`: block distance,
  with two decimal places, to selected X/Z and to world (0,0).
- `chunk_x` and `chunk_z`: start chunk coordinates.
- `status`: `estimated_only` for this workflow, never `verified_tower`.
- Results are validated against seed, version, Y threshold, X/Z bounds,
  evidence class, row count and duplicate positions before atomic CSV write.
- The original engine CSV and `.state.json` remain under `results/.engine/`
  for diagnostics and advanced checkpoint recovery.
- Clicking Export CSV copies the completed canonical CSV elsewhere.

## Verification / 測試

```bash
python3 scripts/run_headless_tests.py
python3 -m unittest tests.test_simple_home_workflow -v
# Linux GUI integration (requires xvfb):
xvfb-run -a python3 -m unittest tests.test_simple_home_tk -v
```

GitHub Actions `Native estimated-height smoke` compiles from pinned upstream
source and performs one limited seed-only search on macOS and Ubuntu.
This is not an original Minecraft world-generation proof.

## Troubleshooting

- **CMake or compiler missing:** install the indicated system prerequisites,
  then reopen the launcher or choose Settings → Retry C build.
- **No results / long search:** Y < -37 may be rare. Progress logs show rings;
  Stop cancels the active subprocess. A partial raw checkpoint remains in
  `results/.engine/`.
- **Old CSV collision:** new searches generate unique filenames, never
  overwrite an existing results CSV.
- **macOS bad window path:** the advanced Tk window cancels pending idle
  resize callbacks and guards destroyed widgets.
