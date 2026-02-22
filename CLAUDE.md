# Screenshot Tool -- Projektkontext fuer Claude Code

## Projektstruktur

```
screenshot-tool/
  screenshot_tool.py    -- Gesamte Anwendung (~2.937 Zeilen, ~120 KB)
  requirements.txt      -- Dependencies (plattformspezifisch)
  start.pyw             -- Windows-Starter (ohne Konsole)
  README.md             -- Vollstaendige Dokumentation
  CLAUDE.md             -- Diese Datei (Projektkontext)
  history/              -- Laufzeitdaten (gitignored)
    index.json
    img_*.png / orig_*.png / thumb_*.png
```

## Coding-Konventionen

- **Sprache:** UI-Texte und Kommentare auf Deutsch
- **Single-File:** Alles in `screenshot_tool.py` -- kein Modul-Split (bewusste Entscheidung fuer einfache Distribution)
- **GUI:** tkinter + ttk mit `clam`-Theme. Kein PyQt, kein Electron
- **Plattform-Guards:** `IS_WINDOWS` / `IS_MACOS` Flags (Zeile 40-41). Neuer plattformspezifischer Code MUSS diese Guards verwenden
- **Dataclass:** `Annotation` ist ein `@dataclass` (Zeile 717). Neue Annotation-Typen hier als Felder ergaenzen
- **Theme:** Alle Farben in `_Theme` Klasse (Zeile 694-713). Keine hardcoded Farben in Methoden
- **Font:** `FONT_FAMILY` global definiert (Segoe UI / Helvetica Neue)
- **Undo:** Max 40 Eintraege (`MAX_UNDO`). `_push_undo(save_image=True)` vor destruktiven Aenderungen aufrufen
- **History:** Max 25 Eintraege (`MAX_ENTRIES`). Atomare Schreibvorgaenge mit `os.replace()`

## Architektur-Entscheidungen

### Responsive Toolbar (Flow-Layout)
Die Toolbar nutzt `place()`-Geometrie mit automatischem Zeilenumbruch (`_reflow_row`).
Ein `_reflow_guard` Flag verhindert Endlos-Rekursion (Configure -> Hoehenaenderung -> Configure).
ttk-Buttons haben `width=2` und `padding=(2,3)` fuer kompakte Darstellung (28px statt 124px).

### HistoryManager
- `index.json` wird atomar geschrieben (temp-Datei + `os.replace`)
- Original-Bilder (`orig_*`) separat von bearbeiteten (`img_*`) gespeichert
- Thumbnails (`thumb_*`, 120x80) fuer Filmstrip-Anzeige

### Annotation-System
- Alle Annotationen als `Annotation`-Dataclass-Instanzen in `self.annotations: list[Annotation]`
- Hit-Testing ueber `_hit_test()` fuer Select/Move
- Render-Pipeline: `_apply_annotation()` zeichnet auf PIL-Image, `_draw_annotation_on_canvas()` zeichnet auf tkinter-Canvas
- Canvas und PIL-Koordinaten muessen synchron bleiben (Canvas hat Scroll-Offset)

### Plattform-Abstraktion
- Hotkeys: `keyboard` (Win) vs `pynput` (macOS)
- Fenster-Capture: `ctypes.windll` (Win) vs `Quartz` (macOS)
- Clipboard: `win32clipboard` (Win) vs `osascript` (macOS)
- Rechtsklick: `<Button-3>` (Win) vs `<Button-2>` (macOS)

## Klassen-Uebersicht (Reihenfolge im Code)

1. **HistoryManager** (Z.144) -- Verlaufsverwaltung, JSON-Index, Datei-I/O
2. **RegionOverlay** (Z.323) -- Transparentes Overlay fuer Region-Auswahl
3. **WindowPickerDialog** (Z.429) -- Dialog zur Fenster-Auswahl
4. **CaptureEngine** (Z.519) -- Screenshot-Logik (Region, Vollbild, Fenster, Scroll)
5. **_Theme** (Z.694) -- Farbkonstanten
6. **Annotation** (Z.717) -- Dataclass fuer eine einzelne Annotation
7. **AnnotationEditor** (Z.734) -- Haupt-Editor, laengste Klasse (~1.800 Zeilen)
8. **_ScrollingRegionOverlay** (Z.2530) -- Scrolling-Capture Overlay
9. **ScreenshotApp** (Z.2617) -- Einstiegspunkt, Tray-Icon, Hotkey-Registration

## Offene Issues (aus Code Review, priorisiert)

### Kritisch
- **Thread-Safety:** `RegionOverlay` und `CaptureEngine` rufen tkinter-Methoden aus Background-Threads auf. Muss auf `root.after()`-Callbacks umgestellt werden, da tkinter nicht thread-safe ist.
- **Scrolling Capture:** Braucht robustere Abbruch-Erkennung und Duplikat-Frame-Handling.

### Wichtig
- **Unit-Tests fehlen:** Mindestens HistoryManager und Annotation-Logik mit pytest testen.
- **Konfigurationsdatei:** Benutzereinstellungen (Hotkeys, Speicherpfad, Farben) sollten in JSON/TOML persistiert werden statt hardcoded.
- **Tooltip-Timer:** Aktuell erscheinen Tooltips sofort -- besser mit `after(500)` Verzoegerung.

### Nice-to-have
- Code in Module aufteilen (editor, capture, history, theme)
- Logging statt `print()` fuer Fehler
- Dark Mode
- Anpassbare Hotkeys ueber Settings-Dialog

## Haeufige Aufgaben

### Neues Annotation-Tool hinzufuegen
1. Eintrag in `TOOLS`-Liste (Zeile 737-751) ergaenzen
2. `_make_annotation()` um neuen Typ erweitern
3. `_draw_annotation_on_canvas()` um Canvas-Rendering erweitern
4. `_apply_annotation()` um PIL-Rendering erweitern
5. Optional: `_hit_test()` fuer Select/Move anpassen

### Neuen Hotkey hinzufuegen
1. In `_build_editor()` bei den `bind()`-Aufrufen (Zeile ~1601-1612)
2. Plattform-Guard beachten: `Cmd` (macOS) vs `Ctrl` (Windows)
3. Menu-Accelerator in `_build_menus()` synchron halten

### Neues Bild-Feature hinzufuegen (Menu "Bild")
1. Menu-Eintrag in `_build_menus()` (Zeile ~1045-1052)
2. Methode in `AnnotationEditor` implementieren
3. `_push_undo(save_image=True)` VOR der Bildaenderung aufrufen
4. `_redraw_canvas()` nach der Aenderung aufrufen
