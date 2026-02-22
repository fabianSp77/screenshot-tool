"""
screenshot_tool.py  –  Snagit-ähnliches Screenshot-Tool (Alles in einer Datei)
===============================================================================
Start:  python screenshot_tool.py
        oder Doppelklick auf start.pyw (kein Terminal-Fenster, Windows)

Abhängigkeiten (einmalig installieren):
    Windows:  pip install --user Pillow mss pyautogui pywin32 keyboard numpy
    macOS:    pip install --user Pillow mss pyautogui pyobjc-framework-Quartz pynput numpy

Hotkeys (auch im Hintergrund aktiv):
    Windows:
        Print Screen       → Region auswählen
        Ctrl+Shift+F       → Vollbild
        Ctrl+Shift+W       → Fenster auswählen
        Ctrl+Shift+S       → Scrolling Capture
    macOS:
        Cmd+Shift+1        → Region auswählen
        Cmd+Shift+F        → Vollbild
        Cmd+Shift+W        → Fenster auswählen
        Cmd+Shift+S        → Scrolling Capture
"""

import sys
import io
import json
import math
import os
import subprocess
import tempfile
import time
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, colorchooser, messagebox
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageTk, ImageOps

# ── Plattform-Erkennung ─────────────────────────────────────────────────────
IS_WINDOWS = sys.platform == 'win32'
IS_MACOS   = sys.platform == 'darwin'

FONT_FAMILY = 'Segoe UI' if IS_WINDOWS else 'Helvetica Neue'


def _get_truetype_font(size: int):
    """Plattformspezifische TrueType-Schrift für PIL."""
    paths = []
    if IS_WINDOWS:
        paths = ['segoeui.ttf', 'arial.ttf']
    elif IS_MACOS:
        paths = [
            '/System/Library/Fonts/Helvetica.ttc',
            '/System/Library/Fonts/HelveticaNeue.ttc',
            '/Library/Fonts/Arial.ttf',
        ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ── CMD-Fenster verstecken & DPI (nur Windows) ─────────────────────────────
if IS_WINDOWS:
    import ctypes
    try:
        ctypes.windll.user32.ShowWindow(
            ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Abhängigkeiten prüfen
# ---------------------------------------------------------------------------

if IS_WINDOWS:
    REQUIRED = {
        'PIL':       'Pillow',
        'mss':       'mss',
        'pyautogui': 'pyautogui',
        'win32gui':  'pywin32',
        'keyboard':  'keyboard',
        'numpy':     'numpy',
    }
elif IS_MACOS:
    REQUIRED = {
        'PIL':       'Pillow',
        'mss':       'mss',
        'pyautogui': 'pyautogui',
        'Quartz':    'pyobjc-framework-Quartz',
        'pynput':    'pynput',
        'numpy':     'numpy',
    }
else:
    REQUIRED = {
        'PIL':       'Pillow',
        'mss':       'mss',
        'pyautogui': 'pyautogui',
        'numpy':     'numpy',
    }


def check_dependencies() -> bool:
    missing = []
    for module, package in REQUIRED.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    if missing:
        root = tk.Tk()
        root.withdraw()
        cmd = 'pip install --user ' + ' '.join(missing)
        messagebox.showerror(
            'Fehlende Abhängigkeiten',
            f'Bitte führe folgenden Befehl aus und starte das Tool neu:\n\n'
            f'    {cmd}\n\n'
            f'Fehlend: {", ".join(missing)}',
        )
        root.destroy()
        return False
    return True


# ===========================================================================
# VERLAUF  –  HistoryManager
# ===========================================================================

MAX_ENTRIES = 25
THUMB_W     = 120
THUMB_H     = 80


class HistoryManager:
    """
    Verwaltet den Screenshot-Verlauf (max. 25 Einträge).

    Speicherstruktur neben der screenshot_tool.py:
        history/
            index.json
            img_*.png
            thumb_*.png
    """

    def __init__(self, history_dir: str | None = None):
        if history_dir is None:
            base = os.path.dirname(os.path.abspath(__file__))
            history_dir = os.path.join(base, 'history')

        self.history_dir = history_dir
        self.index_path  = os.path.join(history_dir, 'index.json')
        self.entries: list[dict] = []

        os.makedirs(history_dir, exist_ok=True)
        self._load_index()

    # ------------------------------------------------------------------
    def add(self, image: Image.Image) -> dict:
        now = datetime.now()
        entry_id = now.strftime('%Y%m%d_%H%M%S_%f')

        img_filename = f'img_{entry_id}.png'
        image.save(os.path.join(self.history_dir, img_filename))

        thumb = image.copy()
        thumb.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
        thumb_filename = f'thumb_{entry_id}.png'
        thumb.save(os.path.join(self.history_dir, thumb_filename))

        entry = {
            'id':                entry_id,
            'filename':          img_filename,
            'thumb_filename':    thumb_filename,
            'timestamp':         now.isoformat(),
            'timestamp_display': now.strftime('%d.%m.%Y %H:%M:%S'),
        }
        self.entries.insert(0, entry)

        while len(self.entries) > MAX_ENTRIES:
            self._remove_entry(self.entries[-1])
            self.entries.pop()

        self._save_index()
        return entry

    def update(self, entry_id: str, image: Image.Image):
        entry = self._find(entry_id)
        if not entry:
            return
        image.save(os.path.join(self.history_dir, entry['filename']))
        thumb = image.copy()
        thumb.thumbnail((THUMB_W, THUMB_H), Image.LANCZOS)
        thumb.save(os.path.join(self.history_dir, entry['thumb_filename']))

    def remove(self, entry_id: str):
        entry = self._find(entry_id)
        if entry:
            self._remove_entry(entry)
            self.entries = [e for e in self.entries if e['id'] != entry_id]
            self._save_index()

    def load_image(self, entry_id: str) -> Image.Image | None:
        entry = self._find(entry_id)
        if not entry:
            return None
        path = os.path.join(self.history_dir, entry['filename'])
        return Image.open(path).copy() if os.path.exists(path) else None

    def load_thumbnail(self, entry_id: str) -> Image.Image | None:
        entry = self._find(entry_id)
        if not entry:
            return None
        path = os.path.join(self.history_dir, entry['thumb_filename'])
        return Image.open(path).copy() if os.path.exists(path) else None

    def get_entries(self) -> list[dict]:
        return list(self.entries)

    # ------------------------------------------------------------------
    def _find(self, entry_id: str) -> dict | None:
        for e in self.entries:
            if e['id'] == entry_id:
                return e
        return None

    def _remove_entry(self, entry: dict):
        for key in ('filename', 'thumb_filename'):
            path = os.path.join(self.history_dir, entry.get(key, ''))
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _load_index(self):
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.entries = [
                    e for e in data.get('entries', [])
                    if os.path.exists(
                        os.path.join(self.history_dir, e.get('filename', '')))
                ]
            except Exception:
                self.entries = []
        else:
            self.entries = []

    def _save_index(self):
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump({'entries': self.entries}, f,
                          ensure_ascii=False, indent=2)
        except Exception:
            pass


# ===========================================================================
# CAPTURE  –  RegionOverlay, WindowPickerDialog, CaptureEngine
# ===========================================================================

class RegionOverlay:
    """
    Transparentes Vollbild-Overlay.
    Benutzer zieht einen Bereich → Ausschnitt wird zurückgegeben.
    """

    def __init__(self, root, callback):
        self.root     = root
        self.callback = callback
        self._start_x = self._start_y = 0
        self._cur_x   = self._cur_y   = 0
        self.background: Image.Image | None = None

    def show(self):
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[0]
            raw = sct.grab(mon)
            self.background = Image.frombytes(
                'RGB', raw.size, raw.bgra, 'raw', 'BGRX')

        self.win = tk.Toplevel(self.root)
        self.win.attributes('-fullscreen', True)
        self.win.attributes('-topmost', True)
        self.win.configure(cursor='crosshair')

        self.canvas = tk.Canvas(self.win, highlightthickness=0,
                                cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)

        # Abgedunkelter Hintergrund
        self._bg_dark = self.background.copy()
        r, g, b = self._bg_dark.split()
        factor = 0.5
        r = r.point(lambda p: int(p * factor))
        g = g.point(lambda p: int(p * factor))
        b = b.point(lambda p: int(p * factor))
        self._bg_dark = Image.merge('RGB', (r, g, b))
        self._bg_photo = ImageTk.PhotoImage(self._bg_dark)
        self.canvas.create_image(0, 0, anchor='nw',
                                 image=self._bg_photo, tag='bg')

        self.canvas.create_text(
            self.win.winfo_screenwidth() // 2, 30,
            text='Bereich auswählen  |  ESC = Abbrechen',
            fill='white', font=(FONT_FAMILY, 14), tag='hint')

        self.canvas.bind('<ButtonPress-1>',   self._on_down)
        self.canvas.bind('<B1-Motion>',        self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_up)
        self.win.bind('<Escape>', lambda e: self._cancel())

    def _on_down(self, event):
        self._start_x = event.x
        self._start_y = event.y

    def _on_drag(self, event):
        self._cur_x = event.x
        self._cur_y = event.y
        self._draw_selection()

    def _on_up(self, event):
        self._cur_x = event.x
        self._cur_y = event.y
        x1, y1, x2, y2 = self._normalized_rect()
        if abs(x2 - x1) < 5 or abs(y2 - y1) < 5:
            return
        self.win.destroy()
        self.callback(self.background.crop((x1, y1, x2, y2)))

    def _cancel(self):
        self.win.destroy()

    def _normalized_rect(self):
        return (min(self._start_x, self._cur_x),
                min(self._start_y, self._cur_y),
                max(self._start_x, self._cur_x),
                max(self._start_y, self._cur_y))

    def _draw_selection(self):
        self.canvas.delete('selection')
        x1, y1, x2, y2 = self._normalized_rect()
        w, h = abs(x2 - x1), abs(y2 - y1)
        if w == 0 or h == 0:
            return

        region_img   = self.background.crop((x1, y1, x2, y2))
        self._region_photo = ImageTk.PhotoImage(region_img)
        self.canvas.create_image(x1, y1, anchor='nw',
                                 image=self._region_photo, tag='selection')
        self.canvas.create_rectangle(x1, y1, x2, y2,
                                     outline='#00D4FF', width=2,
                                     tag='selection')
        lbl = f'{w} × {h} px'
        tx  = x1 + 4
        ty  = y1 - 18 if y1 > 20 else y2 + 4
        self.canvas.create_rectangle(
            tx - 2, ty - 2, tx + len(lbl) * 7 + 2, ty + 16,
            fill='#003344', outline='', tag='selection')
        self.canvas.create_text(
            tx, ty, text=lbl, fill='#00D4FF',
            font=(FONT_FAMILY, 10, 'bold'), anchor='nw', tag='selection')


# ---------------------------------------------------------------------------

class WindowPickerDialog:
    """Zeigt alle sichtbaren Fenster zur Auswahl."""

    def __init__(self, parent):
        self.result = None
        self.parent = parent

    def show(self):
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title('Fenster auswählen')
        self.dialog.geometry('500x400')
        self.dialog.grab_set()
        self.dialog.attributes('-topmost', True)

        tk.Label(self.dialog,
                 text='Wähle das Fenster aus, das aufgenommen werden soll:',
                 font=(FONT_FAMILY, 10)).pack(padx=10, pady=8, anchor='w')

        frame = tk.Frame(self.dialog)
        frame.pack(fill='both', expand=True, padx=10, pady=4)

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side='right', fill='y')

        self.listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set,
                                  font=(FONT_FAMILY, 10), selectmode='single')
        self.listbox.pack(fill='both', expand=True)
        scrollbar.config(command=self.listbox.yview)

        self.windows = self._get_windows()
        for wid, title in self.windows:
            self.listbox.insert('end', title)

        btn_frame = tk.Frame(self.dialog)
        btn_frame.pack(fill='x', padx=10, pady=8)
        tk.Button(btn_frame, text='Aufnehmen', command=self._on_ok,
                  bg='#0078D4', fg='white',
                  font=(FONT_FAMILY, 10)).pack(side='right', padx=4)
        tk.Button(btn_frame, text='Abbrechen', command=self._on_cancel,
                  font=(FONT_FAMILY, 10)).pack(side='right', padx=4)

        self.parent.wait_window(self.dialog)
        return self.result

    def _on_ok(self):
        sel = self.listbox.curselection()
        if sel:
            self.result = self.windows[sel[0]]
        self.dialog.destroy()

    def _on_cancel(self):
        self.dialog.destroy()

    @staticmethod
    def _get_windows():
        if IS_WINDOWS:
            try:
                import win32gui
                def callback(hwnd, result):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if title.strip():
                            result.append((hwnd, title))
                wins = []
                win32gui.EnumWindows(callback, wins)
                return wins
            except ImportError:
                return []
        elif IS_MACOS:
            try:
                import Quartz
                options = Quartz.kCGWindowListOptionOnScreenOnly
                window_list = Quartz.CGWindowListCopyWindowInfo(
                    options, Quartz.kCGNullWindowID)
                wins = []
                for win in window_list:
                    name = win.get(Quartz.kCGWindowOwnerName, '')
                    title = win.get(Quartz.kCGWindowName, '')
                    wid = win.get(Quartz.kCGWindowNumber, 0)
                    display = f'{name} – {title}' if title else name
                    if display.strip() and win.get(Quartz.kCGWindowLayer, 99) == 0:
                        wins.append((wid, display))
                return wins
            except ImportError:
                return []
        return []


