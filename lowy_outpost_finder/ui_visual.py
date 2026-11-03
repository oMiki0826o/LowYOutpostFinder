"""Tkinter presentation helpers: dual palette, contextual hints, hover tooltips.

No search or evidence classification logic belongs here.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


PALETTES = {
    'dark': {
        'bg': '#000000', 'surface': '#0b0b0b', 'raised': '#191919',
        'fg': '#ffffff', 'muted': '#b0b0b0', 'border': '#444444',
        'accent': '#ffffff', 'selected': '#333333', 'verified': '#eeeeee',
        'estimated': '#aaaaaa', 'candidate': '#c0c0c0', 'error': '#ffffff',
    },
    'light': {
        'bg': '#ffffff', 'surface': '#ffffff', 'raised': '#ededed',
        'fg': '#111111', 'muted': '#555555', 'border': '#aaaaaa',
        'accent': '#111111', 'selected': '#dddddd', 'verified': '#111111',
        'estimated': '#555555', 'candidate': '#777777', 'error': '#222222',
    },
}


def apply_theme(root: tk.Misc, mode: str) -> dict[str, str]:
    palette = PALETTES[mode]
    style = ttk.Style(root)
    if 'clam' in style.theme_names():
        style.theme_use('clam')
    bg, surface, fg, muted = (palette[k] for k in ('bg', 'surface', 'fg', 'muted'))
    style.configure('TFrame', background=bg)
    style.configure('TLabel', background=bg, foreground=fg)
    style.configure('Header.TLabel', background=bg, foreground=fg,
                    font=('Arial', 19, 'bold'))
    style.configure('Subtitle.TLabel', background=bg, foreground=muted,
                    font=('Arial', 10))
    style.configure('Title.TLabel', background=bg, foreground=fg,
                    font=('Arial', 10, 'bold'))
    style.configure('Hint.TLabel', background=bg, foreground=palette['accent'],
                    font=('Arial', 10))
    for name in ('TRadiobutton', 'TCheckbutton'):
        style.configure(name, background=bg, foreground=fg)
        style.map(name, background=[('active', bg)],
                  foreground=[('disabled', muted), ('active', fg)])
    style.configure('TButton', padding=(6, 4), background=palette['raised'],
                    foreground=fg, bordercolor=palette['border'])
    style.map('TButton', background=[('active', palette['selected'])],
              foreground=[('disabled', muted)])
    style.configure('Start.TButton', padding=(7, 5),
                    background=palette['accent'], foreground='#ffffff',
                    font=('Arial', 10, 'bold'))
    style.map('Start.TButton', background=[('active', palette['selected'])])
    style.configure('TEntry', fieldbackground=surface, foreground=fg,
                    bordercolor=palette['border'])
    style.configure('TCombobox', fieldbackground=surface, foreground=fg,
                    background=palette['raised'], arrowcolor=fg)
    style.map('TCombobox', fieldbackground=[('readonly', surface)],
              foreground=[('readonly', fg)])
    style.configure('TNotebook', background=bg, bordercolor=palette['border'])
    style.configure('TNotebook.Tab', padding=(10, 5),
                    background=palette['raised'], foreground=fg)
    style.map('TNotebook.Tab',
              background=[('selected', surface)], foreground=[('selected', fg)])
    style.configure('Treeview', background=surface, fieldbackground=surface,
                    foreground=fg, rowheight=25, bordercolor=palette['border'])
    style.map('Treeview', background=[('selected', palette['selected'])],
              foreground=[('selected', fg)])
    style.configure('Treeview.Heading', background=palette['raised'],
                    foreground=fg, font=('Arial', 9, 'bold'))
    style.configure('Horizontal.TProgressbar', background=palette['accent'])
    style.configure('TSeparator', background=palette['border'])
    root.configure(bg=bg)
    return palette


def height_note(language: str, mode: str, engine: str, strategy: str,
                max_y: str, center_y: str) -> str:
    zh = language == 'zh-TW'
    if mode == 'full-map':
        if engine == 'placement':
            return ('僅計算結構 X/Z 候選；不代表實際生成，也沒有 Y。' if zh
                    else 'Placement X/Z only. No verified structure or Y.')
        if strategy == 'nearest':
            try:
                # C model uses projected centre = projected base plate + 14.
                base_ceiling = __import__('math').ceil(float(max_y) - 14) - 1
                suffix = (f'；目前模型推算基板 Y ≤ {base_ceiling}' if zh
                          else f'; current model: base plate Y ≤ {base_ceiling}')
            except (ValueError, OverflowError):
                suffix = ''
            return (f'近似結構中心 Y < {max_y}{suffix}。非原版驗證。' if zh else
                    f'Estimated centre Y < {max_y}{suffix}. Not vanilla-verified.')
        return (f'近似基板 Y ≤ {max_y}；不是中心 Y，也不是原版驗證。' if zh else
                f'Estimated base plate Y ≤ {max_y}; NOT centre Y or vanilla verified.')
    if mode in ('seed-vanilla', 'search-live'):
        return (f'實際生成後才核驗結構中心 Y < {center_y}；未驗證候選不視為命中。' if zh else
                f'Only saved-world evidence verifies centre Y < {center_y}.')
    if mode == 'candidates':
        return ('純種子計算的 X/Z 候選，沒有生態域或 Y 證據。' if zh else
                'Seed-derived X/Z placement candidates; no biome or Y evidence.')
    return ''


FIELD_HINTS = {
    'seed': ('Minecraft Java 64 位元有號世界種子。', 'Signed 64-bit Minecraft Java seed.'),
    'radius': ('以所選 X/Z 中心的方形半徑（方塊）。', 'Square radius around chosen X/Z centre, in blocks.'),
    'center_x': ('搜尋參考中心；預設 0，不一定是世界出生點。',
                 'Search reference centre; zero is not necessarily the world spawn.'),
    'center_z': ('搜尋參考中心；預設 0，不一定是世界出生點。',
                 'Search reference centre; zero is not necessarily the world spawn.'),
    'nearest_only': ('只取最近 N 個 X/Z 候選，避免全世界完整列舉。',
                     'Return nearest N placement candidates without exhaustive enumeration.'),
    'top': ('輸出數量；依搜尋模式可能是距離或高度篩選結果。',
            'Result count, with sorting and filters depending on search mode.'),
    'scan_strategy': ('nearest 優先距離；exhaustive 逐格並支援續跑。',
                      'Nearest expands from centre; exhaustive scans cells with checkpoints.'),
    'height_engine': ('placement 僅 X/Z；estimate 是 1.21.8 的非精確 C 高度推算。',
                      'Placement is X/Z only; estimate is experimental 1.21.8 C height.'),
    'scan_engine': ('原生 C 加速需要先建置；auto 只在支援時回退 Python。',
                    'Native scanner requires compiling; auto falls back only for supported modes.'),
    'max_y': ('nearest 近似中心嚴格小於；exhaustive 近似基板小於等於。',
              'Nearest filters estimated centre strictly; exhaustive filters base plate inclusively.'),
    'resume': ('使用相同設定及輸出位置恢復未完成的逐格／近似高度搜尋。',
               'Resume compatible incomplete exhaustive or estimated-height checkpoints.'),
    'threads': ('僅供 C 近似高度 nearest；0 表示自動。',
                'Only for C estimated nearest; zero selects automatically.'),
}


def hover_text(language: str, category: str, key: str) -> str:
    if category == 'fields':
        entry = FIELD_HINTS.get(key)
        if entry:
            return entry[0 if language == 'zh-TW' else 1]
    if category == 'modes':
        return (f'{key}：請查看下方模式說明；候選與近似值均不代表已驗證 Y。'
                if language == 'zh-TW' else
                f'{key}: see mode guidance; candidates and estimates are not verified Y.')
    return ''


class HoverTips:
    """Hover tooltips with delayed display, designed for Tk and macOS."""

    def __init__(self, root: tk.Misc, palette_supplier):
        self.root = root
        self.palette_supplier = palette_supplier
        self.timer = None
        self.window = None

    def attach(self, widget: tk.Misc, supplier):
        widget.bind('<Enter>', lambda _event: self._schedule(widget, supplier), add='+')
        widget.bind('<Leave>', lambda _event: self.hide(), add='+')
        widget.bind('<ButtonPress>', lambda _event: self.hide(), add='+')

    def _schedule(self, widget, supplier):
        self.hide()
        self.timer = self.root.after(650, lambda: self._show(widget, supplier()))

    def _show(self, widget, message):
        self.timer = None
        if not message or not widget.winfo_exists():
            return
        palette = self.palette_supplier()
        self.window = tk.Toplevel(self.root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        label = tk.Label(self.window, text=message, justify='left',
                         wraplength=370, padx=10, pady=8,
                         bg=palette['raised'], fg=palette['fg'],
                         highlightbackground=palette['border'],
                         highlightthickness=1)
        label.pack()
        x, y = widget.winfo_pointerxy()
        self.window.geometry(f'+{x + 12}+{y + 16}')
        self.window.deiconify()

    def hide(self):
        if self.timer is not None:
            try:
                self.root.after_cancel(self.timer)
            except tk.TclError:
                pass
            self.timer = None
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None
