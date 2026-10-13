"""File: explorer_gui.py
Modification: 2026-10-13 — bilingual single-seed / seed-list explorer GUI.

The GUI intentionally labels Y estimates as unverified and never invents
teleport heights for candidate-only results.
"""
from __future__ import annotations

import csv
from datetime import timedelta
from pathlib import Path
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from explorer import (Explorer, RegionBounds, MAX_REGIONS, FIELDS, load_seeds,
                      export_seed_list, export_teleports)
from finder import signed_seed, write_csv
import argparse
from versions import VERSIONS

LABELS = {
    'zh-TW': {
        'title': '進階搜尋｜單種子與種子清單', 'single': '單種子', 'batch': '種子清單',
        'mode': '搜尋類型', 'candidate': '位置候選（無 Y）', 'estimate': '試驗性近似 Y（1.21.8）',
        'version': 'Minecraft 版本', 'seed': '世界種子', 'file': '種子清單（.txt）',
        'browse': '選取檔案', 'threads': '同時處理種子數', 'top': '每種子結果數上限',
        'radius': '近似高度模式搜尋半徑（方塊）', 'max_y': '近似高度 Y 上限',
        'bounds': '矩形範圍（512 方塊一格，含兩端）',
        'min_x': '最小 X', 'max_x': '最大 X', 'min_z': '最小 Z', 'max_z': '最大 Z',
        'world': '設為世界邊界', 'default': '預設小範圍',
        'note': '位置候選沒有 Y；近似高度並非前哨站真實 Y。精確 Y 需用原版世界驗證。',
        'start': '開始', 'pause': '暫停', 'resume': '繼續', 'stop': '停止',
        'save': '匯出 CSV', 'seeds': '匯出種子', 'tp': '匯出座標文字',
        'sort_y': '按近似 Y 排序', 'sort_distance': '按原點距離排序', 'sort_seed': '按種子排序',
        'progress': '已完成 {done}/{total} 種子；{rows} 筆；預計剩餘 {eta}',
        'region_progress': '候選區域掃描 {done}/{total} 列',
        'done': '完成：{rows} 筆（未經原版生成確認）', 'stopped': '已停止：結果尚未完整',
        'error': '操作失敗', 'ready': '準備就緒', 'all_regions': '所選面積超過安全限制，請分區搜尋',
        'filedialog': '選擇文字種子清單', 'save_csv': '儲存 CSV', 'save_text': '儲存文字檔',
        'tip': '候選＝結構嘗試點｜近似 Y＝未對拍地形樣本｜確認 Y＝原版存檔結構高度',
    },
    'en-US': {
        'title': 'Advanced explorer | Single seed / seed list', 'single': 'Single seed',
        'batch': 'Seed list', 'mode': 'Search kind', 'candidate': 'Placement only (no Y)',
        'estimate': 'Experimental Y approximation (1.21.8)', 'version': 'Minecraft version',
        'seed': 'World seed', 'file': 'Seed list (.txt)', 'browse': 'Browse',
        'threads': 'Parallel seed workers', 'top': 'Max rows per seed',
        'radius': 'Approximate-height search radius (blocks)', 'max_y': 'Approximate Y maximum',
        'bounds': 'Rectangle (512-block regions; inclusive)',
        'min_x': 'Min X', 'max_x': 'Max X', 'min_z': 'Min Z', 'max_z': 'Max Z',
        'world': 'Reset to world bounds', 'default': 'Small default area',
        'note': 'Placement candidates have no Y. Approximations are not actual outpost heights. Confirm Y using vanilla worlds.',
        'start': 'Start', 'pause': 'Pause', 'resume': 'Resume', 'stop': 'Stop',
        'save': 'Export CSV', 'seeds': 'Export seeds', 'tp': 'Export coordinates',
        'sort_y': 'Sort by approximate Y', 'sort_distance': 'Sort by origin distance',
        'sort_seed': 'Sort by seed', 'progress': 'Completed {done}/{total} seeds; '
                    '{rows} rows; estimated remaining {eta}',
        'region_progress': 'Scanning region rows {done}/{total}',
        'done': 'Finished: {rows} rows (not vanilla-generation verified)',
        'stopped': 'Stopped: results are incomplete', 'error': 'Search failed',
        'ready': 'Ready', 'all_regions': 'Area exceeds safety cap; scan smaller sections',
        'filedialog': 'Select plain-text seed list', 'save_csv': 'Save CSV',
        'save_text': 'Save text file',
        'tip': 'Candidate = placement attempt | Approximate Y = unverified terrain sample | Verified Y = vanilla saved structure',
    },
}
assert set(LABELS['zh-TW']) == set(LABELS['en-US'])