# ---------------------------------------------------------------------------

class CaptureEngine:
    """Kapselt alle vier Capture-Modi."""

    def capture_fullscreen(self) -> Image.Image:
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[0]
            raw = sct.grab(mon)
            return Image.frombytes('RGB', raw.size, raw.bgra, 'raw', 'BGRX')

    def capture_window(self, wid: int) -> Image.Image:
        if IS_WINDOWS:
            return self._capture_window_win(wid)
        elif IS_MACOS:
            return self._capture_window_mac(wid)
        raise RuntimeError('Fenster-Capture wird auf dieser Plattform nicht unterstützt')

    def _capture_window_win(self, hwnd: int) -> Image.Image:
        import win32gui, win32ui
        from ctypes import windll

        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        w = right - left
        h = bottom - top
        if w <= 0 or h <= 0:
            raise ValueError('Fenster hat ungültige Größe')

        hwnd_dc = save_dc = mfc_dc = save_bmp = None
        try:
            hwnd_dc  = win32gui.GetWindowDC(hwnd)
            mfc_dc   = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc  = mfc_dc.CreateCompatibleDC()
            save_bmp = win32ui.CreateBitmap()
            save_bmp.CreateCompatibleBitmap(mfc_dc, w, h)
            save_dc.SelectObject(save_bmp)
            windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)

            bmpinfo = save_bmp.GetInfo()
            bmpstr  = save_bmp.GetBitmapBits(True)
            return Image.frombuffer(
                'RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1)
        except Exception:
            # Fallback: mss Region-Capture
            import mss
            with mss.mss() as sct:
                mon = {'left': left, 'top': top,
                       'width': w, 'height': h}
                raw = sct.grab(mon)
                return Image.frombytes('RGB', raw.size,
                                       raw.bgra, 'raw', 'BGRX')
        finally:
            if save_bmp:
                try: win32gui.DeleteObject(save_bmp.GetHandle())
                except Exception: pass
            if save_dc:
                try: save_dc.DeleteDC()
                except Exception: pass
            if mfc_dc:
                try: mfc_dc.DeleteDC()
                except Exception: pass
            if hwnd_dc:
                try: win32gui.ReleaseDC(hwnd, hwnd_dc)
                except Exception: pass

    def _capture_window_mac(self, wid: int) -> Image.Image:
        import Quartz
        cg_image = Quartz.CGWindowListCreateImage(
            Quartz.CGRectNull,
            Quartz.kCGWindowListOptionIncludingWindow,
            wid,
            Quartz.kCGWindowImageBoundsIgnoreFraming)
        if cg_image is None:
            raise RuntimeError('Fenster konnte nicht aufgenommen werden')

        w = Quartz.CGImageGetWidth(cg_image)
        h = Quartz.CGImageGetHeight(cg_image)
        bpr = Quartz.CGImageGetBytesPerRow(cg_image)
        provider = Quartz.CGImageGetDataProvider(cg_image)
        data = Quartz.CGDataProviderCopyData(provider)
        img = Image.frombuffer('RGBA', (w, h), data, 'raw', 'BGRA', bpr, 1)
        return img.convert('RGB')

    def capture_scrolling(self, region: tuple,
                          scroll_pause: float = 0.5,
                          max_scrolls: int = 30) -> Image.Image:
        import mss, pyautogui

        x1, y1, x2, y2 = region
        mon = {'left': x1, 'top': y1, 'width': x2 - x1, 'height': y2 - y1}
        cx  = x1 + (x2 - x1) // 2
        cy  = y1 + (y2 - y1) // 2

        strips: list[Image.Image] = []
        prev_strip: Image.Image | None = None
        scroll_offsets: list[int] = []

        for _ in range(max_scrolls + 1):
            time.sleep(0.1)
            with mss.mss() as sct:
                raw   = sct.grab(mon)
                strip = Image.frombytes('RGB', raw.size, raw.bgra, 'raw', 'BGRX')

            if prev_strip is not None:
                offset = self._find_overlap(prev_strip, strip)
                if offset is None or offset == 0:
                    break
                scroll_offsets.append(offset)
            strips.append(strip)
            prev_strip = strip

            pyautogui.click(cx, cy)
            pyautogui.press('pagedown')
            time.sleep(scroll_pause)

        if not strips:
            import mss
            with mss.mss() as sct:
                raw = sct.grab(mon)
                return Image.frombytes('RGB', raw.size,
                                       raw.bgra, 'raw', 'BGRX')
        return self._stitch(strips, scroll_offsets)

    def _find_overlap(self, prev: Image.Image,
                      curr: Image.Image) -> int | None:
        try:
            import numpy as np
        except ImportError:
            return prev.height // 2

        pa = np.array(prev.convert('L'), dtype=np.int32)
        ca = np.array(curr.convert('L'), dtype=np.int32)
        h  = pa.shape[0]
        search = min(300, h // 2)

        best_offset = None
        best_score  = float('inf')
        for candidate in range(5, search):
            diff = float(np.mean(np.abs(
                pa[h - candidate:h] - ca[0:candidate])))
            if diff < best_score:
                best_score  = diff
                best_offset = candidate

        if best_score > 20:
            return None
        return h - best_offset

    def _stitch(self, strips: list[Image.Image],
                offsets: list[int]) -> Image.Image:
        w = strips[0].width
        visible_heights = offsets + [strips[-1].height]
        total_h = sum(
            vis if i < len(strips) - 1 else strip.height
            for i, (strip, vis) in enumerate(zip(strips, visible_heights)))

        canvas = Image.new('RGB', (w, total_h), 'white')
        y = 0
        for i, (strip, vis) in enumerate(zip(strips, visible_heights)):
            if i < len(strips) - 1:
                canvas.paste(strip.crop((0, 0, w, vis)), (0, y))
                y += vis
            else:
                canvas.paste(strip, (0, y))
        return canvas


# ===========================================================================
# EDITOR  –  Annotation (Datenmodell) + AnnotationEditor
# ===========================================================================

# ── Gemeinsame UI-Farben ──────────────────────────────────────────────────
class _Theme:
    BG_MAIN      = '#F8FAFC'
    BG_TOOLBAR   = '#FFFFFF'
    BG_CANVAS    = '#CBD5E1'
    FG_MAIN      = '#0F172A'
    FG_MUTED     = '#64748B'
    ACCENT       = '#2563EB'
    ACCENT_HOV   = '#1D4ED8'
    ACCENT_LIGHT = '#EFF6FF'
    BTN_SEL      = '#2563EB'
    BTN_NORM     = '#F1F5F9'
    BTN_HOV      = '#E2E8F0'
    BTN_FG       = '#334155'
    DIVIDER      = '#E2E8F0'
    DANGER       = '#DC2626'
    DANGER_HOV   = '#B91C1C'
    SUCCESS      = '#16A34A'
    EXPORT_BG    = '#1E293B'
    EXPORT_BTN   = '#334155'
    EXPORT_HOV   = '#475569'


@dataclass
class Annotation:
    kind:        str
    x1:          int  = 0
    y1:          int  = 0
    x2:          int  = 0
    y2:          int  = 0
    color:       str  = '#FF0000'
    width:       int  = 3
    text:        str  = ''
    font_size:   int  = 16
    tail_x:      int  = 0
    tail_y:      int  = 0
    points:      list = field(default_factory=list)
    blur_radius: int  = 15
    number:      int  = 0


class AnnotationEditor(_Theme):
    """Annotations-Editor mit horizontaler Toolbar und Filmstreifen."""

    TOOLS = [
        ('arrow',     '→',  'Pfeil'),
        ('line',      '╱',  'Linie'),
        ('rect',      '□',  'Rechteck'),
        ('text',      'T',  'Text'),
        ('callout',   '💬', 'Callout'),
        ('highlight', '▓',  'Markierung'),
        ('blur',      '≋',  'Weichzeichner'),
        ('blackout',  '■',  'Schwärzung'),
        ('ellipse',   '◯',  'Ellipse'),
        ('freehand',  '✏',  'Freihand'),
        ('step',      '①',  'Schritt'),
        ('crop',      '⬒',  'Zuschneiden'),
    ]

    # Zusätzliche Farben (nur Editor)
    BG_STRIP     = '#F8FAFC'
    BG_CELL      = '#FFFFFF'

    _CONFIG_PATH = os.path.join(os.path.expanduser('~'),
                                '.screenshot_tool_config.json')

    def __init__(self, parent: tk.Tk, image: Image.Image, app,
                 history: HistoryManager | None = None):
        self.parent  = parent
        self.image   = image.copy()
        self.app     = app
        self.history = history or HistoryManager()

        self._settings = self._load_settings()

        self.annotations: list[Annotation] = []
        # Undo/Redo: list of (annotations_copy, image_or_None)
        self.undo_stack: list[tuple[list[Annotation], Image.Image | None]] = []
        self.redo_stack: list[tuple[list[Annotation], Image.Image | None]] = []

        self.active_tool = 'arrow'
        self.tool_color  = '#FF0000'
        self.tool_width  = 3
        self.font_size   = 16

        self._drawing    = False
        self._drag_start = (0, 0)
        self._freehand_points: list[tuple[int, int]] = []
        self._step_counter = 0
        self.blur_radius = 15

        self._thumb_photos: list[ImageTk.PhotoImage] = []
        self._current_entry_id: str | None = None

        self.win:         tk.Toplevel | None        = None
        self.canvas:      tk.Canvas | None          = None
        self._base_photo: ImageTk.PhotoImage | None = None

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def load_image(self, image: Image.Image, entry_id: str | None = None):
        self._autosave()
        self._current_entry_id = entry_id
        self.image = image.copy()
        self.annotations.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._step_counter = 0
        self._update_undo_redo_state()
        self._redraw_canvas()
        self._refresh_filmstrip()
        self.win.lift()
        self.win.focus_force()
        self._status_var.set('Neuer Screenshot geladen')

    def _autosave(self):
        if not self.annotations or not self._current_entry_id:
            return
        try:
            self._status_var.set('Autospeicherung …')
            self.history.update(self._current_entry_id, self._composite_image())
            self._refresh_filmstrip()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Einstellungen (persistent)
    # ------------------------------------------------------------------

    @classmethod
    def _load_settings(cls) -> dict:
        defaults = {
            'quick_save_dir': os.path.join(os.path.expanduser('~'), 'Desktop'),
        }
        try:
            with open(cls._CONFIG_PATH, 'r') as f:
                stored = json.load(f)
            defaults.update(stored)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        # Validierung: Ordner muss existieren
        if not os.path.isdir(defaults['quick_save_dir']):
            defaults['quick_save_dir'] = os.path.expanduser('~')
        return defaults

    def _save_settings(self):
        try:
            with open(self._CONFIG_PATH, 'w') as f:
                json.dump(self._settings, f, indent=2)
        except OSError:
            pass

    def _change_save_dir(self):
        """Lässt den Nutzer den Quick-Save-Ordner auswählen."""
        new_dir = filedialog.askdirectory(
            parent=self.win,
            initialdir=self._settings['quick_save_dir'],
            title='Schnell-Export Zielordner wählen')
        if new_dir:
            self._settings['quick_save_dir'] = new_dir
            self._save_settings()
            # Label in Export-Bar aktualisieren
            short = self._short_path(new_dir)
            self._save_dir_label.config(text=f'📂 {short}')
            self._show_toast(f'Zielordner: {short}')

    @staticmethod
    def _short_path(path: str, max_len: int = 30) -> str:
        """Kürzt einen Pfad für die Anzeige."""
        home = os.path.expanduser('~')
        if path.startswith(home):
            path = '~' + path[len(home):]
        if len(path) <= max_len:
            return path
        parts = path.split(os.sep)
        return os.sep.join([parts[0], '…', parts[-1]])

    def show(self, entry_id: str | None = None):
        self._current_entry_id = entry_id
        self.win = tk.Toplevel(self.parent)
        self.win.title('Screenshot-Editor')
        self.win.attributes('-topmost', False)

        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        iw, ih = self.image.size
        win_w  = min(iw + 120, int(sw * 0.9))
        win_h  = min(ih + 230, int(sh * 0.92))
        self.win.geometry(f'{win_w}x{win_h}')

        self._setup_styles()
        self._build_menu()
        self._build_statusbar()   # side='bottom' → zuerst packen
        self._build_filmstrip()   # side='bottom' → vor Canvas packen!
        self._build_export_bar()  # side='bottom' → prominente Export-Leiste
        self._build_toolbar()     # side='top'
        self._build_canvas()      # fill='both', expand=True → zuletzt!
        self._bind_shortcuts()
        self._redraw_canvas()
        self.win.protocol('WM_DELETE_WINDOW', self._on_close)

    def _setup_styles(self):
        """Konfiguriert alle ttk-Styles für ein modernes Erscheinungsbild."""
        self._style = ttk.Style(self.win)
        self._style.theme_use('clam')

        # ── Werkzeug-Buttons (kompakt, Zeile 1) ──────────────────────
        self._style.configure('Tool.TButton',
            font=(FONT_FAMILY, 13),
            padding=(6, 4),
            relief='flat',
            background=self.BTN_NORM,
            foreground=self.BTN_FG,
            borderwidth=0)
        self._style.map('Tool.TButton',
            background=[('active', self.ACCENT_LIGHT),
                        ('pressed', self.ACCENT)],
            foreground=[('active', self.ACCENT),
                        ('pressed', 'white')])

        # Werkzeug selektiert
        self._style.configure('ToolSel.TButton',
            font=(FONT_FAMILY, 13),
            padding=(6, 4),
            relief='flat',
            background=self.ACCENT,
            foreground='white',
            borderwidth=0)
        self._style.map('ToolSel.TButton',
            background=[('active', self.ACCENT_HOV),
                        ('pressed', self.ACCENT_HOV)])

        # ── Controls-Zeile: Undo/Redo ────────────────────────────────
        self._style.configure('UndoRedo.TButton',
            font=(FONT_FAMILY, 11),
            padding=(8, 3),
            relief='flat',
            background=self.BTN_NORM,
            foreground=self.BTN_FG,
            borderwidth=0)
        self._style.map('UndoRedo.TButton',
            background=[('active', self.BTN_HOV),
                        ('disabled', self.BTN_NORM)],
            foreground=[('disabled', self.DIVIDER)])

        # ── Export-Bar: dunkle Buttons ────────────────────────────────
        self._style.configure('Export.TButton',
            font=(FONT_FAMILY, 10, 'bold'),
            padding=(14, 7),
            relief='flat',
            background=self.EXPORT_BTN,
            foreground='#E2E8F0',
            borderwidth=0)
        self._style.map('Export.TButton',
            background=[('active', self.EXPORT_HOV),
                        ('pressed', '#64748B')],
            foreground=[('active', 'white'),
                        ('pressed', 'white')])

        # Clipboard-Button
        self._style.configure('ExportClip.TButton',
            font=(FONT_FAMILY, 10),
            padding=(12, 7),
            relief='flat',
            background=self.EXPORT_BTN,
            foreground='#CBD5E1',
            borderwidth=0)
        self._style.map('ExportClip.TButton',
            background=[('active', self.EXPORT_HOV)],
            foreground=[('active', 'white')])

        # Speichern-unter (Akzent)
        self._style.configure('SaveAs.TButton',
            font=(FONT_FAMILY, 11, 'bold'),
            padding=(18, 8),
            relief='flat',
            background=self.ACCENT,
            foreground='white',
            borderwidth=0)
        self._style.map('SaveAs.TButton',
            background=[('active', self.ACCENT_HOV),
                        ('pressed', '#1E40AF')])

    # ------------------------------------------------------------------
    # Hover-Hilfsmethoden
    # ------------------------------------------------------------------

    def _add_hover(self, widget: tk.Widget,
                   hover_bg: str, hover_fg: str,
                   normal_bg: str, normal_fg: str):
        widget.bind('<Enter>',
                    lambda e: widget.config(bg=hover_bg, fg=hover_fg))
        widget.bind('<Leave>',
                    lambda e: widget.config(bg=normal_bg, fg=normal_fg))

    def _add_tool_hover(self, btn, tool_id: str):
        """Hover für ttk Tool-Buttons (nicht mehr benötigt, ttk macht
        Hover über style.map automatisch)."""
        pass

    def _add_tooltip(self, widget: tk.Widget, text: str):
        tip_win = [None]
        delay_id = [None]

        def show(e):
            def _create():
                tw = tk.Toplevel(widget)
                tw.wm_overrideredirect(True)
                tw.wm_geometry(f'+{e.x_root + 8}+{e.y_root + 24}')
                tw.attributes('-alpha', 0.92)
                tk.Label(tw, text=text, bg='#0F172A', fg='#E2E8F0',
                         font=(FONT_FAMILY, 9), padx=8, pady=4).pack()
                tip_win[0] = tw
            delay_id[0] = widget.after(400, _create)

        def hide(e):
            if delay_id[0]:
                widget.after_cancel(delay_id[0])
                delay_id[0] = None
            if tip_win[0]:
                tip_win[0].destroy()
                tip_win[0] = None

        widget.bind('<Enter>', show, add='+')
        widget.bind('<Leave>', hide, add='+')

    # ------------------------------------------------------------------
    # GUI-Aufbau
    # ------------------------------------------------------------------

    def _build_menu(self):
        # Tastenkürzel-Labels plattformabhängig
        mod = 'Cmd' if IS_MACOS else 'Ctrl'
        mb = tk.Menu(self.win, bg=self.BG_TOOLBAR, fg=self.FG_MAIN,
                     activebackground=self.ACCENT, activeforeground='white')
        fm = tk.Menu(mb, tearoff=0, bg=self.BG_TOOLBAR, fg=self.FG_MAIN,
                     activebackground=self.ACCENT, activeforeground='white')
        fm.add_command(label=f'Speichern  {mod}+S',       command=self.save_to_file)
        fm.add_command(label=f'In Zwischenablage  {mod}+C', command=self.copy_to_clipboard)
        fm.add_separator()
        fm.add_command(label='Schließen',               command=self._on_close)
        mb.add_cascade(label='Datei', menu=fm)

        em = tk.Menu(mb, tearoff=0, bg=self.BG_TOOLBAR, fg=self.FG_MAIN,
                     activebackground=self.ACCENT, activeforeground='white')
        em.add_command(label=f'Rückgängig        {mod}+Z', command=self._undo)
        em.add_command(label=f'Wiederherstellen  {mod}+Y', command=self._redo)
        mb.add_cascade(label='Bearbeiten', menu=em)

        im = tk.Menu(mb, tearoff=0, bg=self.BG_TOOLBAR, fg=self.FG_MAIN,
                     activebackground=self.ACCENT, activeforeground='white')
        im.add_command(label='Größe ändern …',      command=self._resize_image)
        im.add_command(label='Wasserzeichen …',      command=self._add_watermark)
        im.add_separator()
        im.add_command(label='Schatten hinzufügen',  command=self._add_shadow)
        im.add_command(label='Rahmen hinzufügen …',  command=self._add_border)
        mb.add_cascade(label='Bild', menu=im)

        self.win.config(menu=mb, bg=self.BG_MAIN)

    def _build_toolbar(self):
        toolbar_wrap = tk.Frame(self.win, bg=self.BG_TOOLBAR)
        toolbar_wrap.pack(side='top', fill='x')

        # ════════ Zeile 1: Werkzeuge ══════════════════════════════════
        row1 = tk.Frame(toolbar_wrap, bg=self.BG_TOOLBAR)
        row1.pack(fill='x', padx=10, pady=(6, 0))

        self._tool_buttons: dict[str, ttk.Button] = {}
        for tool_id, symbol, label in self.TOOLS:
            btn = ttk.Button(row1, text=symbol, style='Tool.TButton',
                             command=lambda t=tool_id: self._select_tool(t),
                             cursor='hand2')
            btn.pack(side='left', padx=1)
            self._tool_buttons[tool_id] = btn
            self._add_tooltip(btn, label)

        # Bildgröße rechts in Zeile 1
        iw, ih = self.image.size
        self._size_label = tk.Label(
            row1, text=f'{iw} × {ih} px', bg=self.BG_TOOLBAR,
            fg=self.FG_MUTED, font=(FONT_FAMILY, 9))
        self._size_label.pack(side='right', padx=(0, 4))

        # Thin divider between rows
        tk.Frame(toolbar_wrap, bg=self.DIVIDER, height=1).pack(
            fill='x', padx=10, pady=0)

        # ════════ Zeile 2: Controls ═══════════════════════════════════
        row2 = tk.Frame(toolbar_wrap, bg=self.BG_TOOLBAR)
        row2.pack(fill='x', padx=10, pady=(4, 6))

        # ── Farb-Swatch ──────────────────────────────────────────────
        self._color_swatch = tk.Frame(
            row2, bg=self.tool_color, width=32, height=22,
            highlightthickness=2, highlightbackground=self.DIVIDER,
            cursor='hand2')
        self._color_swatch.pack(side='left', padx=(0, 4))
        self._color_swatch.pack_propagate(False)
        self._color_swatch.bind('<Button-1>', lambda e: self._pick_color())
        self._color_swatch.bind('<Enter>',
            lambda e: self._color_swatch.config(
                highlightbackground=self.ACCENT))
        self._color_swatch.bind('<Leave>',
            lambda e: self._color_swatch.config(
                highlightbackground=self.DIVIDER))
        self._add_tooltip(self._color_swatch, 'Farbe wählen')

        self._toolbar_sep(row2)

        # ── Strichbreite / Schrift / Blur (inline) ────────────────────
        for label_text, var_name, default, lo, hi, cmd in [
            ('Breite',  '_width_var', self.tool_width,  1, 20, '_update_width'),
            ('Schrift', '_font_var',  self.font_size,   8, 72, '_update_font'),
            ('Blur',    '_blur_var',  self.blur_radius,  1, 50, '_update_blur'),
        ]:
            tk.Label(row2, text=label_text, bg=self.BG_TOOLBAR,
                     fg=self.FG_MUTED, font=(FONT_FAMILY, 8)
                     ).pack(side='left', padx=(4, 2))
            var = tk.IntVar(value=default)
            setattr(self, var_name, var)
            tk.Spinbox(row2, from_=lo, to=hi, textvariable=var,
                       width=3, font=(FONT_FAMILY, 9), relief='flat',
                       bg=self.BTN_NORM, fg=self.FG_MAIN,
                       buttonbackground=self.BTN_NORM,
                       command=getattr(self, cmd)
                       ).pack(side='left', padx=(0, 4))

        self._toolbar_sep(row2)

        # ── Undo / Redo ──────────────────────────────────────────────
        self._undo_btn = ttk.Button(row2, text='↩ Zurück',
            style='UndoRedo.TButton', command=self._undo,
            state='disabled', cursor='hand2')
        self._undo_btn.pack(side='left', padx=2)
        self._add_tooltip(self._undo_btn, 'Rückgängig  ⌘Z')

        self._redo_btn = ttk.Button(row2, text='↪ Vor',
            style='UndoRedo.TButton', command=self._redo,
            state='disabled', cursor='hand2')
        self._redo_btn.pack(side='left', padx=2)
        self._add_tooltip(self._redo_btn, 'Wiederherstellen  ⌘Y')

        # Bottom divider
        tk.Frame(toolbar_wrap, bg=self.DIVIDER, height=1).pack(
            side='bottom', fill='x')

        self._select_tool('arrow')

    @staticmethod
    def _toolbar_sep(parent):
        tk.Frame(parent, bg='#CBD5E1', width=1).pack(
            side='left', fill='y', padx=8, pady=1)

    def _build_canvas(self):
        frame = tk.Frame(self.win, bg=self.BG_MAIN)
        frame.pack(side='left', fill='both', expand=True)

        hbar = tk.Scrollbar(frame, orient='horizontal')
        hbar.pack(side='bottom', fill='x')
        vbar = tk.Scrollbar(frame, orient='vertical')
        vbar.pack(side='right', fill='y')

        self.canvas = tk.Canvas(frame, bg=self.BG_CANVAS,
                                xscrollcommand=hbar.set,
                                yscrollcommand=vbar.set,
                                cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)
        hbar.config(command=self.canvas.xview)
        vbar.config(command=self.canvas.yview)

        iw, ih = self.image.size
        self.canvas.config(scrollregion=(0, 0, iw, ih))
        self.canvas.bind('<ButtonPress-1>',   self._on_mouse_down)
        self.canvas.bind('<B1-Motion>',        self._on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_mouse_up)
        # macOS: Button-2 = Rechtsklick; Windows/Linux: Button-3
        if IS_MACOS:
            self.canvas.bind('<Button-2>', self._on_right_click)
        else:
            self.canvas.bind('<Button-3>', self._on_right_click)

    def _build_filmstrip(self):
        STRIP_H = 132
        tk.Frame(self.win, bg=self.DIVIDER, height=1).pack(
            side='bottom', fill='x')

        strip_frame = tk.Frame(self.win, bg=self.BG_STRIP, height=STRIP_H)
        strip_frame.pack(side='bottom', fill='x')
        strip_frame.pack_propagate(False)

        hdr = tk.Frame(strip_frame, bg=self.BG_STRIP)
        hdr.pack(side='left', fill='y', padx=(12, 4))
        tk.Label(hdr, text='🗂', bg=self.BG_STRIP, fg=self.ACCENT,
                 font=(FONT_FAMILY, 18)).pack(pady=(14, 0))
        tk.Label(hdr, text='VERLAUF', bg=self.BG_STRIP, fg=self.FG_MUTED,
                 font=(FONT_FAMILY, 7, 'bold')).pack()

        tk.Frame(strip_frame, bg=self.DIVIDER, width=1).pack(
            side='left', fill='y', pady=12, padx=(4, 0))

        outer = tk.Frame(strip_frame, bg=self.BG_STRIP)
        outer.pack(side='left', fill='both', expand=True)

        hbar = tk.Scrollbar(outer, orient='horizontal')
        hbar.pack(side='bottom', fill='x')

        self._strip_canvas = tk.Canvas(outer, bg=self.BG_STRIP,
                                       height=STRIP_H - 20,
                                       xscrollcommand=hbar.set,
                                       highlightthickness=0)
        self._strip_canvas.pack(side='top', fill='both', expand=True)
        hbar.config(command=self._strip_canvas.xview)

        self._strip_inner = tk.Frame(self._strip_canvas, bg=self.BG_STRIP)
        self._strip_canvas.create_window(0, 0, anchor='nw',
                                          window=self._strip_inner)
        self._strip_inner.bind('<Configure>',
            lambda e: self._strip_canvas.config(
                scrollregion=self._strip_canvas.bbox('all')))

        self._refresh_filmstrip()

    def _refresh_filmstrip(self):
        for w in self._strip_inner.winfo_children():
            w.destroy()
        self._thumb_photos.clear()

        entries = self.history.get_entries()
        if not entries:
            tk.Label(self._strip_inner,
                     text='Noch keine Screenshots vorhanden',
                     bg=self.BG_STRIP, fg=self.FG_MUTED,
                     font=(FONT_FAMILY, 9)).pack(padx=20, pady=20)
            return
        for entry in entries:
            self._add_thumb_widget(entry)

    def _add_thumb_widget(self, entry: dict):
        thumb_img = self.history.load_thumbnail(entry['id'])
        is_active = (entry['id'] == self._current_entry_id)

        card = tk.Frame(self._strip_inner, bg=self.BG_CELL,
                        highlightthickness=2,
                        highlightbackground=self.ACCENT if is_active
                                            else self.DIVIDER)
        card.pack(side='left', padx=5, pady=6)

        if is_active:
            tk.Frame(card, bg=self.ACCENT, height=3).pack(fill='x', side='top')

        if thumb_img:
            photo = ImageTk.PhotoImage(thumb_img)
            self._thumb_photos.append(photo)
            img_lbl = tk.Label(card, image=photo, bg=self.BG_CELL,
                               cursor='hand2')
            img_lbl.pack(padx=4, pady=(3 if not is_active else 0, 0))
            img_lbl.bind('<Button-1>',
                lambda e, eid=entry['id']: self._load_from_history(eid))
        else:
            img_lbl = tk.Label(card, text='?', bg=self.BG_CELL,
                               fg=self.FG_MUTED, width=14, height=5)
            img_lbl.pack(padx=4, pady=3)

        ts = entry.get('timestamp_display', '')[-8:]
        time_lbl = tk.Label(card, text=ts, bg=self.BG_CELL,
                            fg=self.ACCENT if is_active else self.FG_MUTED,
                            font=(FONT_FAMILY, 7,
                                  'bold' if is_active else 'normal'))
        time_lbl.pack(pady=(1, 0))

        del_btn = tk.Button(card, text='✕', font=(FONT_FAMILY, 7),
                            bg=self.BG_CELL, fg=self.FG_MUTED,
                            activebackground=self.DANGER,
                            activeforeground='white',
                            relief='flat', padx=4, pady=1,
                            bd=0, cursor='hand2',
                            command=lambda eid=entry['id']:
                                self._delete_history_entry(eid))
        del_btn.pack(fill='x', padx=3, pady=(0, 3))

        def on_card_enter(e):
            card.config(highlightbackground=self.ACCENT)
        def on_card_leave(e):
            card.config(highlightbackground=self.ACCENT if is_active
                                            else self.DIVIDER)
        for w in [card, img_lbl, time_lbl]:
            w.bind('<Enter>', on_card_enter)
            w.bind('<Leave>', on_card_leave)

        del_btn.bind('<Enter>',
            lambda e: del_btn.config(bg=self.DANGER, fg='white'))
        del_btn.bind('<Leave>',
            lambda e: del_btn.config(bg=self.BG_CELL, fg=self.FG_MUTED))

    def _load_from_history(self, entry_id: str):
        img = self.history.load_image(entry_id)
        if img is None:
            messagebox.showwarning('Verlauf', 'Bild nicht mehr verfügbar.',
                                   parent=self.win)
            return
        self._autosave()
        self._current_entry_id = entry_id
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.annotations.clear()
        self._step_counter = 0
        self.image = img
        self._redraw_canvas()
        self._refresh_filmstrip()
        self._update_undo_redo_state()
        self._status_var.set('Bild aus Verlauf geladen')

    def _delete_history_entry(self, entry_id: str):
        self.history.remove(entry_id)
        self._refresh_filmstrip()
        self._status_var.set('Eintrag aus Verlauf gelöscht')

    def _build_statusbar(self):
        self._status_var = tk.StringVar(value='Bereit')
        SBG = '#F1F5F9'
        bar = tk.Frame(self.win, bg=SBG)
        bar.pack(side='bottom', fill='x')
        tk.Frame(self.win, bg=self.DIVIDER, height=1).pack(
            side='bottom', fill='x')
        row = tk.Frame(bar, bg=SBG)
        row.pack(fill='x', padx=12, pady=3)
        self._status_dot = tk.Label(row, text='●', bg=SBG,
                                    fg=self.SUCCESS, font=(FONT_FAMILY, 6))
        self._status_dot.pack(side='left')
        tk.Label(row, textvariable=self._status_var, anchor='w',
                 bg=SBG, fg=self.FG_MUTED,
                 font=(FONT_FAMILY, 8)).pack(side='left', padx=(4, 0))

    def _build_export_bar(self):
        """Dark-Theme Export-Leiste mit ttk-Buttons."""
        EBG  = self.EXPORT_BG
        EMUT = '#94A3B8'

        bar = tk.Frame(self.win, bg=EBG, height=54)
        bar.pack(side='bottom', fill='x')
        bar.pack_propagate(False)

        inner = tk.Frame(bar, bg=EBG)
        inner.pack(fill='both', expand=True, padx=14, pady=8)

        # ── Links: Clipboard ──────────────────────────────────────────
        tk.Label(inner, text='EXPORT', bg=EBG, fg=EMUT,
                 font=(FONT_FAMILY, 7, 'bold')).pack(side='left',
                                                      padx=(0, 12))

        ttk.Button(inner, text='📋 Clipboard', style='ExportClip.TButton',
                   command=self.copy_to_clipboard, cursor='hand2'
                   ).pack(side='left', padx=(0, 6))

        tk.Frame(inner, bg='#475569', width=1).pack(
            side='left', fill='y', padx=8, pady=2)

        # ── Quick-Export Format-Buttons ───────────────────────────────
        for fmt, label in [('png', 'PNG'), ('jpg', 'JPG'), ('pdf', 'PDF')]:
            ttk.Button(inner, text=label, style='Export.TButton',
                       command=lambda f=fmt: self._quick_save(f),
                       cursor='hand2').pack(side='left', padx=2)

        # ── Zielordner ───────────────────────────────────────────────
        tk.Frame(inner, bg='#475569', width=1).pack(
            side='left', fill='y', padx=8, pady=2)

        short = self._short_path(self._settings['quick_save_dir'])
        self._save_dir_label = tk.Label(
            inner, text=f'📂 {short}', bg=EBG, fg=EMUT,
            font=(FONT_FAMILY, 9), cursor='hand2')
        self._save_dir_label.pack(side='left', padx=(0, 4))
        self._save_dir_label.bind('<Button-1>',
                                  lambda e: self._change_save_dir())
        self._save_dir_label.bind('<Enter>',
            lambda e: self._save_dir_label.config(fg='white'))
        self._save_dir_label.bind('<Leave>',
            lambda e: self._save_dir_label.config(fg=EMUT))
        self._add_tooltip(self._save_dir_label, 'Zielordner ändern')

        # ── Rechts: Speichern unter … ─────────────────────────────────
        ttk.Button(inner, text='Speichern unter …', style='SaveAs.TButton',
                   command=self.save_to_file, cursor='hand2'
                   ).pack(side='right', padx=(8, 0))

    def _bind_shortcuts(self):
        # macOS: Command statt Control
        mod = 'Command' if IS_MACOS else 'Control'
        self.win.bind(f'<{mod}-z>', lambda e: self._undo())
        self.win.bind(f'<{mod}-y>', lambda e: self._redo())
        self.win.bind(f'<{mod}-s>', lambda e: self.save_to_file())
        self.win.bind(f'<{mod}-c>', lambda e: self.copy_to_clipboard())
        for i, (tool_id, _, _) in enumerate(self.TOOLS):
            if i < 9:
                self.win.bind(str(i + 1),
                              lambda e, t=tool_id: self._select_tool(t))
            elif i == 9:
                self.win.bind('0',
                              lambda e, t=tool_id: self._select_tool(t))

    # ------------------------------------------------------------------
    # Tool-Steuerung
    # ------------------------------------------------------------------

    def _select_tool(self, tool_id: str):
        self.active_tool = tool_id
        for tid, btn in self._tool_buttons.items():
            btn.configure(style='ToolSel.TButton' if tid == tool_id
                                else 'Tool.TButton')
        self._update_status()

    def _pick_color(self):
        c = colorchooser.askcolor(color=self.tool_color,
                                  parent=self.win, title='Farbe wählen')
        if c and c[1]:
            self.tool_color = c[1]
            self._color_swatch.config(bg=self.tool_color)

    def _update_width(self):
        self.tool_width = self._width_var.get()

    def _update_font(self):
        self.font_size = self._font_var.get()

    def _update_blur(self):
        self.blur_radius = self._blur_var.get()

    def _update_status(self):
        labels = {t[0]: t[2] for t in self.TOOLS}
        self._status_var.set(
            f'Werkzeug: {labels.get(self.active_tool, "")}  |  '
            f'Farbe: {self.tool_color}  |  '
            f'Breite: {self.tool_width}')

    # ------------------------------------------------------------------
    # Maus-Events
    # ------------------------------------------------------------------

    def _canvas_coords(self, event):
        return int(self.canvas.canvasx(event.x)), int(self.canvas.canvasy(event.y))

    def _on_mouse_down(self, event):
        self._drawing    = True
        x, y             = self._canvas_coords(event)
        self._drag_start = (x, y)
        if self.active_tool == 'text':
            self._handle_text(x, y)
            self._drawing = False
        elif self.active_tool == 'callout':
            self._handle_callout_start(x, y)
        elif self.active_tool == 'freehand':
            self._freehand_points = [(x, y)]
        elif self.active_tool == 'step':
            self._handle_step(x, y)
            self._drawing = False

    def _on_mouse_drag(self, event):
        if not self._drawing:
            return
        x, y    = self._canvas_coords(event)
        x0, y0  = self._drag_start
        if self.active_tool == 'freehand':
            self._freehand_points.append((x, y))
            self._draw_freehand_preview()
            return
        self._draw_preview(x0, y0, x, y)

    def _on_mouse_up(self, event):
        if not self._drawing:
            return
        self._drawing = False
        x, y   = self._canvas_coords(event)
        x0, y0 = self._drag_start
        if self.active_tool == 'freehand':
            self._freehand_points.append((x, y))
            if len(self._freehand_points) > 2:
                ann = Annotation(kind='freehand', color=self.tool_color,
                                 width=self.tool_width,
                                 points=list(self._freehand_points))
                self._commit(ann)
            self._freehand_points.clear()
            self._clear_preview()
            return
        if abs(x - x0) < 2 and abs(y - y0) < 2:
            self._clear_preview()
            return
        if self.active_tool == 'callout':
            return
        if self.active_tool == 'crop':
            self._handle_crop(x0, y0, x, y)
            self._clear_preview()
            return
        ann = self._make_annotation(x0, y0, x, y)
        if ann:
            self._commit(ann)
        self._clear_preview()

    # ------------------------------------------------------------------
    # Vorschau während des Ziehens
    # ------------------------------------------------------------------

    def _draw_preview(self, x0, y0, x1, y1):
        self.canvas.delete('preview')
        tool = self.active_tool
        c, w = self.tool_color, self.tool_width

        if tool == 'arrow':
            self.canvas.create_line(x0, y0, x1, y1, fill=c, width=w,
                                    arrow=tk.LAST, arrowshape=(16, 20, 6),
                                    tag='preview')
        elif tool == 'line':
            self.canvas.create_line(x0, y0, x1, y1, fill=c, width=w,
                                    tag='preview')
        elif tool == 'rect':
            self.canvas.create_rectangle(x0, y0, x1, y1, outline=c, width=w,
                                         tag='preview')
        elif tool == 'ellipse':
            self.canvas.create_oval(x0, y0, x1, y1, outline=c, width=w,
                                    tag='preview')
        elif tool == 'crop':
            self.canvas.create_rectangle(x0, y0, x1, y1,
                                         outline='#00D4FF', width=2,
                                         dash=(6, 4), tag='preview')
            lbl = f'{abs(x1 - x0)} × {abs(y1 - y0)} px'
            self.canvas.create_text(min(x0, x1) + 4,
                                     min(y0, y1) - 18,
                                     text=lbl, fill='#00D4FF',
                                     font=(FONT_FAMILY, 10, 'bold'),
                                     anchor='nw', tag='preview')
        elif tool in ('highlight', 'blur', 'blackout'):
            fill = c if tool == 'highlight' else (
                'gray' if tool == 'blur' else 'black')
            stip = 'gray50' if tool == 'highlight' else ''
            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                outline=c if tool == 'highlight' else fill,
                fill=fill, stipple=stip, width=1, tag='preview')

    def _draw_freehand_preview(self):
        self.canvas.delete('preview')
        if len(self._freehand_points) < 2:
            return
        coords = []
        for px, py in self._freehand_points:
            coords.extend([px, py])
        self.canvas.create_line(*coords, fill=self.tool_color,
                                width=self.tool_width, smooth=True,
                                tag='preview')

    def _clear_preview(self):
        self.canvas.delete('preview')

    # ------------------------------------------------------------------
    # Annotierungen erstellen
    # ------------------------------------------------------------------

    def _make_annotation(self, x0, y0, x1, y1) -> Annotation | None:
        if self.active_tool not in ('arrow', 'line', 'rect', 'ellipse',
                                    'highlight', 'blur', 'blackout'):
            return None
        ann = Annotation(kind=self.active_tool,
                         x1=x0, y1=y0, x2=x1, y2=y1,
                         color=self.tool_color, width=self.tool_width)
        if self.active_tool == 'blur':
            ann.blur_radius = self.blur_radius
        return ann

    def _handle_text(self, x, y):
        text = simpledialog.askstring('Text eingeben', 'Beschriftung:',
                                      parent=self.win)
        if text:
            self._commit(Annotation(kind='text', x1=x, y1=y, x2=x, y2=y,
                                    color=self.tool_color,
                                    font_size=self.font_size, text=text))

    def _handle_callout_start(self, x, y):
        text = simpledialog.askstring('Callout-Text', 'Beschriftung:',
                                      parent=self.win)
        if not text:
            self._drawing = False
            return
        self._callout_text = text
        self._callout_x    = x
        self._callout_y    = y
        self._status_var.set(
            'Schweif-Spitze setzen: Klicke auf das Ziel des Callouts')
        self.canvas.bind('<ButtonPress-1>', self._handle_callout_tip)

    def _handle_callout_tip(self, event):
        self.canvas.bind('<ButtonPress-1>', self._on_mouse_down)
        x, y = self._canvas_coords(event)
        # Bubble-Größe dynamisch an Text anpassen
        bubble_w = max(120, int(len(self._callout_text) * self.font_size * 0.65) + 16)
        bubble_h = max(40, self.font_size + 16)
        self._commit(Annotation(
            kind='callout',
            x1=self._callout_x, y1=self._callout_y,
            x2=self._callout_x + bubble_w, y2=self._callout_y + bubble_h,
            color=self.tool_color, width=self.tool_width,
            font_size=self.font_size, text=self._callout_text,
            tail_x=x, tail_y=y))
        self._drawing = False
        self._update_status()

    def _handle_step(self, x, y):
        self._step_counter += 1
        r = max(16, self.font_size)
        self._commit(Annotation(
            kind='step', x1=x, y1=y, x2=x + r * 2, y2=y + r * 2,
            color=self.tool_color, font_size=self.font_size,
            number=self._step_counter))

    def _handle_crop(self, x0, y0, x1, y1):
        cx1, cy1 = min(x0, x1), min(y0, y1)
        cx2, cy2 = max(x0, x1), max(y0, y1)
        iw, ih = self.image.size
        cx1, cy1 = max(0, cx1), max(0, cy1)
        cx2, cy2 = min(iw, cx2), min(ih, cy2)
        if cx2 - cx1 < 10 or cy2 - cy1 < 10:
            return
        self._push_undo(save_image=True)
        if self.annotations:
            self.image = self._composite_image()
            self.annotations.clear()
        self.image = self.image.crop((cx1, cy1, cx2, cy2))
        self._finish_image_op(f'Zugeschnitten auf {cx2-cx1} × {cy2-cy1} px')

    def _on_right_click(self, event):
        x, y = self._canvas_coords(event)
        # Finde die letzte (oberste) Annotation unter dem Klick
        hit_idx = None
        for i in range(len(self.annotations) - 1, -1, -1):
            ann = self.annotations[i]
            if ann.kind == 'freehand':
                # Prüfe ob Punkt in der Nähe eines Freehand-Segments liegt
                for px, py in ann.points:
                    if abs(px - x) < 10 and abs(py - y) < 10:
                        hit_idx = i
                        break
                if hit_idx is not None:
                    break
            elif ann.kind == 'step':
                r = max(16, ann.font_size)
                cx, cy = ann.x1 + r, ann.y1 + r
                if (x - cx) ** 2 + (y - cy) ** 2 <= (r + 4) ** 2:
                    hit_idx = i
                    break
            elif ann.kind == 'text':
                # Ungefährer Treffer-Test für Text
                tw = len(ann.text) * ann.font_size * 0.6
                th = ann.font_size * 1.4
                if ann.x1 <= x <= ann.x1 + tw and ann.y1 <= y <= ann.y1 + th:
                    hit_idx = i
                    break
            else:
                ax1, ay1 = min(ann.x1, ann.x2), min(ann.y1, ann.y2)
                ax2, ay2 = max(ann.x1, ann.x2), max(ann.y1, ann.y2)
                if ax1 - 5 <= x <= ax2 + 5 and ay1 - 5 <= y <= ay2 + 5:
                    hit_idx = i
                    break

        if hit_idx is None:
            return
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(
            label='Annotation löschen',
            command=lambda idx=hit_idx: self._delete_annotation(idx))
        menu.tk_popup(event.x_root, event.y_root)

    def _delete_annotation(self, idx: int):
        self._push_undo()
        del self.annotations[idx]
        self._step_counter = max(
            (a.number for a in self.annotations if a.kind == 'step'),
            default=0)
        self._finish_image_op('Annotation gelöscht')

    # ------------------------------------------------------------------
    # Undo / Commit
    # ------------------------------------------------------------------

    def _commit(self, ann: Annotation):
        self._push_undo()
        self.annotations.append(ann)
        self._redraw_canvas()
        self._update_undo_redo_state()

    def _undo(self):
        if not self.undo_stack:
            return
        prev_anns, prev_img = self.undo_stack.pop()
        # Redo muss das aktuelle Bild speichern falls es sich ändert
        redo_img = self.image.copy() if prev_img is not None else None
        self.redo_stack.append((deepcopy(self.annotations), redo_img))
        self.annotations = prev_anns
        if prev_img is not None:
            self.image = prev_img
        self._step_counter = max(
            (a.number for a in self.annotations if a.kind == 'step'),
            default=0)
        self._redraw_canvas()
        self._update_undo_redo_state()

    def _redo(self):
        if not self.redo_stack:
            return
        next_anns, next_img = self.redo_stack.pop()
        undo_img = self.image.copy() if next_img is not None else None
        self.undo_stack.append((deepcopy(self.annotations), undo_img))
        self.annotations = next_anns
        if next_img is not None:
            self.image = next_img
        self._step_counter = max(
            (a.number for a in self.annotations if a.kind == 'step'),
            default=0)
        self._redraw_canvas()
        self._update_undo_redo_state()

    def _update_undo_redo_state(self):
        if hasattr(self, '_undo_btn'):
            self._undo_btn.state(
                ['!disabled'] if self.undo_stack else ['disabled'])
        if hasattr(self, '_redo_btn'):
            self._redo_btn.state(
                ['!disabled'] if self.redo_stack else ['disabled'])

    # ------------------------------------------------------------------
    # Canvas-Redraw
    # ------------------------------------------------------------------

    def _redraw_canvas(self):
        self.canvas.delete('annotation')
        self.canvas.delete('base')
        self._base_photo = ImageTk.PhotoImage(self.image)
        self.canvas.create_image(0, 0, anchor='nw',
                                 image=self._base_photo, tag='base')
        iw, ih = self.image.size
        self.canvas.config(scrollregion=(0, 0, iw, ih))
        # Viewport auf (0,0) zurücksetzen (wichtig nach Crop)
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        for ann in self.annotations:
            self._draw_annotation_on_canvas(ann)

    def _draw_annotation_on_canvas(self, ann: Annotation):
        c, w, tag = ann.color, ann.width, 'annotation'

        if ann.kind == 'arrow':
            self.canvas.create_line(ann.x1, ann.y1, ann.x2, ann.y2,
                fill=c, width=w, arrow=tk.LAST, arrowshape=(16, 20, 6),
                tag=tag)
        elif ann.kind == 'line':
            self.canvas.create_line(ann.x1, ann.y1, ann.x2, ann.y2,
                fill=c, width=w, tag=tag)
        elif ann.kind == 'rect':
            self.canvas.create_rectangle(ann.x1, ann.y1, ann.x2, ann.y2,
                outline=c, width=w, tag=tag)
        elif ann.kind == 'text':
            self.canvas.create_text(ann.x1, ann.y1,
                text=ann.text, fill=c,
                font=(FONT_FAMILY, ann.font_size, 'bold'),
                anchor='nw', tag=tag)
        elif ann.kind == 'callout':
            mx = (ann.x1 + ann.x2) // 2
            self.canvas.create_rectangle(ann.x1, ann.y1, ann.x2, ann.y2,
                fill='white', outline=c, width=w, tag=tag)
            self.canvas.create_polygon(
                mx - 8, ann.y2, mx + 8, ann.y2, ann.tail_x, ann.tail_y,
                fill='white', outline=c, width=w, tag=tag)
            self.canvas.create_text(ann.x1 + 6, ann.y1 + 6,
                text=ann.text, fill=c,
                font=(FONT_FAMILY, ann.font_size), anchor='nw', tag=tag)
        elif ann.kind == 'ellipse':
            self.canvas.create_oval(ann.x1, ann.y1, ann.x2, ann.y2,
                outline=c, width=w, tag=tag)
        elif ann.kind == 'freehand':
            if len(ann.points) >= 2:
                coords = []
                for px, py in ann.points:
                    coords.extend([px, py])
                self.canvas.create_line(*coords, fill=c, width=w,
                    smooth=True, tag=tag)
        elif ann.kind == 'step':
            r = max(16, ann.font_size)
            cx, cy = ann.x1 + r, ann.y1 + r
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                fill=c, outline='white', width=2, tag=tag)
            self.canvas.create_text(cx, cy, text=str(ann.number),
                fill='white', font=(FONT_FAMILY, ann.font_size, 'bold'),
                tag=tag)
        elif ann.kind == 'highlight':
            self.canvas.create_rectangle(ann.x1, ann.y1, ann.x2, ann.y2,
                fill=c, stipple='gray50', outline='', tag=tag)
        elif ann.kind == 'blur':
            self.canvas.create_rectangle(ann.x1, ann.y1, ann.x2, ann.y2,
                fill='gray', stipple='gray50', outline='gray', tag=tag)
        elif ann.kind == 'blackout':
            self.canvas.create_rectangle(ann.x1, ann.y1, ann.x2, ann.y2,
                fill='black', outline='black', tag=tag)

    # ------------------------------------------------------------------
    # PIL-Composite (für Speichern)
    # ------------------------------------------------------------------

    def _composite_image(self) -> Image.Image:
        img = self.image.copy().convert('RGBA')
        for ann in self.annotations:
            img = self._apply_annotation(img, ann)
        return img.convert('RGB')

    def _apply_annotation(self, img: Image.Image,
                          ann: Annotation) -> Image.Image:
        draw = ImageDraw.Draw(img, 'RGBA')

        def rgba(hex_color, alpha=255):
            h = hex_color.lstrip('#')
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha

        c, w = rgba(ann.color), ann.width

        if ann.kind == 'arrow':
            draw.line([(ann.x1, ann.y1), (ann.x2, ann.y2)], fill=c, width=w)
            angle = math.atan2(ann.y2 - ann.y1, ann.x2 - ann.x1)
            size  = max(12, w * 4)
            for a in [angle + 2.5, angle - 2.5]:
                px = ann.x2 - size * math.cos(a)
                py = ann.y2 - size * math.sin(a)
                draw.line([(ann.x2, ann.y2), (int(px), int(py))],
                          fill=c, width=w)
        elif ann.kind == 'line':
            draw.line([(ann.x1, ann.y1), (ann.x2, ann.y2)], fill=c, width=w)
        elif ann.kind == 'rect':
            draw.rectangle([(ann.x1, ann.y1), (ann.x2, ann.y2)],
                           outline=c, width=w)
        elif ann.kind == 'text':
            font = _get_truetype_font(ann.font_size)
            draw.text((ann.x1, ann.y1), ann.text, fill=c, font=font)
        elif ann.kind == 'callout':
            bg = (255, 255, 255, 230)
            draw.rectangle([(ann.x1, ann.y1), (ann.x2, ann.y2)],
                           fill=bg, outline=c, width=w)
            mx = (ann.x1 + ann.x2) // 2
            draw.polygon([(mx - 8, ann.y2), (mx + 8, ann.y2),
                          (ann.tail_x, ann.tail_y)], fill=bg, outline=c)
            font = _get_truetype_font(ann.font_size)
            draw.text((ann.x1 + 6, ann.y1 + 6), ann.text,
                      fill=c, font=font)
        elif ann.kind == 'ellipse':
            draw.ellipse([(ann.x1, ann.y1), (ann.x2, ann.y2)],
                         outline=c, width=w)
        elif ann.kind == 'freehand':
            if len(ann.points) >= 2:
                for i in range(len(ann.points) - 1):
                    draw.line([ann.points[i], ann.points[i + 1]],
                              fill=c, width=w)
        elif ann.kind == 'step':
            r = max(16, ann.font_size)
            cx, cy = ann.x1 + r, ann.y1 + r
            draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)],
                         fill=c, outline=(255, 255, 255, 255), width=2)
            font = _get_truetype_font(ann.font_size)
            bbox = font.getbbox(str(ann.number))
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((cx - tw // 2, cy - th // 2 - bbox[1]),
                      str(ann.number), fill=(255, 255, 255, 255), font=font)
        elif ann.kind == 'highlight':
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            ov_draw = ImageDraw.Draw(overlay)
            ov_draw.rectangle([(ann.x1, ann.y1), (ann.x2, ann.y2)],
                               fill=rgba(ann.color, 100))
            img = Image.alpha_composite(img, overlay)
        elif ann.kind == 'blur':
            x1, y1 = min(ann.x1, ann.x2), min(ann.y1, ann.y2)
            x2, y2 = max(ann.x1, ann.x2), max(ann.y1, ann.y2)
            if x2 > x1 and y2 > y1:
                region  = img.crop((x1, y1, x2, y2))
                blurred = region.filter(
                    ImageFilter.GaussianBlur(radius=ann.blur_radius))
                img.paste(blurred, (x1, y1))
        elif ann.kind == 'blackout':
            x1, y1 = min(ann.x1, ann.x2), min(ann.y1, ann.y2)
            x2, y2 = max(ann.x1, ann.x2), max(ann.y1, ann.y2)
            draw.rectangle([(x1, y1), (x2, y2)], fill=(0, 0, 0, 255))

        del draw
        return img

    # ------------------------------------------------------------------
    # Speichern / Clipboard
    # ------------------------------------------------------------------

    def _save_image_to_path(self, img: Image.Image, path: str):
        """Speichert ein PIL-Image in den angegebenen Pfad (PNG/JPG/PDF)."""
        lp = path.lower()
        if lp.endswith('.pdf'):
            img.convert('RGB').save(path, 'PDF', resolution=150)
        elif lp.endswith(('.jpg', '.jpeg')):
            img.convert('RGB').save(path, quality=95)
        else:
            img.save(path)

    def _show_toast(self, message: str, is_error: bool = False):
        """Zeigt ein modernes Toast-Banner mittig über dem Canvas."""
        bg = self.DANGER if is_error else '#0F172A'
        toast = tk.Frame(self.win, bg=bg, padx=20, pady=10,
                         highlightthickness=1,
                         highlightbackground='#475569' if not is_error
                                             else self.DANGER_HOV)
        lbl = tk.Label(toast, text=message, bg=bg, fg='white',
                       font=(FONT_FAMILY, 11, 'bold'))
        lbl.pack()
        toast.place(relx=0.5, rely=0.0, anchor='n', y=12)
        toast.lift()

        def remove():
            try:
                toast.destroy()
            except tk.TclError:
                pass

        self.win.after(2200, remove)

    def _quick_save(self, fmt: str):
        """Schnell-Export in den konfigurierten Zielordner."""
        save_dir = self._settings.get('quick_save_dir',
                                       os.path.expanduser('~/Desktop'))
        if not os.path.isdir(save_dir):
            save_dir = os.path.expanduser('~')
        filename = f'screenshot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.{fmt}'
        path = os.path.join(save_dir, filename)

        self._status_var.set('Wird gespeichert …')
        self.win.config(cursor='watch')
        self.win.update_idletasks()
        try:
            self._save_image_to_path(self._composite_image(), path)
            short = self._short_path(save_dir)
            self._status_var.set(f'✓ {filename} ({short})')
            self._show_toast(f'✓  {filename}  →  {short}')
        except Exception as e:
            self._status_var.set(f'Fehler: {e}')
            self._show_toast(f'Fehler: {e}', is_error=True)
        finally:
            self.win.config(cursor='')

    def save_to_file(self):
        default = datetime.now().strftime('screenshot_%Y%m%d_%H%M%S.png')
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension='.png',
            initialfile=default,
            filetypes=[('PNG-Bild', '*.png'), ('JPEG-Bild', '*.jpg'),
                       ('PDF-Dokument', '*.pdf'),
                       ('Alle Dateien', '*.*')])
        if not path:
            return
        self._status_var.set('Wird gespeichert …')
        self.win.config(cursor='watch')
        self.win.update_idletasks()
        try:
            self._save_image_to_path(self._composite_image(), path)
            name = os.path.basename(path)
            self._status_var.set(f'✓ Gespeichert: {name}')
            self._show_toast(f'✓  {name}')
        except Exception as e:
            self._status_var.set(f'Fehler: {e}')
            self._show_toast(f'Fehler: {e}', is_error=True)
        finally:
            self.win.config(cursor='')

    def copy_to_clipboard(self):
        img = self._composite_image()
        if IS_WINDOWS:
            self._clipboard_win(img)
        elif IS_MACOS:
            self._clipboard_mac(img)
        else:
            messagebox.showinfo(
                'Zwischenablage',
                'Clipboard wird auf dieser Plattform nicht unterstützt.\n'
                'Bitte speichere das Bild als Datei.',
                parent=self.win)

    def _clipboard_win(self, img: Image.Image):
        try:
            import win32clipboard
        except ImportError:
            messagebox.showinfo(
                'Zwischenablage',
                'pywin32 nicht verfügbar.\n'
                'Bitte speichere das Bild als Datei.',
                parent=self.win)
            return
        output = io.BytesIO()
        img.convert('RGB').save(output, 'BMP')
        data = output.getvalue()[14:]
        output.close()
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            self._status_var.set('In Zwischenablage kopiert')
            self._show_toast('✓  In Zwischenablage kopiert')
        except Exception as e:
            self._status_var.set(f'Clipboard-Fehler: {e}')
            self._show_toast(f'Clipboard-Fehler: {e}', is_error=True)
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

    def _clipboard_mac(self, img: Image.Image):
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                tmp_path = f.name
                img.save(f, 'PNG')
            safe_path = tmp_path.replace('\\', '\\\\').replace('"', '\\"')
            script = (
                'set the clipboard to '
                f'(read (POSIX file "{safe_path}") as «class PNGf»)'
            )
            subprocess.run(['osascript', '-e', script],
                           check=True, capture_output=True)
            os.unlink(tmp_path)
            self._status_var.set('In Zwischenablage kopiert')
            self._show_toast('✓  In Zwischenablage kopiert')
        except Exception as e:
            self._status_var.set(f'Clipboard-Fehler: {e}')
            self._show_toast(f'Clipboard-Fehler: {e}', is_error=True)

    # ------------------------------------------------------------------
    # Bild-Operationen: Resize, Watermark, Shadow, Border
    # ------------------------------------------------------------------

    def _push_undo(self, save_image: bool = False):
        """Aktuellen Zustand auf den Undo-Stack schieben."""
        img_copy = self.image.copy() if save_image else None
        self.undo_stack.append((deepcopy(self.annotations), img_copy))
        self.redo_stack.clear()

    def _offset_annotations(self, dx: int, dy: int):
        """Alle Annotations um (dx, dy) Pixel verschieben."""
        for ann in self.annotations:
            ann.x1     += dx
            ann.y1     += dy
            ann.x2     += dx
            ann.y2     += dy
            ann.tail_x += dx
            ann.tail_y += dy
            ann.points = [(px + dx, py + dy) for px, py in ann.points]

    def _finish_image_op(self, status_msg: str):
        """Canvas neu zeichnen und Undo-State aktualisieren."""
        self._redraw_canvas()
        self._update_undo_redo_state()
        self._status_var.set(status_msg)
        # Bildgröße-Label aktualisieren
        if hasattr(self, '_size_label'):
            iw, ih = self.image.size
            self._size_label.config(text=f'{iw} × {ih} px')

    def _resize_image(self):
        """Bild-Größe ändern über Dialog."""
        w, h = self.image.size
        result = simpledialog.askstring(
            'Größe ändern',
            f'Aktuelle Größe: {w} × {h}\n\n'
            'Neue Größe eingeben (Breite×Höhe oder Prozent):\n'
            'Beispiele: 800×600, 50%',
            parent=self.win)
        if not result:
            return
        result = result.strip()
        try:
            if '%' in result:
                pct = float(result.replace('%', '').strip()) / 100
                new_w, new_h = max(1, int(w * pct)), max(1, int(h * pct))
            elif '×' in result or 'x' in result.lower():
                parts = result.replace('×', 'x').lower().split('x')
                new_w, new_h = max(1, int(parts[0].strip())), max(1, int(parts[1].strip()))
            else:
                messagebox.showwarning('Ungültige Eingabe',
                    'Format: 800×600 oder 50%', parent=self.win)
                return
        except (ValueError, IndexError):
            messagebox.showwarning('Ungültige Eingabe',
                'Format: 800×600 oder 50%', parent=self.win)
            return

        self._push_undo(save_image=True)

        sx, sy = new_w / w, new_h / h
        scale = (sx + sy) / 2
        self.image = self.image.resize((new_w, new_h), Image.LANCZOS)

        for ann in self.annotations:
            ann.x1        = int(ann.x1 * sx)
            ann.y1        = int(ann.y1 * sy)
            ann.x2        = int(ann.x2 * sx)
            ann.y2        = int(ann.y2 * sy)
            ann.tail_x    = int(ann.tail_x * sx)
            ann.tail_y    = int(ann.tail_y * sy)
            ann.width     = max(1, int(ann.width * scale))
            ann.font_size = max(8, int(ann.font_size * scale))
            ann.points    = [(int(px * sx), int(py * sy))
                             for px, py in ann.points]

        self._finish_image_op(f'Größe geändert: {new_w} × {new_h}')

    def _add_watermark(self):
        """Text-Wasserzeichen auf das Bild legen."""
        text = simpledialog.askstring(
            'Wasserzeichen',
            'Wasserzeichen-Text eingeben:',
            initialvalue='© Mein Wasserzeichen',
            parent=self.win)
        if not text:
            return

        self._push_undo(save_image=True)

        overlay = Image.new('RGBA', self.image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font_size = max(14, self.image.width // 30)
        font = _get_truetype_font(font_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = max(4, self.image.width - tw - 16)
        y = max(4, self.image.height - th - 16)
        draw.rectangle([(x - 8, y - 4), (x + tw + 8, y + th + 4)],
                        fill=(0, 0, 0, 80))
        draw.text((x, y), text, fill=(255, 255, 255, 140), font=font)
        del draw

        base = self.image.convert('RGBA')
        self.image = Image.alpha_composite(base, overlay).convert('RGB')
        self._finish_image_op('Wasserzeichen hinzugefügt')

    def _add_shadow(self):
        """Drop-Shadow um das gesamte Bild hinzufügen."""
        self._push_undo(save_image=True)

        pad, off = 20, 6
        w, h = self.image.size
        new_w, new_h = w + pad * 2, h + pad * 2

        shadow = Image.new('L', (new_w, new_h), 0)
        shadow.paste(180, (pad + off, pad + off, pad + off + w, pad + off + h))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=pad // 2))

        result = Image.new('RGB', (new_w, new_h), (240, 240, 240))
        result = Image.composite(
            Image.new('RGB', (new_w, new_h), (0, 0, 0)), result, shadow)
        result.paste(self.image, (pad, pad))

        self._offset_annotations(pad, pad)
        self.image = result
        self._finish_image_op('Schatten hinzugefügt')

    def _add_border(self):
        """Farbigen Rahmen um das Bild hinzufügen."""
        result = simpledialog.askstring(
            'Rahmen hinzufügen',
            'Rahmenbreite in Pixel eingeben:',
            initialvalue='10',
            parent=self.win)
        if not result:
            return
        try:
            border_px = max(1, int(result.strip()))
        except ValueError:
            messagebox.showwarning('Ungültige Eingabe',
                'Bitte eine Zahl eingeben.', parent=self.win)
            return

        color = colorchooser.askcolor(
            title='Rahmenfarbe wählen', color='#1E293B',
            parent=self.win)
        if not color[1]:
            return
        hex_color = color[1]

        self._push_undo(save_image=True)
        self.image = ImageOps.expand(self.image, border=border_px,
                                      fill=hex_color)
        self._offset_annotations(border_px, border_px)
        self._finish_image_op(f'Rahmen ({border_px}px) hinzugefügt')

    # ------------------------------------------------------------------
    # Fenster schließen
    # ------------------------------------------------------------------

    def _on_close(self):
        self.win.destroy()
        self.app.on_editor_closed()


# ===========================================================================
# Spezielles Overlay für Scrolling (gibt Koordinaten zurück, kein Bild)
# ===========================================================================

class _ScrollingRegionOverlay:
    """Wie RegionOverlay, gibt aber Bildschirmkoordinaten zurück."""

    def __init__(self, root, callback):
        self.root     = root
        self.callback = callback
        self._start_x = self._start_y = 0
        self._cur_x   = self._cur_y   = 0

    def show(self):
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[0]
            raw = sct.grab(mon)
            self.background = Image.frombytes(
                'RGB', raw.size, raw.bgra, 'raw', 'BGRX')

        self.win = tk.Toplevel(self.root)
        self.win.attributes('-fullscreen', True)
        self.win.attributes('-topmost', True)
        self.win.configure(cursor='crosshair')

        self.canvas = tk.Canvas(self.win, highlightthickness=0,
                                cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)

        bg_dark = self.background.copy()
        r, g, b = bg_dark.split()
        bg_dark = Image.merge('RGB', tuple(
            c.point(lambda p: int(p * 0.5)) for c in (r, g, b)))
        self._bg_photo = ImageTk.PhotoImage(bg_dark)
        self.canvas.create_image(0, 0, anchor='nw', image=self._bg_photo)

        sw = self.win.winfo_screenwidth()
        self.canvas.create_text(
            sw // 2, 30,
            text='Scroll-Bereich auswählen (sichtbares Fenster)  |  ESC = Abbrechen',
            fill='#FFDD00', font=(FONT_FAMILY, 13))

        self.canvas.bind('<ButtonPress-1>',   self._on_down)
        self.canvas.bind('<B1-Motion>',        self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_up)
        self.win.bind('<Escape>', lambda e: self.win.destroy())

    def _on_down(self, e):
        self._start_x, self._start_y = e.x, e.y

    def _on_drag(self, e):
        self._cur_x, self._cur_y = e.x, e.y
        self._draw_sel()

    def _on_up(self, e):
        self._cur_x, self._cur_y = e.x, e.y
        x1, y1, x2, y2 = self._rect()
        if abs(x2 - x1) < 5 or abs(y2 - y1) < 5:
            return
        self.win.destroy()
        self.callback((x1, y1, x2, y2))

    def _rect(self):
        return (min(self._start_x, self._cur_x),
                min(self._start_y, self._cur_y),
                max(self._start_x, self._cur_x),
                max(self._start_y, self._cur_y))

    def _draw_sel(self):
        self.canvas.delete('sel')
        x1, y1, x2, y2 = self._rect()
        if x2 == x1 or y2 == y1:
            return
        region = self.background.crop((x1, y1, x2, y2))
        self._sel_photo = ImageTk.PhotoImage(region)
        self.canvas.create_image(x1, y1, anchor='nw',
                                 image=self._sel_photo, tag='sel')
        self.canvas.create_rectangle(x1, y1, x2, y2,
                                     outline='#FFDD00', width=2, tag='sel')
        lbl = f'{x2-x1} × {y2-y1} px'
        self.canvas.create_text(
            x1 + 4, y1 - 18 if y1 > 20 else y2 + 4,
            text=lbl, fill='#FFDD00',
            font=(FONT_FAMILY, 10, 'bold'), anchor='nw', tag='sel')


# ===========================================================================
# HAUPTANWENDUNG  –  ScreenshotApp
# ===========================================================================

class ScreenshotApp(_Theme):
    """Haupt-Controller: kleines Toolbar-Fenster + globale Hotkeys."""

    # Aliases für Rückwärtskompatibilität
    BG       = _Theme.BG_MAIN
    BG_TOP   = _Theme.BG_TOOLBAR
    ACCENT_H = _Theme.ACCENT_HOV

    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Screenshot-Tool')
        self._capturing    = False
        self._active_editor = None
        self._hotkey_listener = None
        self._timer_seconds = 0

        self.engine  = CaptureEngine()
        self.history = HistoryManager()

        self._build_ui()
        self._register_hotkeys()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.root.configure(bg=self.BG)
        self.root.geometry('820x72')
        self.root.minsize(780, 72)
        self.root.resizable(True, False)

        bar = tk.Frame(self.root, bg=self.BG_TOP,
                       highlightthickness=1,
                       highlightbackground=self.DIVIDER)
        bar.pack(fill='both', expand=True)

        # Logo
        logo_frame = tk.Frame(bar, bg=self.BG_TOP)
        logo_frame.pack(side='left', padx=(12, 8))
        tk.Label(logo_frame, text='📷', bg=self.BG_TOP, fg=self.ACCENT,
                 font=(FONT_FAMILY, 20)).pack(pady=(2, 0))
        tk.Label(logo_frame, text='Screenshot', bg=self.BG_TOP,
                 fg=self.FG_MUTED, font=(FONT_FAMILY, 7, 'bold')).pack()

        tk.Frame(bar, bg=self.DIVIDER, width=1).pack(
            side='left', fill='y', pady=10, padx=(0, 6))

        # Hotkey-Labels plattformabhängig
        if IS_MACOS:
            hotkeys = ['⌘⇧1', '⌘⇧F', '⌘⇧W', '⌘⇧S']
        else:
            hotkeys = ['Print Screen', 'Ctrl+Shift+F',
                       'Ctrl+Shift+W', 'Ctrl+Shift+S']

        # Capture-Buttons
        for (icon, label, _, cmd), hotkey in zip([
            ('✂',  'Region',    '', self.start_region),
            ('🖥',  'Vollbild',  '', self.start_fullscreen),
            ('🪟',  'Fenster',   '', self.start_window),
            ('📜',  'Scrolling', '', self.start_scrolling),
        ], hotkeys):
            cell = tk.Frame(bar, bg=self.BG_TOP)
            cell.pack(side='left', padx=2, pady=6)
            btn = tk.Button(cell, text=f'{icon}  {label}',
                            font=(FONT_FAMILY, 10),
                            bg=self.BTN_NORM, fg=self.BTN_FG,
                            activebackground=self.ACCENT,
                            activeforeground='white',
                            relief='flat', padx=12, pady=5, bd=0,
                            cursor='hand2', command=cmd)
            btn.pack()
            tk.Label(cell, text=hotkey, bg=self.BG_TOP, fg=self.FG_MUTED,
                     font=(FONT_FAMILY, 7)).pack()
            btn.bind('<Enter>',
                     lambda e, b=btn: b.config(bg=self.ACCENT, fg='white'))
            btn.bind('<Leave>',
                     lambda e, b=btn: b.config(bg=self.BTN_NORM,
                                               fg=self.BTN_FG))

        tk.Frame(bar, bg=self.DIVIDER, width=1).pack(
            side='left', fill='y', pady=10, padx=4)

        # Timer
        timer_cell = tk.Frame(bar, bg=self.BG_TOP)
        timer_cell.pack(side='left', padx=4, pady=6)
        tk.Label(timer_cell, text='⏱', bg=self.BG_TOP, fg=self.ACCENT,
                 font=(FONT_FAMILY, 10)).pack(side='left')
        self._timer_var = tk.StringVar(value='0s')
        timer_menu = tk.OptionMenu(timer_cell, self._timer_var,
                                   '0s', '3s', '5s', '10s',
                                   command=self._on_timer_change)
        timer_menu.config(font=(FONT_FAMILY, 9), bg=self.BTN_NORM,
                          fg=self.BTN_FG, relief='flat', bd=0,
                          highlightthickness=0)
        timer_menu.pack(side='left')

        tk.Frame(bar, bg=self.DIVIDER, width=1).pack(
            side='left', fill='y', pady=10, padx=4)

        # Status
        self._status_var = tk.StringVar(value='Bereit')
        status_row = tk.Frame(bar, bg=self.BG_TOP)
        status_row.pack(side='left', padx=6)
        tk.Label(status_row, text='●', bg=self.BG_TOP, fg=self.ACCENT,
                 font=(FONT_FAMILY, 7)).pack(side='left')
        tk.Label(status_row, textvariable=self._status_var,
                 bg=self.BG_TOP, fg=self.FG_MUTED,
                 font=(FONT_FAMILY, 8), width=18, anchor='w').pack(
                     side='left', padx=(3, 0))

        # Schließen-Button
        close_btn = tk.Button(bar, text='✕', font=(FONT_FAMILY, 11),
                              bg=self.BG_TOP, fg=self.FG_MUTED,
                              activebackground='#DC2626',
                              activeforeground='white',
                              relief='flat', padx=10, pady=4, bd=0,
                              cursor='hand2', command=self.root.quit)
        close_btn.pack(side='right', padx=8, pady=8)
        close_btn.bind('<Enter>',
                       lambda e: close_btn.config(bg='#DC2626', fg='white'))
        close_btn.bind('<Leave>',
                       lambda e: close_btn.config(bg=self.BG_TOP,
                                                   fg=self.FG_MUTED))
        self.root.protocol('WM_DELETE_WINDOW', self.root.quit)

    # ------------------------------------------------------------------
    # Hotkeys
    # ------------------------------------------------------------------

    def _register_hotkeys(self):
        if IS_WINDOWS:
            self._register_hotkeys_win()
        elif IS_MACOS:
            self._register_hotkeys_mac()

    def _register_hotkeys_win(self):
        try:
            import keyboard as kb
            kb.add_hotkey('print_screen',
                          lambda: self.root.after(0, self.start_region))
            kb.add_hotkey('ctrl+shift+f',
                          lambda: self.root.after(0, self.start_fullscreen))
            kb.add_hotkey('ctrl+shift+w',
                          lambda: self.root.after(0, self.start_window))
            kb.add_hotkey('ctrl+shift+s',
                          lambda: self.root.after(0, self.start_scrolling))
        except Exception as e:
            self._set_status(f'Hotkeys nicht verfügbar: {e}')

    def _register_hotkeys_mac(self):
        try:
            from pynput import keyboard as pynput_kb

            hotkeys = {
                '<cmd>+<shift>+1': lambda: self.root.after(0, self.start_region),
                '<cmd>+<shift>+f': lambda: self.root.after(0, self.start_fullscreen),
                '<cmd>+<shift>+w': lambda: self.root.after(0, self.start_window),
                '<cmd>+<shift>+s': lambda: self.root.after(0, self.start_scrolling),
            }
            self._hotkey_listener = pynput_kb.GlobalHotKeys(hotkeys)
            self._hotkey_listener.daemon = True
            self._hotkey_listener.start()
        except Exception as e:
            self._set_status(f'Hotkeys nicht verfügbar: {e}')

    # ------------------------------------------------------------------
    # Timer
    # ------------------------------------------------------------------

    def _on_timer_change(self, val: str):
        self._timer_seconds = int(val.replace('s', ''))

    def _start_with_timer(self, action_fn):
        """Startet einen Countdown und ruft dann action_fn auf."""
        delay = self._timer_seconds
        if delay <= 0:
            action_fn()
            return
        self._set_status(f'Timer: {delay}s …')
        self._countdown(delay, action_fn)

    def _countdown(self, remaining: int, action_fn):
        if remaining <= 0:
            action_fn()
            return
        self._set_status(f'Aufnahme in {remaining}s …')
        self.root.after(1000, lambda: self._countdown(remaining - 1, action_fn))

    # ------------------------------------------------------------------
    # Capture-Aktionen
    # ------------------------------------------------------------------

    def start_region(self):
        if self._capturing:
            return
        self._capturing = True
        self._start_with_timer(self._do_region_delayed)

    def _do_region_delayed(self):
        self._set_status('Region auswählen …')
        self.root.withdraw()
        self.root.after(150, self._do_region)

    def _do_region(self):
        overlay = RegionOverlay(self.root, self._on_captured)
        overlay.show()

    def start_fullscreen(self):
        if self._capturing:
            return
        self._capturing = True
        self._start_with_timer(self._do_fullscreen_delayed)

    def _do_fullscreen_delayed(self):
        self._set_status('Vollbild wird aufgenommen …')
        self.root.withdraw()
        self.root.after(300, self._do_fullscreen)

    def _do_fullscreen(self):
        try:
            self._on_captured(self.engine.capture_fullscreen())
        except Exception as e:
            self._capturing = False
            self._show_error(f'Vollbild-Fehler: {e}')

    def start_window(self):
        if self._capturing:
            return
        self._capturing = True
        self._start_with_timer(self._do_window_pick)

    def _do_window_pick(self):
        result = WindowPickerDialog(self.root).show()
        if result is None:
            self._capturing = False
            return
        wid, title = result
        self._set_status(f'Fenster wird aufgenommen: {title}')
        self.root.withdraw()
        self.root.after(300, lambda: self._do_window(wid))

    def _do_window(self, wid):
        try:
            self._on_captured(self.engine.capture_window(wid))
        except Exception as e:
            self._capturing = False
            self._show_error(f'Fenster-Fehler: {e}')

    def start_scrolling(self):
        if self._capturing:
            return
        self._capturing = True
        self._start_with_timer(self._do_scrolling_delayed)

    def _do_scrolling_delayed(self):
        self._set_status('Region für Scrolling auswählen …')
        self.root.withdraw()
        self.root.after(200, self._do_scrolling_pick)

    def _do_scrolling_pick(self):
        _ScrollingRegionOverlay(self.root, self._on_scroll_region).show()

    def _on_scroll_region(self, region: tuple):
        self._set_status('Scrolling Capture läuft … bitte warten')
        self.root.after(100, lambda: self._do_scrolling(region))

    def _do_scrolling(self, region):
        try:
            self._on_captured(self.engine.capture_scrolling(region))
        except Exception as e:
            self._capturing = False
            self._show_error(f'Scrolling-Fehler: {e}')

    # ------------------------------------------------------------------
    # Nach erfolgreichem Capture
    # ------------------------------------------------------------------

    def _on_captured(self, image):
        self._capturing = False
        self.root.deiconify()
        self._set_status('Bereit')

        entry    = self.history.add(image)
        entry_id = entry['id']

        if (self._active_editor
                and self._active_editor.win
                and self._active_editor.win.winfo_exists()):
            self._active_editor.load_image(image, entry_id=entry_id)
        else:
            self._active_editor = AnnotationEditor(
                self.root, image, self, self.history)
            self._active_editor.show(entry_id=entry_id)

    def on_editor_closed(self):
        self._active_editor = None
        self._set_status('Bereit')

    # ------------------------------------------------------------------
    def _set_status(self, msg: str):
        self._status_var.set(msg)
        self.root.update_idletasks()

    def _show_error(self, msg: str):
        self.root.deiconify()
        self._set_status('Fehler')
        messagebox.showerror('Fehler', msg, parent=self.root)

    def run(self):
        self.root.mainloop()


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == '__main__':
    if not check_dependencies():
        sys.exit(1)
    ScreenshotApp().run()
