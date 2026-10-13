"""File: gui.py
Modification: 2026-10-12 — responsive Tkinter desktop UI for Java 1.21–26.3 outpost finder.

Built on Python's standard library. No game client modification is performed.
"""
from __future__ import annotations

import csv
from datetime import datetime
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from gui_model import SearchRequest, build_arguments
from explorer_gui import AdvancedWindow
from i18n import CATALOGS, tr
from versions import VERSIONS

ROOT = Path(__file__).resolve().parent
PROJECT_VERSION = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
MODES = [(key, 'mode_' + key) for key in
         ('candidates', 'estimate', 'world', 'verify', 'search-live', 'seed-vanilla')]



class App(tk.Tk):
    def __init__(self, language: str = 'zh-TW'):
        super().__init__()
        self.language = tk.StringVar(value=language)
        self.title(self.t('window_title'))
        self.geometry('1070x720')
        self.minsize(810, 570)
        self.events: queue.Queue = queue.Queue()
        self.process: subprocess.Popen | None = None
        self.worker: threading.Thread | None = None
        self.cancel_requested = threading.Event()
        self.mode_choices = tuple(MODES)
        self.mode_widgets = {}
        self.field_widgets = {}
        self.browse_widgets = {}
        self.last_output: Path | None = None
        self.vars = {}
        self.groups = {}
        self.mode = tk.StringVar(value='candidates')
        self.banner = tk.StringVar(value=self.t('banner_ready'))
        self._theme()
        self._build()
        self._set_mode()
        self._apply_language()
        self._poll_id = self.after(100, self._poll)
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def t(self, key: str, **values) -> str:
        return tr(self.language.get(), key, **values)

    def _theme(self):
        style = ttk.Style(self)
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        self.configure(bg='#f4f7f7')
        style.configure('TFrame', background='#f4f7f7')
        style.configure('TLabel', background='#f4f7f7', foreground='#223a3c')
        style.configure('Header.TLabel', font=('Arial', 19, 'bold'))
        style.configure('Subtitle.TLabel', font=('Arial', 10), foreground='#587076')
        style.configure('Title.TLabel', font=('Arial', 10, 'bold'))
        style.configure('TButton', padding=(11, 6))
        style.configure('Start.TButton', background='#236e69', foreground='white', font=('Arial', 10, 'bold'))
        style.map('Start.TButton', background=[('active', '#18534e'), ('disabled', '#a1adab')])
        style.configure('Treeview', rowheight=25, background='white', fieldbackground='white')
        style.configure('Treeview.Heading', font=('Arial', 9, 'bold'))
        style.configure('Horizontal.TProgressbar', background='#3f948b')

    def _build(self):
        root = ttk.Frame(self, padding=16)
        root.pack(fill='both', expand=True)
        ttk.Label(root, text='LowYOutpostFinder', style='Header.TLabel').pack(anchor='w')
        self.subtitle = ttk.Label(root, style='Subtitle.TLabel')
        self.subtitle.pack(anchor='w', pady=(2, 12))
        top = ttk.Frame(root)
        top.pack(fill='x')
        self.mode_label = ttk.Label(top, style='Title.TLabel')
        self.mode_label.pack(side='left', padx=(0, 12))
        mode_rows = (ttk.Frame(top), ttk.Frame(top))
        for mode_row in mode_rows:
            mode_row.pack(fill='x')
        for index, (key, _label) in enumerate(MODES):
            widget = ttk.Radiobutton(mode_rows[index // 3], value=key,
                                     variable=self.mode, command=self._set_mode)
            widget.pack(side='left', padx=3)
            self.mode_widgets[key] = widget
        locale = ttk.Frame(root)
        locale.pack(fill='x', pady=(9, 0))
        self.language_label = ttk.Label(locale, style='Subtitle.TLabel')
        self.language_label.pack(side='left', padx=(0, 10))
        self.language_combo = ttk.Combobox(locale, textvariable=self.language, state='readonly',
                                           values=('zh-TW', 'en-US'), width=12)
        self.language_combo.pack(side='left')
        self.language_combo.bind('<<ComboboxSelected>>', self._apply_language)
        ttk.Separator(root).pack(fill='x', pady=10)
        form_container = ttk.Frame(root)
        form_container.pack(fill='x')
        self.form_canvas = tk.Canvas(form_container, height=228, highlightthickness=0,
                                     bg='#f4f7f7', borderwidth=0)
        form_scroll = ttk.Scrollbar(form_container, orient='vertical',
                                     command=self.form_canvas.yview)
        self.form_canvas.configure(yscrollcommand=form_scroll.set)
        self.form_canvas.pack(side='left', fill='x', expand=True)
        form_scroll.pack(side='right', fill='y')
        self.form = ttk.Frame(self.form_canvas)
        self.form_item = self.form_canvas.create_window((0, 0), window=self.form, anchor='nw')
        self.form.bind('<Configure>', self._resize_form_scroll)
        self.form_canvas.bind('<Configure>', self._resize_form_window)
        defaults = {
            'seed': '123', 'version': '1.21.8', 'radius': '8192',
            'world': '', 'candidates': '', 'max_y': '', 'limit': '50',
            'timeout': '180', 'port': '25575', 'password': '', 'out': '',
            'top': '25', 'core_archive': '', 'game_jar': '', 'server_jar': '',
            'java': 'java', 'memory': '2048', 'startup_timeout': '300',
            'priority': 'near-origin'
        }
        for name, value in defaults.items():
            self.vars[name] = tk.StringVar(value=value)
        self.vars['eula_accepted'] = tk.BooleanVar(value=False)
        fields = ('version', 'seed', 'radius', 'world', 'candidates', 'max_y',
                  'top', 'core_archive', 'game_jar', 'server_jar', 'java', 'memory', 'startup_timeout',
                  'eula_accepted', 'priority', 'limit', 'timeout', 'port', 'password', 'out')
        for row_index, field in enumerate(fields):
            line = ttk.Frame(self.form)
            line.pack(fill='x', pady=3)
            self.groups[field] = line
            label = ttk.Label(line, width=31)
            label.pack(side='left')
            self.field_widgets[field] = label
            if field == 'eula_accepted':
                widget = ttk.Checkbutton(line, variable=self.vars[field])
                widget.pack(side='left', anchor='w')
            elif field == 'priority':
                widget = ttk.Combobox(line, textvariable=self.vars[field], state='readonly',
                                      values=('near-origin', 'terrain'), width=21)
                widget.pack(side='left', fill='x', expand=True, padx=(0, 6))
            elif field == 'version':
                widget = ttk.Combobox(line, textvariable=self.vars[field], state='readonly',
                                      values=[v.id for v in VERSIONS], width=21)
                widget.pack(side='left', fill='x', expand=True, padx=(0, 6))
                self.version_combo = widget
            else:
                widget = ttk.Entry(line, textvariable=self.vars[field],
                                   show='*' if field == 'password' else '', width=47)
                widget.pack(side='left', fill='x', expand=True, padx=(0, 6))
                if field == 'world':
                    self.browse_widgets[field] = ttk.Button(line, command=self._browse_world)
                    self.browse_widgets[field].pack(side='left')
                elif field == 'candidates':
                    self.browse_widgets[field] = ttk.Button(line, command=self._browse_candidates)
                    self.browse_widgets[field].pack(side='left')
                elif field == 'out':
                    self.browse_widgets[field] = ttk.Button(line, command=self._browse_output)
                    self.browse_widgets[field].pack(side='left')
                elif field == 'core_archive':
                    self.browse_widgets[field] = ttk.Button(line, command=self._browse_core_archive)
                    self.browse_widgets[field].pack(side='left')
                elif field == 'game_jar':
                    self.browse_widgets[field] = ttk.Button(line, command=self._browse_game_jar)
                    self.browse_widgets[field].pack(side='left')
                elif field == 'server_jar':
                    self.browse_widgets[field] = ttk.Button(line, command=self._browse_server_jar)
                    self.browse_widgets[field].pack(side='left')
        self.tips = ttk.Label(root, text='', wraplength=1000, justify='left', style='Subtitle.TLabel')
        self.tips.pack(fill='x', pady=(10, 7))
        actions = ttk.Frame(root)
        actions.pack(fill='x', pady=2)
        self.start_btn = ttk.Button(actions, style='Start.TButton', command=self._start)
        self.start_btn.pack(side='left')
        self.advanced_btn = ttk.Button(actions, command=self._advanced)
        self.advanced_btn.pack(side='left', padx=7)
        self.stop_btn = ttk.Button(actions, command=self._stop, state='disabled')
        self.stop_btn.pack(side='left', padx=9)
        self.folder_btn = ttk.Button(actions, command=self._open_folder)
        self.folder_btn.pack(side='left')
        self.copy_btn = ttk.Button(actions, command=self._save_copy)
        self.copy_btn.pack(side='left', padx=6)
        self.progress = ttk.Progressbar(actions, mode='indeterminate', length=125)
        self.progress.pack(side='right')
        ttk.Label(root, textvariable=self.banner, style='Subtitle.TLabel', wraplength=1000).pack(
            fill='x', pady=(7, 5))
        results = ttk.Panedwindow(root, orient='vertical')
        results.pack(fill='both', expand=True)
        preview = ttk.Frame(results)
        results.add(preview, weight=4)
        self.preview_label = ttk.Label(preview, style='Title.TLabel')
        self.preview_label.pack(anchor='w')
        grid_frame = ttk.Frame(preview)
        grid_frame.pack(fill='both', expand=True, pady=(4, 0))
        self.grid = ttk.Treeview(grid_frame, show='headings', height=7)
        self.grid.pack(side='left', fill='both', expand=True)
        y = ttk.Scrollbar(grid_frame, orient='vertical', command=self.grid.yview)
        y.pack(side='right', fill='y')
        x = ttk.Scrollbar(preview, orient='horizontal', command=self.grid.xview)
        x.pack(fill='x')
        self.grid.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        logs = ttk.Frame(results)
        results.add(logs, weight=1)
        self.logs_label = ttk.Label(logs, style='Title.TLabel')
        self.logs_label.pack(anchor='w')
        self.log_text = tk.Text(logs, font=('Menlo', 9), height=5, wrap='word',
                                state='disabled', bg='#fff', fg='#263d3c')
        self.log_text.pack(fill='both', expand=True)

    def _resize_form_scroll(self, _event=None):
        self.form_canvas.configure(scrollregion=self.form_canvas.bbox('all'))

    def _resize_form_window(self, event):
        self.form_canvas.itemconfigure(self.form_item, width=event.width)
        self._resize_form_scroll()

    def _set_mode(self, *, reset_output: bool = True):
        mode = self.mode.get()
        visibility = {
            'candidates': {'version', 'seed', 'radius', 'out'},
            'estimate': {'version', 'seed', 'radius', 'max_y', 'top', 'core_archive', 'game_jar', 'out'},
            'world': {'version', 'world', 'max_y', 'out'},
            'verify': {'version', 'world', 'candidates', 'out'},
            'search-live': {'version', 'world', 'radius', 'max_y', 'limit',
                            'timeout', 'port', 'password', 'out'},
            'seed-vanilla': {'version', 'seed', 'radius', 'server_jar', 'java', 'memory',
                             'startup_timeout', 'eula_accepted', 'priority', 'core_archive', 'game_jar',
                             'limit', 'timeout', 'max_y', 'out'},
        }
        for key, widget in self.groups.items():
            widget.pack_forget()
            if key in visibility[mode]:
                widget.pack(fill='x', pady=3)
        if mode == 'estimate':
            self.version_combo.configure(values=['1.21.8'])
            self.vars['version'].set('1.21.8')
            if not self.vars['max_y'].get().strip():
                self.vars['max_y'].set('64')
        elif mode in ('candidates', 'seed-vanilla'):
            self.version_combo.configure(values=[v.id for v in VERSIONS])
            if self.vars['version'].get() == 'auto':
                self.vars['version'].set('1.21.8')
        else:
            self.version_combo.configure(values=['auto'] + [v.id for v in VERSIONS])
            if reset_output:
                self.vars['version'].set('auto')
        if reset_output:
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            self.vars['out'].set(str(ROOT / 'results' / f'{mode}-{stamp}.csv'))
        self.tips.configure(text=self.t('tip_' + mode))
        self.form_canvas.yview_moveto(0.0)
        self._resize_form_scroll()

    def _apply_language(self, _event=None):
        self.title(f"{self.t('window_title')} {PROJECT_VERSION}")
        self.subtitle.configure(text=self.t('subtitle'))
        self.mode_label.configure(text=self.t('mode_caption'))
        self.language_label.configure(text=self.t('language_caption'))
        for mode, _key in MODES:
            self.mode_widgets[mode].configure(text=self.t('mode_' + mode))
        for field, widget in self.field_widgets.items():
            widget.configure(text=self.t('field_' + field))
        for field, widget in self.browse_widgets.items():
            widget.configure(text=self.t('browse_' + ('output' if field == 'out' else field)))
        for key, widget in (
            ('start', self.start_btn), ('advanced', self.advanced_btn), ('stop', self.stop_btn),
            ('open_folder', self.folder_btn), ('save_copy', self.copy_btn),
            ('preview_label', self.preview_label), ('logs_label', self.logs_label)):
            widget.configure(text=self.t(key))
        self._set_mode(reset_output=False)
        for child in self.winfo_children():
            if isinstance(child, AdvancedWindow):
                child.change_language(self.language.get())
        # Preserve active worker state and user-entered fields on language switch.
        if self.worker is None or not self.worker.is_alive():
            self.banner.set(self.t('banner_ready'))
        columns = self.grid['columns']
        for field in columns:
            self.grid.heading(field, text=self.t('column_' + field)
                              if 'column_' + field in CATALOGS[self.language.get()] else field)

    def _advanced(self):
        window = AdvancedWindow(self, language=self.language.get())
        window.focus_set()

    def _browse_world(self):
        path = filedialog.askdirectory(title=self.t('dialog_world'))
        if path:
            self.vars['world'].set(path)

    def _browse_candidates(self):
        path = filedialog.askopenfilename(title=self.t('dialog_candidates'), filetypes=[('CSV', '*.csv')])
        if path:
            self.vars['candidates'].set(path)

    def _browse_core_archive(self):
        path = filedialog.askopenfilename(title=self.t('dialog_core_archive'),
                filetypes=[('Compressed tar archive', '*.tar.gz'), ('All files', '*')])
        if path:
            self.vars['core_archive'].set(path)

    def _browse_game_jar(self):
        path = filedialog.askopenfilename(title=self.t('dialog_game_jar'),
                                         filetypes=[('Java archive', '*.jar'), ('All files', '*')])
        if path:
            self.vars['game_jar'].set(path)

    def _browse_server_jar(self):
        path = filedialog.askopenfilename(title=self.t('dialog_server_jar'),
                                         filetypes=[('Java archive', '*.jar'), ('All files', '*')])
        if path:
            self.vars['server_jar'].set(path)

    def _browse_output(self):
        path = filedialog.asksaveasfilename(title=self.t('dialog_output'), defaultextension='.csv',
                                            filetypes=[('CSV', '*.csv')])
        if path:
            self.vars['out'].set(path)

    def _log(self, message: str):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', message.rstrip() + '\n')
        if int(self.log_text.index('end-1c').split('.')[0]) > 250:
            self.log_text.delete('1.0', '60.0')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _start(self):
        if self.worker and self.worker.is_alive():
            return
        request = SearchRequest(mode=self.mode.get(), **{
            key: value.get() for key, value in self.vars.items()})
        try:
            argv, secrets = build_arguments(request, language=self.language.get())
        except ValueError as exc:
            messagebox.showerror(self.t('error_title'), str(exc))
            return
        if request.mode in ('search-live', 'seed-vanilla'):
            confirm = 'vanilla_confirm' if request.mode == 'seed-vanilla' else 'live_confirm'
            if not messagebox.askyesno(self.t('live_title'), self.t(confirm)):
                return
        self.last_output = None
        self.cancel_requested.clear()
        self.start_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.progress.start(12)
        self.banner.set(self.t('banner_running'))
        # Intentionally avoid printing argv or including RCON credentials in logs.
        self._log(self.t('start_log', mode=self.t('mode_' + request.mode), version=request.version))
        self.worker = threading.Thread(target=self._worker, args=(argv, secrets, request.out), daemon=True)
        self.worker.start()

    def _worker(self, args: list[str], secrets: dict, out: str):
        try:
            if self.cancel_requested.is_set():
                self.events.put(('done', 130, out))
                return
            env = {**os.environ, **secrets}
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            process = subprocess.Popen([sys.executable, str(ROOT / 'finder.py'), *args],
                         cwd=ROOT, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                         errors='replace', bufsize=1, creationflags=flags)
            self.process = process
            if self.cancel_requested.is_set() and process.poll() is None:
                process.terminate()
            assert process.stdout is not None
            for line in process.stdout:
                self.events.put(('log', line))
            code = process.wait()
            self.events.put(('done', code, out))
        except (OSError, ValueError) as exc:
            self.events.put(('error', str(exc)))
        finally:
            self.process = None

    def _stop(self):
        self.cancel_requested.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self._log(self.t('stop_log'))
            self.banner.set(self.t('banner_stopping'))
        else:
            self._log(self.t('not_running_log'))

    def destroy(self):
        timer = getattr(self, '_poll_id', None)
        if timer is not None:
            try:
                self.after_cancel(timer)
            except tk.TclError:
                pass
            self._poll_id = None
        super().destroy()

    def _on_close(self):
        """Never orphan a running world-modifying subprocess on window close."""
        if self.worker is not None and self.worker.is_alive():
            if not messagebox.askyesno(self.t('close_title'), self.t('close_confirm')):
                return
            self._stop()
            self.banner.set(self.t('banner_closing'))
            self.after(200, self._close_when_done)
        else:
            self.destroy()

    def _close_when_done(self):
        if self.worker is not None and self.worker.is_alive():
            self.after(200, self._close_when_done)
        else:
            self.destroy()

    def _poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == 'log':
                    self._log(event[1])
                elif event[0] == 'error':
                    self._complete()
                    self.banner.set(self.t('launch_failed', error=event[1]))
                    messagebox.showerror(self.t('execution_failed'), event[1])
                elif event[0] == 'done':
                    _, code, path = event
                    self._complete()
                    if code == 0:
                        self.last_output = Path(path).expanduser()
                        try:
                            count, shown = self._preview(self.last_output)
                            self.banner.set(self.t('done', count=count, shown=shown, path=self.last_output))
                        except (OSError, UnicodeError, csv.Error) as exc:
                            self.banner.set(self.t('preview_failed', error=exc))
                    else:
                        self.banner.set(self.t('failed'))
                        self._log(self.t('exit_code', code=code))
        except queue.Empty:
            pass
        if self.winfo_exists():
            self._poll_id = self.after(120, self._poll)

    def _complete(self):
        self.progress.stop()
        self.start_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')

    def _preview(self, path: Path) -> tuple[int, int]:
        for child in self.grid.get_children():
            self.grid.delete(child)
        with path.open('r', encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            self.grid.configure(columns=fields)
            for col in fields:
                self.grid.heading(col, text=self.t('column_' + col) if 'column_' + col in CATALOGS[self.language.get()] else col)
                self.grid.column(col, width=155 if col in ('status', 'classification', 'reason') else 112,
                                 stretch=False, anchor='center')
            count = 0
            for row in reader:
                if count < 500:
                    self.grid.insert('', 'end', values=[row.get(col, '') for col in fields])
                count += 1
        return count, min(count, 500)

    def _open_folder(self):
        path = (self.last_output or Path(self.vars['out'].get())).expanduser().parent
        if not path.exists():
            messagebox.showinfo(self.t('folder_missing_title'), self.t('folder_missing'))
            return
        if sys.platform == 'darwin':
            subprocess.Popen(['open', str(path)])
        elif os.name == 'nt':
            os.startfile(str(path))
        else:
            subprocess.Popen(['xdg-open', str(path)])

    def _save_copy(self):
        if not self.last_output or not self.last_output.is_file():
            messagebox.showinfo(self.t('no_results_title'), self.t('no_results'))
            return
        destination = filedialog.asksaveasfilename(defaultextension='.csv',
                         filetypes=[('CSV', '*.csv')], title=self.t('save_dialog'))
        if destination:
            if self.last_output.resolve() != Path(destination).resolve():
                shutil.copyfile(self.last_output, destination)
            self.banner.set(self.t('copy_saved', path=destination))


def main(argv=None) -> None:
    import argparse
    parser = argparse.ArgumentParser(description='LowYOutpostFinder desktop GUI')
    parser.add_argument('--lang', choices=tuple(CATALOGS), default='zh-TW',
                        help='UI language / 介面語言')
    args = parser.parse_args(argv)
    App(language=args.lang).mainloop()


if __name__ == '__main__':
    main()
