"""File: gui.py
Modification: 2026-10-12 — responsive Tkinter desktop UI for Java 1.21–26.3 outpost finder.

Built on Python's standard library. No game client modification is performed.
"""
from __future__ import annotations

import csv
from pathlib import Path
from datetime import datetime
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .gui_model import SearchRequest, build_arguments
from .ui_visual import PALETTES, HoverTips, apply_theme, height_note, hover_text
from .explorer_gui import AdvancedWindow
from .i18n import CATALOGS, tr
from .paths import PROJECT_ROOT, cli_command
from .versions import VERSIONS

PROJECT_VERSION = (PROJECT_ROOT / 'VERSION').read_text(encoding='utf-8').strip()
MODES = [(key, 'mode_' + key) for key in
         ('candidates', 'full-map', 'seed-geometry', 'estimate', 'world', 'verify', 'search-live', 'seed-vanilla')]



class App(tk.Tk):
    def __init__(self, language: str = 'zh-TW', initial_mode: str = 'candidates'):
        super().__init__()
        self.language = tk.StringVar(value=language)
        if initial_mode not in dict(MODES):
            raise ValueError('Unsupported advanced mode')
        self._closing = False
        self._layout_after = None
        self.theme_mode = tk.StringVar(value='dark')
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
        self.mode = tk.StringVar(value=initial_mode)
        self.banner = tk.StringVar(value=self.t('banner_ready'))
        self._theme()
        self._build()
        self._hover = HoverTips(self, lambda: PALETTES[self.theme_mode.get()])
        self._install_hover()
        self._install_form_scrolling()
        self._apply_theme()
        self._set_mode()
        self._apply_language()
        self._poll_id = self.after(100, self._poll)
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.bind('<F1>', lambda _event: self._show_help())
        self.bind('<Control-Return>', lambda _event: self._start())

    def t(self, key: str, **values) -> str:
        return tr(self.language.get(), key, **values)

    def _theme(self):
        apply_theme(self, self.theme_mode.get())

    def _apply_theme(self):
        palette = apply_theme(self, self.theme_mode.get())
        self.form_canvas.configure(bg=palette['bg'])
        self.log_text.configure(bg=palette['surface'], fg=palette['fg'],
                                insertbackground=palette['fg'],
                                selectbackground=palette['selected'])
        for tag in ('verified_tower', 'estimated_only', 'placement_candidate', 'error'):
            key = {'verified_tower': 'verified', 'estimated_only': 'estimated',
                   'placement_candidate': 'candidate', 'error': 'error'}[tag]
            self.grid.tag_configure(tag, foreground=palette[key])

    def _change_theme(self, _event=None):
        self.theme_mode.set('light' if self.theme_display.get() == self.t('theme_light') else 'dark')
        self._apply_theme()

    def _install_hover(self):
        for mode, widget in self.mode_widgets.items():
            self._hover.attach(widget, lambda m=mode:
                               hover_text(self.language.get(), 'modes', m))
        for field, group in self.groups.items():
            description = lambda f=field: hover_text(self.language.get(), 'fields', f)
            for widget in group.winfo_children():
                self._hover.attach(widget, description)
                for child in widget.winfo_children():
                    self._hover.attach(child, description)
        self._hover.attach(self.theme_combo, lambda:
                           '切換深色或淺色外觀' if self.language.get() == 'zh-TW'
                           else 'Switch dark/light appearance')

    def _install_form_scrolling(self):
        def bind(widget):
            widget.bind('<MouseWheel>', self._scroll_form, add='+')
            widget.bind('<Button-4>', self._scroll_form, add='+')
            widget.bind('<Button-5>', self._scroll_form, add='+')
            for child in widget.winfo_children():
                bind(child)
        bind(self.form_canvas)
        self.bind('<Configure>', self._resize_form_viewport, add='+')
        self._schedule_form_resize()

    def _scroll_form(self, event):
        if self.form_canvas.yview() == (0.0, 1.0):
            return None
        if getattr(event, 'num', None) == 4:
            amount = -3
        elif getattr(event, 'num', None) == 5:
            amount = 3
        else:
            delta = getattr(event, 'delta', 0)
            if delta == 0:
                return None
            amount = (-3 if delta > 0 else 3)
        self.form_canvas.yview_scroll(amount, 'units')
        return 'break'

    def _schedule_form_resize(self):
        if self._closing or self._layout_after is not None:
            return
        self._layout_after = self.after_idle(self._run_form_resize)

    def _run_form_resize(self):
        self._layout_after = None
        self._resize_form_viewport()

    def _resize_form_viewport(self, event=None):
        """Avoid touching a destroyed Tk widget after macOS Configure/after_idle."""
        if self._closing:
            return
        if event is not None and getattr(event, 'widget', self) is not self:
            return
        if not getattr(self, 'form_visible', False):
            return
        try:
            if not self.form.winfo_exists() or not self.form_canvas.winfo_exists():
                return
            size = max(170, min(420, self.winfo_height() - 430,
                                self.form.winfo_reqheight() + 12))
            if int(self.form_canvas.cget('height')) != size:
                self.form_canvas.configure(height=size)
            self._resize_form_scroll()
        except tk.TclError:
            return

    def _update_height_note(self):
        if not hasattr(self, 'height_note'):
            return
        self.height_note.configure(text=height_note(
            self.language.get(), self.mode.get(), self.vars['height_engine'].get(),
            self.vars['scan_strategy'].get(), self.vars['max_y'].get(),
            self.vars['center_y_below'].get()))

    def _build(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill='both', expand=True)
        ttk.Label(root, text='LowYOutpostFinder', style='Header.TLabel').pack(anchor='w')
        self.subtitle = ttk.Label(root, style='Subtitle.TLabel')
        self.subtitle.pack(anchor='w', pady=(2, 4))
        top = ttk.Frame(root)
        top.pack(fill='x')
        self.mode_label = ttk.Label(top, style='Title.TLabel')
        self.mode_label.pack(side='left', padx=(0, 12))
        mode_panel = ttk.Frame(top)
        mode_panel.pack(side='left', fill='x')
        mode_panel.columnconfigure(0, minsize=205)
        mode_panel.columnconfigure(1, minsize=250)
        for index, (key, _label) in enumerate(MODES):
            widget = ttk.Radiobutton(mode_panel, value=key,
                                     variable=self.mode, command=self._set_mode)
            widget.grid(row=index // 2, column=index % 2, sticky='w', padx=(0, 8), pady=1)
            self.mode_widgets[key] = widget
        locale = ttk.Frame(root)
        locale.pack(fill='x', pady=(9, 0))
        self.language_label = ttk.Label(locale, style='Subtitle.TLabel')
        self.language_label.pack(side='left', padx=(0, 10))
        self.language_combo = ttk.Combobox(locale, textvariable=self.language, state='readonly',
                                           values=('zh-TW', 'en-US'), width=12)
        self.language_combo.pack(side='left')
        self.language_combo.bind('<<ComboboxSelected>>', self._apply_language)
        self.theme_label = ttk.Label(locale, style='Subtitle.TLabel')
        self.theme_label.pack(side='left', padx=(18, 7))
        self.theme_display = tk.StringVar(value=self.t('theme_dark'))
        self.theme_combo = ttk.Combobox(locale, textvariable=self.theme_display,
                                        state='readonly', width=9,
                                        values=(self.t('theme_dark'), self.t('theme_light')))
        self.theme_combo.pack(side='left')
        self.theme_combo.bind('<<ComboboxSelected>>', self._change_theme)
        self.form_visible = True
        self.toggle_form_btn = ttk.Button(locale, command=self._toggle_form)
        self.toggle_form_btn.pack(side='right')
        ttk.Separator(root).pack(fill='x', pady=5)
        form_container = ttk.Frame(root)
        form_container.pack(fill='x')
        self.form_container = form_container
        self.form_canvas = tk.Canvas(form_container, height=305, highlightthickness=0,
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
            'center_x': '0', 'center_z': '0',
            'world': '', 'candidates': '', 'max_y': '', 'limit': '50', 'offset': '0',
            'timeout': '180', 'port': '25575', 'password': '', 'out': '',
            'top': '25', 'center_y_below': '-37', 'core_archive': '', 'game_jar': '', 'server_jar': '',
            'java': 'java', 'memory': '2048', 'startup_timeout': '300',
            'priority': 'near-origin', 'sort_by': 'distance',
            'scan_strategy': 'nearest', 'scan_engine': 'auto', 'height_engine': 'placement',
            'batch_regions': '500000', 'cpu_rest_ms': '150', 'threads': '0'
        }
        for name, value in defaults.items():
            self.vars[name] = tk.StringVar(value=value)
        self.vars['eula_accepted'] = tk.BooleanVar(value=False)
        self.vars['resume'] = tk.BooleanVar(value=False)
        self.vars['nearest_only'] = tk.BooleanVar(value=True)
        self.vars['max_y'].trace_add('write', lambda *_: self._update_height_note())
        self.vars['center_y_below'].trace_add('write', lambda *_: self._update_height_note())
        fields = ('version', 'seed', 'radius', 'center_x', 'center_z', 'world', 'candidates', 'max_y',
                  'top', 'nearest_only', 'center_y_below', 'core_archive', 'game_jar', 'server_jar', 'java', 'memory', 'startup_timeout',
                  'eula_accepted', 'priority', 'sort_by', 'scan_strategy', 'scan_engine', 'height_engine', 'batch_regions', 'cpu_rest_ms', 'threads', 'resume',
                  'limit', 'offset', 'timeout', 'port', 'password', 'out')
        for row_index, field in enumerate(fields):
            line = ttk.Frame(self.form)
            line.pack(fill='x', pady=3)
            self.groups[field] = line
            label = ttk.Label(line, width=31)
            label.pack(side='left')
            self.field_widgets[field] = label
            if field in ('eula_accepted', 'resume', 'nearest_only'):
                widget = ttk.Checkbutton(line, variable=self.vars[field],
                                         command=(lambda: self._set_mode(reset_output=False))
                                         if field == 'nearest_only' else None)
                widget.pack(side='left', anchor='w')
            elif field == 'sort_by':
                widget = ttk.Combobox(line, textvariable=self.vars[field], state='readonly',
                                      values=('distance', 'base-y', 'tower-y'), width=21)
                widget.pack(side='left', fill='x', expand=True, padx=(0, 6))
            elif field == 'scan_strategy':
                widget = ttk.Combobox(line, textvariable=self.vars[field], state='readonly',
                                      values=('nearest', 'exhaustive'), width=21)
                widget.pack(side='left', fill='x', expand=True, padx=(0, 6))
                widget.bind('<<ComboboxSelected>>', lambda _e: self._set_mode(reset_output=False))
            elif field == 'scan_engine':
                widget = ttk.Combobox(line, textvariable=self.vars[field], state='readonly',
                                      values=('auto', 'python', 'native'), width=21)
                widget.pack(side='left', fill='x', expand=True, padx=(0, 6))
            elif field == 'height_engine':
                widget = ttk.Combobox(line, textvariable=self.vars[field], state='readonly',
                                      values=('placement', 'estimate'), width=21)
                widget.pack(side='left', fill='x', expand=True, padx=(0, 6))
                widget.bind('<<ComboboxSelected>>', lambda _e: self._set_mode(reset_output=False))
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
        self.height_note = ttk.Label(root, text='', wraplength=1000, justify='left', style='Hint.TLabel')
        self.height_note.pack(fill='x', pady=(4, 1))
        self.tips = ttk.Label(root, text='', wraplength=1000, justify='left', style='Subtitle.TLabel')
        self.tips.pack(fill='x', pady=(10, 7))
        # Two toolbar rows remain usable on 810px laptops and with Windows fonts.
        actions = ttk.Frame(root)
        actions.pack(fill='x', pady=(2, 0))
        self.start_btn = ttk.Button(actions, style='Start.TButton', command=self._start)
        self.start_btn.pack(side='left')
        self.stop_btn = ttk.Button(actions, command=self._stop, state='disabled')
        self.stop_btn.pack(side='left', padx=7)
        self.advanced_btn = ttk.Button(actions, command=self._advanced)
        self.advanced_btn.pack(side='left', padx=5)
        secondary = ttk.Frame(root)
        secondary.pack(fill='x', pady=(2, 0))
        self.folder_btn = ttk.Button(secondary, command=self._open_folder)
        self.folder_btn.pack(side='left')
        self.copy_btn = ttk.Button(secondary, command=self._save_copy)
        self.copy_btn.pack(side='left', padx=7)
        self.help_btn = ttk.Button(secondary, command=self._show_help)
        self.help_btn.pack(side='left', padx=6)
        self.progress = ttk.Progressbar(secondary, mode='indeterminate', length=125)
        self.progress.pack(side='right')
        ttk.Label(root, textvariable=self.banner, style='Subtitle.TLabel', wraplength=1000).pack(
            fill='x', pady=(7, 5))
        results = ttk.Notebook(root)
        results.pack(fill='both', expand=True, pady=(3, 0))
        self.results_tabs = results
        preview = ttk.Frame(results)
        results.add(preview, text='Results')
        self.preview_label = ttk.Label(preview, style='Title.TLabel')
        self.preview_label.pack(anchor='w')
        self.preview_count = tk.StringVar(value='')
        ttk.Label(preview, textvariable=self.preview_count, style='Subtitle.TLabel').pack(anchor='w')
        grid_frame = ttk.Frame(preview)
        grid_frame.pack(fill='both', expand=True, pady=(4, 0))
        self.grid = ttk.Treeview(grid_frame, show='headings', height=7)
        self.grid.tag_configure('verified_tower', foreground='#165e50')
        self.grid.tag_configure('estimated_only', foreground='#805000')
        self.grid.tag_configure('placement_candidate', foreground='#516470')
        self.grid.tag_configure('error', foreground='#a12828')
        self.grid.pack(side='left', fill='both', expand=True)
        y = ttk.Scrollbar(grid_frame, orient='vertical', command=self.grid.yview)
        y.pack(side='right', fill='y')
        x = ttk.Scrollbar(preview, orient='horizontal', command=self.grid.xview)
        x.pack(fill='x')
        self.grid.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        logs = ttk.Frame(results)
        results.add(logs, text='Logs')
        self.logs_label = ttk.Label(logs, style='Title.TLabel')
        self.logs_label.pack(anchor='w')
        self.log_text = tk.Text(logs, font=('Menlo', 9), height=5, wrap='word',
                                state='disabled', bg='#fff', fg='#263d3c')
        self.log_text.pack(fill='both', expand=True)

    def _resize_form_scroll(self, _event=None):
        if self._closing:
            return
        try:
            if self.form_canvas.winfo_exists():
                self.form_canvas.configure(scrollregion=self.form_canvas.bbox('all'))
        except tk.TclError:
            pass

    def _resize_form_window(self, event):
        if self._closing:
            return
        try:
            if self.form_canvas.winfo_exists():
                self.form_canvas.itemconfigure(self.form_item, width=event.width)
                self._resize_form_scroll()
        except tk.TclError:
            pass

    def _set_mode(self, *, reset_output: bool = True):
        mode = self.mode.get()
        visibility = {
            'candidates': {'version', 'seed', 'radius', 'center_x', 'center_z', 'nearest_only', 'top', 'out'},
            'full-map': {'version', 'seed', 'center_x', 'center_z', 'top', 'height_engine', 'max_y', 'scan_strategy', 'scan_engine',
                         'batch_regions', 'cpu_rest_ms', 'threads', 'resume', 'out'},
            'seed-geometry': {'version', 'seed', 'radius', 'center_x', 'center_z', 'game_jar', 'out'},
            'estimate': {'version', 'seed', 'radius', 'max_y', 'top', 'center_y_below', 'core_archive', 'game_jar', 'out'},
            'world': {'version', 'world', 'max_y', 'out'},
            'verify': {'version', 'world', 'candidates', 'out'},
            'search-live': {'version', 'world', 'radius', 'center_x', 'center_z', 'max_y', 'limit', 'offset',
                            'timeout', 'port', 'password', 'center_y_below', 'sort_by', 'out'},
            'seed-vanilla': {'version', 'seed', 'radius', 'center_x', 'center_z', 'server_jar', 'java', 'memory',
                             'startup_timeout', 'eula_accepted', 'priority', 'core_archive', 'game_jar',
                             'limit', 'offset', 'timeout', 'max_y', 'center_y_below', 'sort_by', 'out'},
        }
        if mode == 'candidates' and not self.vars['nearest_only'].get():
            visibility[mode].discard('top')
        if mode == 'full-map' and self.vars['height_engine'].get() != 'estimate':
            visibility[mode].discard('max_y')
        if mode == 'full-map' and self.vars['height_engine'].get() == 'estimate':
            if not self.vars['max_y'].get().strip():
                self.vars['max_y'].set('-37')
        for key, widget in self.groups.items():
            widget.pack_forget()
            if key in visibility[mode]:
                widget.pack(fill='x', pady=3)
        if mode == 'estimate':
            self.version_combo.configure(values=['1.21.8'])
            self.vars['version'].set('1.21.8')
            if not self.vars['max_y'].get().strip():
                self.vars['max_y'].set('64')
        elif mode == 'full-map' and self.vars['height_engine'].get() == 'estimate':
            self.version_combo.configure(values=['1.21.8'])
            self.vars['version'].set('1.21.8')
        elif mode in ('candidates', 'seed-vanilla', 'seed-geometry', 'full-map'):
            self.version_combo.configure(values=[v.id for v in VERSIONS])
            if self.vars['version'].get() == 'auto':
                self.vars['version'].set('1.21.8')
        else:
            self.version_combo.configure(values=['auto'] + [v.id for v in VERSIONS])
            if reset_output:
                self.vars['version'].set('auto')
        if reset_output:
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            self.vars['out'].set(str(PROJECT_ROOT / 'results' / f'{mode}-{stamp}.csv'))
        self.tips.configure(text=self.t('tip_' + mode))
        if mode == 'full-map' and self.vars['height_engine'].get() == 'estimate':
            top_key = 'field_top_estimate_nearest' if self.vars['scan_strategy'].get() == 'nearest' else 'field_top_estimate_exhaustive'
            y_key = 'field_max_y_center' if self.vars['scan_strategy'].get() == 'nearest' else 'field_max_y_base'
        else:
            top_key = ('field_top_nearest' if mode == 'full-map' else
                       'field_top_candidates' if mode == 'candidates' else 'field_top')
            y_key = 'field_max_y'
        self.field_widgets['top'].configure(text=self.t(top_key))
        self.field_widgets['max_y'].configure(text=self.t(y_key))
        self._update_height_note()
        if self.height_note.cget('text'):
            self.height_note.pack(fill='x', before=self.tips, pady=(4, 1))
        else:
            self.height_note.pack_forget()
        self.form_canvas.yview_moveto(0.0)
        self._schedule_form_resize()
        self._resize_form_scroll()

    def _apply_language(self, _event=None):
        self.title(f"{self.t('window_title')} {PROJECT_VERSION}")
        self.subtitle.configure(text=self.t('subtitle'))
        self.mode_label.configure(text=self.t('mode_caption'))
        self.language_label.configure(text=self.t('language_caption'))
        self.toggle_form_btn.configure(text=self.t('collapse_form' if self.form_visible else 'expand_form'))
        for mode, _key in MODES:
            self.mode_widgets[mode].configure(text=self.t('mode_' + mode))
        for field, widget in self.field_widgets.items():
            widget.configure(text=self.t('field_' + field))
        for field, widget in self.browse_widgets.items():
            widget.configure(text=self.t('browse_' + ('output' if field == 'out' else field)))
        for key, widget in (
            ('start', self.start_btn), ('advanced', self.advanced_btn), ('stop', self.stop_btn),
            ('open_folder', self.folder_btn), ('save_copy', self.copy_btn),
            ('help', self.help_btn),
            ('preview_label', self.preview_label), ('logs_label', self.logs_label)):
            widget.configure(text=self.t(key))
        self.results_tabs.tab(0, text=self.t('tab_results'))
        self.results_tabs.tab(1, text=self.t('tab_logs'))
        self.theme_label.configure(text=self.t('theme'))
        self.theme_combo.configure(values=(self.t('theme_dark'), self.t('theme_light')))
        self.theme_display.set(self.t('theme_light' if self.theme_mode.get() == 'light' else 'theme_dark'))
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

    def _toggle_form(self, visible: bool | None = None):
        """Let results use the small-screen viewport without losing form values."""
        show = (not self.form_visible) if visible is None else bool(visible)
        if show != self.form_visible:
            if show:
                self.form_container.pack(fill='x', before=self.tips)
            else:
                self.form_container.pack_forget()
            self.form_visible = show
        self.toggle_form_btn.configure(text=self.t('collapse_form' if show else 'expand_form'))

    def _show_help(self):
        """Open a read-only, bilingual quick-start guide without leaving the app."""
        window = tk.Toplevel(self)
        window.title(self.t('help_title'))
        window.geometry('650x480')
        window.minsize(420, 330)
        frame = ttk.Frame(window, padding=15)
        frame.pack(fill='both', expand=True)
        palette = PALETTES[self.theme_mode.get()]
        text_box = tk.Text(frame, wrap='word', font=('Arial', 11), padx=12, pady=12,
                           bg=palette['surface'], fg=palette['fg'], insertbackground=palette['fg'])
        text_box.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=text_box.yview)
        scrollbar.pack(side='right', fill='y')
        text_box.configure(yscrollcommand=scrollbar.set)
        text_box.insert('1.0', self.t('help_text'))
        text_box.configure(state='disabled')
        window.transient(self)

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
                filetypes=[('Source archive ZIP', '*.zip'), ('Compressed tar archive', '*.tar.gz'), ('All files', '*')])
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
        self.results_tabs.select(1)  # Streaming log is visible during a long-running job.
        self.start_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.progress.configure(mode='indeterminate', value=0)
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
            process = subprocess.Popen(cli_command(*args),
                         cwd=PROJECT_ROOT, env=env, stdout=subprocess.PIPE,
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
        self._closing = True
        if self._layout_after is not None:
            try:
                self.after_cancel(self._layout_after)
            except tk.TclError:
                pass
            self._layout_after = None
        if hasattr(self, '_hover'):
            self._hover.hide()
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

    def _update_progress_from_log(self, line: str) -> None:
        """Display measured candidate progress, never an invented worldgen percentage."""
        full = re.match(r'^FULLMAP_PROGRESS (\d+) (\d+) (\d+) (complete|incomplete)', line.strip())
        if full:
            current, total, matched = map(int, full.group(1, 2, 3))
            if 0 <= current <= total and total > 0:
                self.progress.stop()
                self.progress.configure(mode='determinate', maximum=total, value=current)
                self.banner.set(self.t('banner_fullmap_progress', checked=f'{current:,}',
                                       total=f'{total:,}', matched=f'{matched:,}'))
            return
        estimated = re.match(r'^FULLMAP_ESTIMATE_PROGRESS (\d+) (\d+|ring) (\d+) ([a-z_]+)', line.strip())
        if estimated:
            checked, total, matched, status = estimated.groups()
            if total != 'ring' and int(total) > 0:
                self.progress.stop()
                self.progress.configure(mode='determinate', maximum=int(total), value=int(checked))
                self.banner.set(self.t('banner_estimated_progress', checked=checked, total=total, matched=matched))
            else:
                self.banner.set(self.t('banner_estimated_rings', rings=checked, matched=matched))
            return
        match = re.match(r'^\[(\d+)/(\d+)\]', line.strip())
        if match is None:
            return
        current, total = int(match[1]), int(match[2])
        if total < 1 or not (0 <= current <= total):
            return
        self.progress.stop()
        self.progress.configure(mode='determinate', maximum=total, value=current)
        self.banner.set(self.t('banner_progress', checked=current, total=total))

    def _poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == 'log':
                    self._log(event[1])
                    self._update_progress_from_log(event[1])
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
                            self._toggle_form(visible=False)
                            self.results_tabs.select(0)
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
        self.preview_count.set('')
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
                    status = str(row.get('status') or row.get('classification') or '')
                    tag = (status if status in ('verified_tower', 'estimated_only',
                                                'placement_candidate') else
                           'error' if status in ('invalid_nbt', 'timeout', 'version_mismatch',
                                                  'invalid_region') else '')
                    self.grid.insert('', 'end', values=[row.get(col, '') for col in fields],
                                     tags=(tag,) if tag else ())
                count += 1
        self.preview_count.set(self.t('preview_count', count=count, shown=min(count, 500)))
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
    parser.add_argument('--mode', choices=tuple(key for key, _ in MODES),
                        default='candidates', help='Initial advanced search mode')
    args = parser.parse_args(argv)
    App(language=args.lang, initial_mode=args.mode).mainloop()


if __name__ == '__main__':
    main()