class AdvancedWindow(tk.Toplevel):
    def __init__(self, master, language='zh-TW'):
        super().__init__(master)
        self.language = language
        self.title(self.t('title'))
        self.geometry('1030x750')
        self.minsize(840, 610)
        self.events = queue.Queue()
        self.worker = None
        self.cancel = threading.Event()
        self.pause = threading.Event()
        self.pause.set()
        self.started = 0.0
        self.rows: list[dict] = []
        self.mode = tk.StringVar(value='candidates')
        self.tab = tk.StringVar(value='single')
        self.values = {k: tk.StringVar(value=v) for k, v in {
            'seed': '123', 'file': '', 'version': '1.21.8', 'threads': '2',
            'top': '500', 'min_x': '-16', 'max_x': '16', 'min_z': '-16', 'max_z': '16',
            'radius': '8192', 'max_y': '0',
        }.items()}
        self.caption = tk.StringVar(value=self.t('ready'))
        self._build()
        self._set_language()
        self._poll_id = self.after(120, self._poll)
        self.protocol('WM_DELETE_WINDOW', self._close)

    def t(self, key, **data):
        return LABELS[self.language][key].format(**data)

    def _build(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill='both', expand=True)
        self.tip_label = ttk.Label(root, text='', wraplength=950)
        self.tip_label.pack(anchor='w', pady=(0, 10))
        tabs = ttk.Frame(root)
        tabs.pack(fill='x')
        self.tab_buttons = {}
        for kind in ('single', 'batch'):
            w = ttk.Radiobutton(tabs, variable=self.tab, value=kind,
                                command=self._toggle, text=kind)
            w.pack(side='left', padx=6)
            self.tab_buttons[kind] = w
        settings = ttk.Frame(root)
        settings.pack(fill='x', pady=8)
        self.fields = {}
        for key in ('seed', 'file', 'version', 'threads', 'top', 'radius', 'max_y',
                    'min_x', 'max_x', 'min_z', 'max_z'):
            row = ttk.Frame(settings)
            row.pack(fill='x', pady=2)
            label = ttk.Label(row, text=key, width=36)
            label.pack(side='left')
            if key == 'version':
                w = ttk.Combobox(row, textvariable=self.values[key], state='readonly',
                                 values=[v.id for v in VERSIONS])
            else:
                w = ttk.Entry(row, textvariable=self.values[key])
            w.pack(side='left', fill='x', expand=True)
            if key == 'file':
                self.browse_button = ttk.Button(row, command=self._browse)
                self.browse_button.pack(side='left', padx=4)
            self.fields[key] = (row, label, w)
        option_line = ttk.Frame(settings)
        option_line.pack(fill='x', pady=6)
        self.kind_label = ttk.Label(option_line)
        self.kind_label.pack(side='left', padx=(0, 7))
        self.kind_buttons = {}
        for kind in ('candidate', 'estimate'):
            b = ttk.Radiobutton(option_line, variable=self.mode,
                                 value='candidates' if kind == 'candidate' else 'estimate',
                                 command=self._toggle)
            b.pack(side='left', padx=4)
            self.kind_buttons[kind] = b
        self.bound_buttons = {}
        for key, callback in (('world', self._world), ('default', self._default)):
            w = ttk.Button(option_line, command=callback)
            w.pack(side='left', padx=7)
            self.bound_buttons[key] = w
        actions = ttk.Frame(root)
        actions.pack(fill='x', pady=4)
        self.buttons = {}
        for name, command in (('start', self._start), ('pause', self._pause),
                              ('resume', self._resume), ('stop', self._stop),
                              ('sort_y', lambda: self._sort('y')),
                              ('sort_distance', lambda: self._sort('distance')),
                              ('sort_seed', lambda: self._sort('seed'))):
            b = ttk.Button(actions, command=command)
            b.pack(side='left', padx=2)
            self.buttons[name] = b
        self.bar = ttk.Progressbar(root, mode='determinate', maximum=100)
        self.bar.pack(fill='x', pady=5)
        ttk.Label(root, textvariable=self.caption).pack(anchor='w', pady=(0, 5))
        listing = ttk.Frame(root)
        listing.pack(fill='both', expand=True)
        self.table = ttk.Treeview(listing, columns=FIELDS, show='headings', height=8)
        vscroll = ttk.Scrollbar(listing, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=vscroll.set)
        self.table.pack(side='left', fill='both', expand=True)
        vscroll.pack(side='right', fill='y')
        hscroll = ttk.Scrollbar(root, orient='horizontal', command=self.table.xview)
        self.table.configure(xscrollcommand=hscroll.set)
        hscroll.pack(fill='x')
        for field in FIELDS:
            self.table.heading(field, text=field)
            self.table.column(field, width=145 if field in ('classification', 'projected_surface_y') else 105,
                              anchor='center', stretch=False)
        downloads = ttk.Frame(root)
        downloads.pack(fill='x', pady=(9, 1))
        for key, callback in (('save', self._save), ('seeds', self._export_seeds), ('tp', self._export_tp)):
            b = ttk.Button(downloads, command=callback)
            b.pack(side='left', padx=4)
            self.buttons[key] = b
        self._toggle()

    def _set_language(self):
        self.title(self.t('title'))
        self.tip_label.configure(text=self.t('note'))
        self.kind_label.configure(text=self.t('mode'))
        self.browse_button.configure(text=self.t('browse'))
        for key, button in self.buttons.items():
            button.configure(text=self.t(key))
        for key, button in self.kind_buttons.items():
            button.configure(text=self.t(key))
        for key, button in self.tab_buttons.items():
            button.configure(text=self.t(key))
        for key, button in self.bound_buttons.items():
            button.configure(text=self.t(key))
        for key, (_, label, _) in self.fields.items():
            label.configure(text=self.t(key))
        self._toggle()

    def change_language(self, language):
        if language != self.language:
            self.language = language
            self._set_language()

    def _toggle(self, _event=None):
        search = self.mode.get()
        tab = self.tab.get()
        for key, (row, _, _) in self.fields.items():
            visible = key in ('version', 'threads', 'top')
            visible |= (key == 'seed' and tab == 'single') or (key == 'file' and tab == 'batch')
            visible |= (key in ('radius', 'max_y') if search == 'estimate' else
                        key in ('min_x', 'max_x', 'min_z', 'max_z'))
            if visible:
                row.pack(fill='x', pady=2)
            else:
                row.pack_forget()
        if search == 'estimate':
            self.fields['version'][2].configure(values=['1.21.8'])
            self.values['version'].set('1.21.8')
        else:
            self.fields['version'][2].configure(values=[v.id for v in VERSIONS])
        running = self.worker is not None and self.worker.is_alive()
        self.buttons['start'].configure(state='disabled' if running else 'normal')
        self.buttons['pause'].configure(state='normal' if running and self.pause.is_set() else 'disabled')
        self.buttons['resume'].configure(state='normal' if running and not self.pause.is_set() else 'disabled')
        self.buttons['stop'].configure(state='normal' if running else 'disabled')

    def _browse(self):
        path = filedialog.askopenfilename(title=self.t('filedialog'), filetypes=[('Text', '*.txt'), ('All', '*')])
        if path:
            self.values['file'].set(path)

    def _world(self):
        for key, val in (('min_x', -58594), ('max_x', 58593),
                         ('min_z', -58594), ('max_z', 58593)):
            self.values[key].set(str(val))
        messagebox.showinfo(self.t('all_regions'),
                            f'{MAX_REGIONS:,} regions maximum per search. Split large areas into sections.')

    def _default(self):
        for key, val in (('min_x', -16), ('max_x', 16), ('min_z', -16), ('max_z', 16)):
            self.values[key].set(str(val))

    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            bounds = RegionBounds(*(int(self.values[x].get()) for x in ('min_x', 'max_x', 'min_z', 'max_z')))
            seeds = ([signed_seed(self.values['seed'].get())] if self.tab.get() == 'single'
                     else load_seeds(Path(self.values['file'].get())))
            search = Explorer(self.values['version'].get(), mode=self.mode.get(), bounds=bounds,
                              radius=int(self.values['radius'].get()), max_y=int(self.values['max_y'].get()),
                              top_per_seed=int(self.values['top'].get()),
                              threads=int(self.values['threads'].get()))
        except (ValueError, OSError, argparse.ArgumentTypeError) as exc:
            messagebox.showerror(self.t('error'), str(exc))
            return
        self.cancel.clear()
        self.pause.set()
        self.rows = []
        self.started = time.monotonic()
        self.bar['value'] = 0
        self.caption.set(self.t('ready'))
        self.worker = threading.Thread(target=self._work, args=(search, seeds), daemon=True)
        self.worker.start()
        self._toggle()

    def _work(self, search: Explorer, seeds: list[int]):
        try:
            def progress(done, total, count, eta):
                self.events.put(('progress', done, total, count, eta))
            def region_progress(done, total):
                self.events.put(('region_progress', done, total))
            rows = search.run(seeds, pause=self.pause, cancel=self.cancel,
                               progress=progress, region_progress=region_progress)
            self.events.put(('done', rows, self.cancel.is_set()))
        except Exception as exc:
            self.events.put(('error', str(exc)))

    def _pause(self):
        self.pause.clear()
        self._toggle()

    def _resume(self):
        self.pause.set()
        self._toggle()

    def _stop(self):
        self.cancel.set()
        self.pause.set()
        self._toggle()

    def _poll(self):
        try:
            while True:
                item = self.events.get_nowait()
                if item[0] == 'progress':
                    _, done, total, count, eta = item
                    self.bar['value'] = 100 * done / total
                    self.caption.set(self.t('progress', done=done, total=total, rows=count,
                                            eta=str(timedelta(seconds=int(eta)))))
                elif item[0] == 'region_progress':
                    _, done, total = item
                    self.bar['value'] = 100 * done / total
                    self.caption.set(self.t('region_progress', done=done, total=total))
                elif item[0] == 'done':
                    _, self.rows, canceled = item
                    self._fill()
                    self.caption.set(self.t('stopped') if canceled else self.t('done', rows=len(self.rows)))
                    self._toggle()
                elif item[0] == 'error':
                    self.caption.set(str(item[1]))
                    messagebox.showerror(self.t('error'), str(item[1]))
                    self._toggle()
        except queue.Empty:
            pass
        if self.winfo_exists():
            self._poll_id = self.after(120, self._poll)

    def _fill(self):
        self.table.delete(*self.table.get_children())
        for row in self.rows[:1000]:
            self.table.insert('', 'end', values=[row.get(k, '') for k in FIELDS])

    def _sort(self, key):
        if not self.rows:
            return
        try:
            self.rows = Explorer.sort_rows(self.rows, key)
            self._fill()
        except ValueError as exc:
            messagebox.showerror(self.t('error'), str(exc))

    def _save_file(self, default, extension):
        if not self.rows:
            return None
        return filedialog.asksaveasfilename(defaultextension=extension, initialfile=default,
                                             filetypes=[('CSV', '*.csv')] if extension == '.csv' else [('Text', '*.txt')])

    def _save(self):
        path = self._save_file('outpost-results.csv', '.csv')
        if path:
            try:
                write_csv(Path(path), self.rows, FIELDS)
            except OSError as exc:
                messagebox.showerror(self.t('error'), str(exc))

    def _export_seeds(self):
        path = self._save_file('outpost-seeds.txt', '.txt')
        if path:
            try:
                export_seed_list(Path(path), self.rows)
            except OSError as exc:
                messagebox.showerror(self.t('error'), str(exc))

    def _export_tp(self):
        path = self._save_file('outpost-coordinates.txt', '.txt')
        if path:
            try:
                export_teleports(Path(path), self.rows)
            except OSError as exc:
                messagebox.showerror(self.t('error'), str(exc))

    def destroy(self):
        if getattr(self, '_poll_id', None) is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        super().destroy()

    def _close(self):
        self.cancel.set()
        self.pause.set()
        if self.worker and self.worker.is_alive():
            self.after(150, self._close)
        else:
            self.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    root.withdraw()
    AdvancedWindow(root)
    root.mainloop()
