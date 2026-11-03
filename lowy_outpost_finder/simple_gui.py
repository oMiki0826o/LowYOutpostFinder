"""Minimal monochrome low-Y outpost home; advanced searches stay in gui.py."""
from __future__ import annotations

import csv
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .native_bootstrap import BootstrapError, ensure_native_estimator
from .paths import PROJECT_ROOT, cli_command
from .process_control import launch_scanner, stop_scanner
from .simple_workflow import (
    PUBLIC_FIELDS, SimpleRequest, build_search_arguments, export_results,
    unique_output_paths,
)


TEXT = {
    'zh-TW': {
        'subtitle': 'Minecraft Java · 低 Y 掠奪者前哨站搜尋',
        'version': '遊戲版本', 'seed': '世界種子碼', 'y': '結構中心高度低於',
        'top': '搜尋結果數量', 'radius': '搜尋半徑（方塊）',
        'center': '搜尋中心 (0, 0) · 全圖範圍',
        'search': '開始搜尋低 Y 前哨站', 'stop': '停止搜尋',
        'setup': '正在準備 C 高度估算引擎…', 'ready': 'C 引擎已就緒',
        'not_ready': '尚未準備 C 引擎', 'running': '正在搜尋近似低 Y 前哨站…',
        'results': '搜尋結果', 'logs': '執行紀錄', 'export': '匯出 CSV',
        'settings': '設定與其他模式', 'advanced': '進階工作模式',
        'engine': '重新檢查／編譯 C 引擎', 'theme': '切換黑白／淺色',
        'language': 'English', 'cancelled': '搜尋已取消',
        'setup_fail': '無法準備 C 搜尋器', 'search_fail': '搜尋失敗',
        'save_as': '匯出結果 CSV', 'no_results': '目前沒有可匯出的結果',
        'error': '錯誤', 'completed': '搜尋完成：{count} 筆近似候選',
        'insufficient': '搜尋結束：範圍內只找到 {count} 筆近似候選',
        'note': ('這些是 C 引擎推算的結構中心 Y，不是原版實測；'
                 '已依水平距離排序，但環狀提前停止尚不能保證全球最近 N 筆。'),
        'tip': '搜尋中心預設為世界原點 (0,0)，不一定是實際出生點。進階模式可調整中心。',
        'status_initial': '尚未開始搜尋',
        'mode_candidates': '種子候選（僅 X/Z）',
        'mode_full-map': '全圖搜尋（進階）',
        'mode_estimate': '舊版高度推算',
        'mode_world': '讀取既有世界',
        'mode_verify': '驗證候選存檔',
        'mode_search-live': '現成伺服器實測',
        'mode_seed-vanilla': '原版生成實測',
        'mode_seed-geometry': '種子幾何（無 Y）',
    },
    'en-US': {
        'subtitle': 'Minecraft Java · Low-Y Pillager Outpost Search',
        'version': 'Game version', 'seed': 'World seed', 'y': 'Structure centre Y below',
        'top': 'Number of results', 'radius': 'Search radius (blocks)',
        'center': 'Centre (0, 0) · Whole-world range',
        'search': 'Search estimated low-Y outposts', 'stop': 'Stop',
        'setup': 'Preparing C height estimator…', 'ready': 'C engine ready',
        'not_ready': 'C engine not ready', 'running': 'Searching estimated low-Y outposts…',
        'results': 'Results', 'logs': 'Execution log', 'export': 'Export CSV',
        'settings': 'Settings and other modes', 'advanced': 'Advanced modes',
        'engine': 'Retry / build C height engine', 'theme': 'Toggle black/white theme',
        'language': '繁體中文', 'cancelled': 'Search cancelled',
        'setup_fail': 'C engine setup failed', 'search_fail': 'Search failed',
        'save_as': 'Export results CSV', 'no_results': 'No result CSV to export',
        'error': 'Error', 'completed': 'Search finished: {count} estimated candidates',
        'insufficient': 'Search exhausted: only {count} estimated candidates found',
        'note': ('C-estimated structure-centre Y, not vanilla verification. '
                 'Results are ranked by horizontal distance; centre-out ring stopping '
                 'does not prove globally nearest N.'),
        'tip': 'Default centre is (0,0), not necessarily world spawn. Advanced mode can change it.',
        'status_initial': 'No search started',
        'mode_candidates': 'Seed placement (X/Z only)',
        'mode_full-map': 'Full map (advanced)',
        'mode_estimate': 'Legacy height estimate',
        'mode_world': 'Saved world inspection',
        'mode_verify': 'Verify candidate CSV',
        'mode_search-live': 'Existing server verification',
        'mode_seed-vanilla': 'Generate with vanilla server',
        'mode_seed-geometry': 'Seed geometry (no Y)',
    },
}

HEADINGS = {
    'zh-TW': ('版本', '種子', '序號', 'X', '估算 Y', 'Z',
              '距離搜尋中心', '距離 (0,0)', '區塊 X', '區塊 Z', '狀態'),
    'en-US': ('Version', 'Seed', '#', 'X', 'Estimated Y', 'Z',
              'Centre distance', 'Origin distance', 'Chunk X', 'Chunk Z', 'Status'),
}

ADVANCED_MODES = (
    'candidates', 'full-map', 'estimate', 'world', 'verify',
    'search-live', 'seed-vanilla', 'seed-geometry',
)

DARK = {
    'bg': '#000000', 'surface': '#080808', 'fg': '#ffffff',
    'muted': '#aaaaaa', 'border': '#444444', 'raised': '#171717',
    'selected': '#333333', 'button': '#ffffff', 'button_fg': '#000000',
}
LIGHT = {
    'bg': '#ffffff', 'surface': '#ffffff', 'fg': '#080808',
    'muted': '#555555', 'border': '#aaaaaa', 'raised': '#efefef',
    'selected': '#dddddd', 'button': '#080808', 'button_fg': '#ffffff',
}


class SimpleApp(tk.Tk):
    def __init__(self, language: str = 'zh-TW', *, auto_prepare: bool = True):
        super().__init__()
        if language not in TEXT:
            raise ValueError('Unsupported language')
        self.language = language
        self.theme_mode = 'dark'
        self.events: queue.Queue = queue.Queue()
        self.cancel_event = threading.Event()
        self._closing = False
        self._ready = False
        self._busy = False
        self._setup_active = False
        self._poll_id = None
        self._setup_timer = None
        self.process: subprocess.Popen | None = None
        self.last_output: Path | None = None
        self.result_rows: list[dict] = []
        self.title('LowYOutpostFinder')
        self.geometry('1030x770')
        self.minsize(740, 600)
        self.vars = {
            'version': tk.StringVar(value='1.21.8'),
            'seed': tk.StringVar(value=''),
            'max_y': tk.StringVar(value='-37'),
            'top': tk.StringVar(value='25'),
            'radius': tk.StringVar(value='30000000'),
        }
        self.status = tk.StringVar(value=self.t('not_ready'))
        self._build()
        self._apply_theme()
        self._poll_id = self.after(120, self._poll)
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        if auto_prepare:
            self._setup_timer = self.after(100, self._prepare_backend)

    def t(self, key: str, **kw) -> str:
        return TEXT[self.language][key].format(**kw)

    def _label(self, parent, text, size=11, *, muted=False, bold=False, **pack):
        widget = tk.Label(parent, text=text, anchor='w',
                          font=('Arial', size, 'bold' if bold else 'normal'))
        widget.pack(**pack)
        widget._muted = muted
        return widget

    def _entry_field(self, parent, title: str, variable: tk.StringVar,
                     *, version: bool = False):
        frame = tk.Frame(parent)
        frame.pack(fill='x', expand=True)
        label = self._label(frame, title, 11, pady=(4, 6), anchor='w')
        if version:
            field = ttk.Combobox(frame, textvariable=variable,
                                 values=('1.21.8',), state='readonly')
        else:
            field = tk.Entry(frame, textvariable=variable, font=('Arial', 12),
                             highlightthickness=1, relief='flat', bd=0)
        field.pack(fill='x', ipady=11)
        return label, field

    def _build(self):
        self.outer = tk.Frame(self, highlightthickness=1)
        self.outer.pack(fill='both', expand=True, padx=14, pady=14)
        self.body = tk.Frame(self.outer)
        self.body.pack(fill='both', expand=True, padx=20, pady=17)
        header = tk.Frame(self.body)
        header.pack(fill='x')
        headline = tk.Frame(header)
        headline.pack(side='left', fill='x', expand=True)
        self.title_label = self._label(headline, 'LowYOutpostFinder', 18, bold=True,
                                       anchor='w')
        self.subtitle_label = self._label(headline, self.t('subtitle'), 10,
                                          muted=True, anchor='w', pady=(5, 0))
        self.settings_btn = tk.Button(header, text='☷', width=3, font=('Arial', 20),
                                      relief='flat', bd=0, command=self._open_settings)
        self.settings_btn.pack(side='right', anchor='n')

        self.form = tk.Frame(self.body)
        self.form.pack(fill='x', pady=(18, 0))
        self.labels = {}
        self.labels['version'], self.version_field = self._entry_field(
            self.form, self.t('version'), self.vars['version'], version=True)
        self.labels['seed'], self.seed_field = self._entry_field(
            self.form, self.t('seed'), self.vars['seed'])
        self.fields_row = tk.Frame(self.form)
        self.fields_row.pack(fill='x', pady=(0, 0))
        y_col = tk.Frame(self.fields_row)
        y_col.pack(side='left', fill='x', expand=True, padx=(0, 8))
        top_col = tk.Frame(self.fields_row)
        top_col.pack(side='left', fill='x', expand=True, padx=(8, 0))
        self.labels['y'], self.y_field = self._entry_field(
            y_col, self.t('y'), self.vars['max_y'])
        self.labels['top'], self.top_field = self._entry_field(
            top_col, self.t('top'), self.vars['top'])
        self.labels['radius'], self.radius_field = self._entry_field(
            self.form, self.t('radius'), self.vars['radius'])

        summary = tk.Frame(self.form)
        summary.pack(fill='x', pady=(15, 8))
        self.center_label = self._label(summary, self.t('center'), 10,
                                         muted=True, side='left')
        self.advanced_link = tk.Button(
            summary, text=self.t('advanced') + '  ›', relief='flat',
            command=self._open_settings, borderwidth=0)
        self.advanced_link.pack(side='right')
        self.search_btn = tk.Button(self.body, text=self.t('search'),
                                    font=('Arial', 12, 'bold'), relief='flat',
                                    command=self._start_search, state='disabled',
                                    padx=10, pady=12, borderwidth=0)
        self.search_btn.pack(fill='x', pady=(10, 8))
        self.stop_btn = tk.Button(self.body, text=self.t('stop'), font=('Arial', 10),
                                  relief='flat', command=self._stop_search,
                                  state='disabled', pady=6, borderwidth=0)
        self.stop_btn.pack(fill='x', pady=(0, 9))
        self.engine_status = self._label(self.body, self.t('not_ready'), 10,
                                         muted=True, fill='x', pady=(0, 4))
        self.progress = ttk.Progressbar(self.body, mode='indeterminate', length=180)
        self.progress.pack(fill='x', pady=(0, 9))
        self._separator = tk.Frame(self.body, height=1)
        self._separator.pack(fill='x', pady=(8, 12))

        result_header = tk.Frame(self.body)
        result_header.pack(fill='x', pady=(2, 7))
        self.result_heading = self._label(result_header, self.t('results'), 13,
                                          bold=True, side='left')
        self.export_btn = tk.Button(result_header, text=self.t('export'),
                                    relief='flat', borderwidth=0,
                                    command=self._export_csv, state='disabled')
        self.export_btn.pack(side='right')
        self.notebook = ttk.Notebook(self.body)
        self.notebook.pack(fill='both', expand=True)
        results_frame = tk.Frame(self.notebook)
        self.notebook.add(results_frame, text=self.t('results'))
        log_frame = tk.Frame(self.notebook)
        self.notebook.add(log_frame, text=self.t('logs'))
        tree_area = tk.Frame(results_frame)
        tree_area.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(tree_area, show='headings', columns=PUBLIC_FIELDS)
        self.tree.pack(side='left', fill='both', expand=True)
        y_scroll = ttk.Scrollbar(tree_area, orient='vertical', command=self.tree.yview)
        y_scroll.pack(side='right', fill='y')
        x_scroll = ttk.Scrollbar(results_frame, orient='horizontal', command=self.tree.xview)
        x_scroll.pack(fill='x')
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        for key, heading in zip(PUBLIC_FIELDS, HEADINGS[self.language]):
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=120 if key != 'seed' else 170,
                             stretch=False, anchor='center')
        self.log_text = tk.Text(log_frame, font=('Menlo', 10), relief='flat',
                                wrap='word', state='disabled')
        self.log_text.pack(fill='both', expand=True)
        self.note_label = self._label(self.body, self.t('note'), 9, muted=True,
                                      fill='x', pady=(9, 1))
        self.note_label.configure(wraplength=900, justify='left')
        self._open_windows = []

    def _apply_theme(self):
        palette = DARK if self.theme_mode == 'dark' else LIGHT
        s = ttk.Style(self)
        if 'clam' in s.theme_names():
            s.theme_use('clam')
        s.configure('TCombobox', fieldbackground=palette['surface'],
                    background=palette['raised'], foreground=palette['fg'],
                    arrowcolor=palette['fg'], bordercolor=palette['border'])
        s.map('TCombobox', fieldbackground=[('readonly', palette['surface'])],
              foreground=[('readonly', palette['fg'])])
        s.configure('TNotebook', background=palette['bg'], borderwidth=0)
        s.configure('TNotebook.Tab', padding=(14, 6), background=palette['raised'],
                    foreground=palette['fg'])
        s.map('TNotebook.Tab', background=[('selected', palette['surface'])],
              foreground=[('selected', palette['fg'])])
        s.configure('Treeview', background=palette['surface'],
                    fieldbackground=palette['surface'], foreground=palette['fg'],
                    rowheight=27, borderwidth=0)
        s.configure('Treeview.Heading', background=palette['raised'],
                    foreground=palette['fg'], font=('Arial', 10, 'bold'))
        s.map('Treeview', background=[('selected', palette['selected'])],
              foreground=[('selected', palette['fg'])])
        s.configure('Horizontal.TProgressbar', background=palette['fg'],
                    troughcolor=palette['raised'], borderwidth=0)
        self.tree.tag_configure('estimated_only', foreground=palette['muted'])
        self.configure(bg=palette['bg'])

        def repaint(widget):
            if isinstance(widget, (tk.Tk, tk.Toplevel, tk.Frame, tk.LabelFrame)):
                widget.configure(bg=palette['bg'])
            if isinstance(widget, tk.Label):
                widget.configure(bg=palette['bg'],
                                 fg=palette['muted'] if getattr(widget, '_muted', False)
                                 else palette['fg'])
            if isinstance(widget, tk.Entry):
                widget.configure(bg=palette['surface'], fg=palette['fg'],
                                 insertbackground=palette['fg'],
                                 highlightbackground=palette['border'],
                                 highlightcolor=palette['fg'])
            if isinstance(widget, tk.Button):
                primary = widget is self.search_btn
                widget.configure(
                    bg=palette['button'] if primary else palette['bg'],
                    fg=palette['button_fg'] if primary else palette['fg'],
                    activebackground=palette['selected'] if not primary else palette['muted'],
                    activeforeground=palette['fg'] if not primary else palette['button_fg'],
                    disabledforeground=palette['muted'],
                    highlightbackground=palette['bg'])
            if isinstance(widget, tk.Text):
                widget.configure(bg=palette['surface'], fg=palette['fg'],
                                 insertbackground=palette['fg'],
                                 selectbackground=palette['selected'])
            for child in widget.winfo_children():
                repaint(child)
        repaint(self)
        self.outer.configure(highlightbackground=palette['border'])
        self._separator.configure(bg=palette['border'])

    def _translate(self):
        self.subtitle_label.configure(text=self.t('subtitle'))
        for key, lab in self.labels.items():
            lab.configure(text=self.t(key))
        self.center_label.configure(text=self.t('center'))
        self.advanced_link.configure(text=self.t('advanced') + '  ›')
        self.settings_btn.configure(text='☷')
        self.search_btn.configure(text=self.t('search'))
        self.stop_btn.configure(text=self.t('stop'))
        self.result_heading.configure(text=self.t('results'))
        self.export_btn.configure(text=self.t('export'))
        self.note_label.configure(text=self.t('note'), wraplength=max(480, self.winfo_width()-100))
        self.notebook.tab(0, text=self.t('results'))
        self.notebook.tab(1, text=self.t('logs'))
        for key, label in zip(PUBLIC_FIELDS, HEADINGS[self.language]):
            self.tree.heading(key, text=label)

    def _open_settings(self):
        if self._closing:
            return
        panel = tk.Toplevel(self)
        panel.title(self.t('settings'))
        panel.geometry('475x590')
        panel.minsize(340, 380)
        panel.transient(self)
        frame = tk.Frame(panel)
        frame.pack(fill='both', expand=True, padx=22, pady=22)
        heading = tk.Label(frame, text=self.t('settings'), font=('Arial', 17, 'bold'))
        heading.pack(anchor='w', pady=(0, 15))
        controls = [
            (self.t('engine'), lambda: (panel.destroy(), self._prepare_backend())),
            (self.t('theme'), lambda: (panel.destroy(), self._toggle_theme())),
            (self.t('language'), lambda: (panel.destroy(), self._toggle_language())),
        ]
        for label, action in controls:
            tk.Button(frame, text=label, command=action, anchor='w',
                      padx=12, pady=7).pack(fill='x', pady=2)
        tk.Label(frame, text=self.t('advanced'), anchor='w',
                 font=('Arial', 13, 'bold')).pack(fill='x', pady=(17, 7))
        for mode in ADVANCED_MODES:
            tk.Button(frame, text=self.t('mode_' + mode), anchor='w',
                      command=lambda m=mode: self._open_advanced(m),
                      padx=12, pady=3).pack(fill='x', pady=1)
        colors = DARK if self.theme_mode == 'dark' else LIGHT
        panel.configure(bg=colors['bg'])
        frame.configure(bg=colors['bg'])
        for child in frame.winfo_children():
            if isinstance(child, tk.Label):
                child.configure(bg=colors['bg'], fg=colors['fg'])
            elif isinstance(child, tk.Button):
                child.configure(bg=colors['raised'], fg=colors['fg'],
                                activebackground=colors['selected'],
                                activeforeground=colors['fg'], relief='flat')
        self._open_windows.append(panel)

    def _open_advanced(self, mode: str):
        """Preserve the original feature-complete UI in a separate process."""
        subprocess.Popen(
            [sys.executable, '-m', 'lowy_outpost_finder.gui',
             '--lang', self.language, '--mode', mode],
            cwd=PROJECT_ROOT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def _toggle_theme(self):
        self.theme_mode = 'light' if self.theme_mode == 'dark' else 'dark'
        self._apply_theme()

    def _toggle_language(self):
        self.language = 'en-US' if self.language == 'zh-TW' else 'zh-TW'
        self._translate()

    def _prepare_backend(self):
        self._setup_timer = None
        if self._setup_active or self._busy or self._closing:
            return
        # A prior stopped search may have set this event. A deliberate retry
        # must start with a fresh cancellation state.
        self.cancel_event.clear()
        self._setup_active = True
        self._ready = False
        self.search_btn.configure(state='disabled')
        self.engine_status.configure(text=self.t('setup'))
        self.status.set(self.t('setup'))
        self.progress.configure(mode='indeterminate')
        self.progress.start(15)

        def worker():
            try:
                ensure_native_estimator(
                    status=lambda message: self.events.put(('setup_log', message)),
                    cancel_event=self.cancel_event)
                self.events.put(('ready', True, ''))
            except Exception as exc:
                self.events.put(('ready', False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _start_search(self):
        if not self._ready or self._busy or self._closing:
            return
        request = SimpleRequest(
            version=self.vars['version'].get(), seed=self.vars['seed'].get(),
            max_y=self.vars['max_y'].get(), top=self.vars['top'].get(),
            radius=self.vars['radius'].get())
        raw, public = unique_output_paths(PROJECT_ROOT / 'results')
        try:
            arguments = build_search_arguments(request, raw)
        except ValueError as exc:
            messagebox.showerror(self.t('error'), str(exc), parent=self)
            return
        self._busy = True
        self.cancel_event.clear()
        self.search_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.export_btn.configure(state='disabled')
        self.engine_status.configure(text=self.t('running'))
        self.status.set(self.t('running'))
        self.progress.configure(mode='indeterminate')
        self.progress.start(15)
        self.result_rows = []
        self.last_output = None
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.notebook.select(1)
        self._append_log(f'--- {self.t("running")} ---')
        self._append_log(' '.join((request.version, 'seed=' + request.seed,
                                   'Y < ' + request.max_y, 'radius=' + request.radius,
                                   'top=' + request.top)))
        threading.Thread(
            target=self._search_worker, args=(request, arguments, raw, public),
            daemon=True).start()

    def _search_worker(self, req: SimpleRequest, argv: list[str],
                       raw: Path, public: Path) -> None:
        try:
            raw.parent.mkdir(parents=True, exist_ok=True)
            process = launch_scanner(
                cli_command(*argv), cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace', bufsize=1,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.process = process
            assert process.stdout is not None
            if self.cancel_event.is_set():
                stop_scanner(process)
            for line in process.stdout:
                self.events.put(('log', line.rstrip()))
                if self.cancel_event.is_set() and process.poll() is None:
                    stop_scanner(process)
            code = process.wait()
            if self.cancel_event.is_set():
                self.events.put(('cancelled',))
                return
            if code != 0:
                self.events.put(('search_error', f'Exit code {code}. See execution log.'))
                return
            rows = export_results(raw, public, req)
            self.events.put(('finished', rows, str(public), str(raw.with_suffix('.state.json'))))
        except (OSError, ValueError, RuntimeError, csv.Error) as exc:
            self.events.put(('search_error', str(exc)))
        finally:
            self.process = None

    def _stop_search(self):
        self.cancel_event.set()
        if self.process is not None and self.process.poll() is None:
            stop_scanner(self.process)
        self.stop_btn.configure(state='disabled')

    def _append_log(self, line: str):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', str(line).rstrip() + '\n')
        if int(self.log_text.index('end-1c').split('.')[0]) > 500:
            self.log_text.delete('1.0', '70.0')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _explain_bootstrap_error(self, detail: str) -> str:
        if self.language == 'en-US':
            return detail
        return (
            '目前尚無法自動編譯 C 高度搜尋器。請確認 Git、CMake 與 C11 編譯器已安裝。\n'
            'macOS：請先安裝 Xcode Command Line Tools 及 CMake；'
            'Ubuntu：請安裝 git、cmake、build-essential。\n'
            '安裝完成後可在右上角設定重新嘗試。\n'
            '詳細訊息：' + detail
        )

    def _poll(self):
        if self._closing:
            return
        try:
            for _ in range(80):
                event = self.events.get_nowait()
                kind = event[0]
                if kind == 'setup_log':
                    self._append_log(event[1])
                    self.engine_status.configure(text=event[1])
                elif kind == 'ready':
                    self._setup_active = False
                    self._ready = event[1]
                    self.progress.stop()
                    self.engine_status.configure(
                        text=self.t('ready') if self._ready else self.t('setup_fail'))
                    if self._ready:
                        self.search_btn.configure(state='normal')
                    else:
                        explanation = self._explain_bootstrap_error(event[2])
                        self._append_log(explanation)
                        self.notebook.select(1)
                        messagebox.showerror(self.t('setup_fail'), explanation, parent=self)
                elif kind == 'log':
                    self._append_log(event[1])
                    match = re.match(r'^FULLMAP_ESTIMATE_PROGRESS (\d+) (\d+|ring) (\d+) ', event[1])
                    if match:
                        self.engine_status.configure(text=(
                            f'Scanned {match[1]} rings, {match[3]} estimated matches'
                            if self.language == 'en-US' else
                            f'已掃描 {match[1]} 環；符合近似條件 {match[3]} 筆'))
                elif kind == 'finished':
                    _kind, rows, path, state_file = event
                    self._busy = False
                    self.progress.stop()
                    self.stop_btn.configure(state='disabled')
                    self.search_btn.configure(state='normal')
                    self.result_rows = rows
                    self.last_output = Path(path)
                    for row in rows[:500]:
                        self.tree.insert('', 'end', values=[
                            row[col] for col in PUBLIC_FIELDS],
                            tags=('estimated_only',))
                    self.export_btn.configure(state='normal')
                    count = len(rows)
                    incomplete = False
                    try:
                        import json
                        s = json.loads(Path(state_file).read_text(encoding='utf-8'))
                        incomplete = s.get('status') == 'exhausted_estimated_only'
                    except (OSError, ValueError):
                        pass
                    label = self.t('insufficient' if incomplete else 'completed', count=count)
                    self.engine_status.configure(text=label)
                    self.notebook.select(0)
                    self._append_log(label + ' → ' + path)
                elif kind in ('cancelled', 'search_error'):
                    self._busy = False
                    self.progress.stop()
                    self.stop_btn.configure(state='disabled')
                    self.search_btn.configure(state='normal' if self._ready else 'disabled')
                    message = self.t('cancelled') if kind == 'cancelled' else event[1]
                    self.engine_status.configure(text=message)
                    self._append_log(message)
                    if kind == 'search_error':
                        self.notebook.select(1)
                        messagebox.showerror(self.t('search_fail'), message, parent=self)
        except queue.Empty:
            pass
        if not self._closing:
            self._poll_id = self.after(120, self._poll)

    def _export_csv(self):
        if self.last_output is None or not self.last_output.is_file():
            messagebox.showinfo(self.t('export'), self.t('no_results'), parent=self)
            return
        target = filedialog.asksaveasfilename(parent=self, title=self.t('save_as'),
                                              defaultextension='.csv',
                                              filetypes=[('CSV', '*.csv')])
        if target and self.last_output.resolve() != Path(target).resolve():
            shutil.copyfile(self.last_output, target)

    def _on_close(self):
        if self._closing:
            return
        self._closing = True
        self.cancel_event.set()
        if self._setup_timer is not None:
            try:
                self.after_cancel(self._setup_timer)
            except tk.TclError:
                pass
            self._setup_timer = None
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        if self.process is not None and self.process.poll() is None:
            stop_scanner(self.process)
        for window in self._open_windows:
            try:
                if window.winfo_exists():
                    window.destroy()
            except tk.TclError:
                pass
        super().destroy()

    def destroy(self):
        if self._closing:
            return super().destroy()
        self._on_close()


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Minimal low-Y graphical interface')
    parser.add_argument('--lang', choices=tuple(TEXT), default='zh-TW')
    args = parser.parse_args(argv)
    SimpleApp(language=args.lang).mainloop()


if __name__ == '__main__':
    main()
