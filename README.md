# Screenshot Tool

Ein professionelles Screenshot- und Annotations-Tool mit integriertem Editor, Verlaufsmanagement und Export-Funktionen. Entwickelt in Python mit tkinter/ttk.

> **Plattformen:** macOS und Windows

---

## Features

### Screenshot-Aufnahme
| Modus | macOS | Windows |
|-------|-------|---------|
| Region auswahlen | `Cmd+Shift+1` | `Print Screen` |
| Vollbild | `Cmd+Shift+F` | `Ctrl+Shift+F` |
| Fenster auswahlen | `Cmd+Shift+W` | `Ctrl+Shift+W` |
| Scrolling Capture | `Cmd+Shift+S` | `Ctrl+Shift+S` |

### 13 Annotations-Tools

| # | Tool | Symbol | Beschreibung |
|---|------|--------|-------------|
| 1 | Select | `+` | Auswahl / Verschieben von Annotationen |
| 2 | Pfeil | `->` | Pfeile zeichnen |
| 3 | Linie | `/` | Gerade Linien |
| 4 | Rechteck | `[]` | Rechtecke / Rahmen |
| 5 | Text | `T` | Textfelder einfugen |
| 6 | Callout | `...` | Sprechblasen mit Pfeil |
| 7 | Markierung | `#` | Halbtransparente Hervorhebung |
| 8 | Weichzeichner | `~` | Bereiche unscharf machen |
| 9 | Schwarzung | `X` | Bereiche komplett schwarzen |
| 10 | Ellipse | `O` | Kreise / Ellipsen |
| 11 | Freihand | `*` | Freies Zeichnen |
| 12 | Schritt | `1` | Nummerierte Markierungen |
| 13 | Zuschneiden | `[]` | Bild zuschneiden |

### Editor-Funktionen
- **Drag & Move** -- Annotationen per Select-Tool verschieben
- **Undo/Redo** -- Bis zu 40 Schritte ruckgangig machen (`Cmd/Ctrl+Z`, `Cmd/Ctrl+Y`)
- **Farb-/Breiten-/Schriftgrosse-Auswahl** -- Live-Anpassung uber Toolbar
- **Responsive Toolbar** -- Automatischer Zeilenumbruch bei schmalen Fenstern (Flow-Layout)

### Bildbearbeitung (Menu "Bild")
- Grosse andern (Resize mit Seitenverhaltnis)
- Wasserzeichen einfugen
- Schatten hinzufugen
- Rahmen hinzufugen

### Filmstrip (Verlauf)
- Thumbnail-Leiste am unteren Rand mit Paginierung (30 pro Seite)
- Typ-Badges: PNG (grun), JPG (orange), PDF (rot)
- Bearbeitungs-Indikator fur geanderte Bilder
- Rechtsklick-Kontextmenu: Offnen, Original laden, im Finder zeigen, Loschen
- Speicherpfad-Anzeige

### Original-Erhaltung
- Originalbild wird automatisch separat gespeichert
- Jederzeit wiederherstellbar uber `Bearbeiten > Original laden` (`Cmd/Ctrl+Shift+O`)

### Export
- **Speichern als** PNG, JPG oder PDF (`Cmd/Ctrl+S`)
- **Quick-Save** -- Schnellspeicher-Buttons in der Export-Leiste
- **Zwischenablage** -- Direkt kopieren (`Cmd/Ctrl+C`)
- Konfigurierbares Speicherverzeichnis

---

## Installation

### Voraussetzungen
- Python 3.9+ empfohlen
- pip (Python Package Manager)

### macOS

```bash
git clone https://github.com/fabianSp77/screenshot-tool.git
cd screenshot-tool
pip install -r requirements.txt
python screenshot_tool.py
```

> **Hinweis:** Beim ersten Start muss die App in den Systemeinstellungen unter
> `Datenschutz & Sicherheit > Bedienungshilfen` und `Bildschirmaufnahme`
> zugelassen werden.

### Windows

```bash
git clone https://github.com/fabianSp77/screenshot-tool.git
cd screenshot-tool
pip install -r requirements.txt
```

Starten uber:
```bash
python screenshot_tool.py
```

Oder per Doppelklick auf `start.pyw` (startet ohne Konsolenfenster).

### Dependencies

| Paket | Plattform | Zweck |
|-------|-----------|-------|
| Pillow | Alle | Bildverarbeitung |
| mss | Alle | Screenshot-Capture |
| pyautogui | Alle | Maus/Tastatur-Automation |
| numpy | Alle | Bildberechnungen |
| pywin32 | Windows | Win32 API (Clipboard, Fenster) |
| keyboard | Windows | Globale Hotkeys |
| pyobjc-framework-Quartz | macOS | Core Graphics (Fenster-Capture) |
| pynput | macOS | Tastatur-/Maus-Listener |

---

## Benutzung

### Schnellstart
1. App starten -- ein Tray-/Timer-Fenster erscheint
2. Hotkey drucken (z.B. `Cmd+Shift+1` auf macOS) fur Region-Auswahl
3. Bereich auswahlen -- Editor offnet sich automatisch
4. Annotationen hinzufugen, bearbeiten, verschieben
5. Speichern oder in die Zwischenablage kopieren

### Editor-Shortcuts

| Shortcut | Aktion |
|----------|--------|
| `Cmd/Ctrl+Z` | Ruckgangig |
| `Cmd/Ctrl+Y` | Wiederholen |
| `Cmd/Ctrl+S` | Speichern unter |
| `Cmd/Ctrl+C` | In Zwischenablage |
| `Cmd/Ctrl+Shift+O` | Original wiederherstellen |
| `1` - `9`, `0` | Tool direkt wahlen |
| Rechtsklick auf Annotation | Kontextmenu (Loschen) |
| Rechtsklick auf Filmstrip | Kontextmenu (Offnen, Original, Loschen) |

---

## Architektur

### Single-File-Design
Die gesamte Anwendung befindet sich in einer einzigen Datei `screenshot_tool.py` (~2.937 Zeilen, ~120 KB). Dies vereinfacht die Distribution und das Deployment.

### Klassen-Ubersicht

| Klasse | Zeilen (ca.) | Aufgabe |
|--------|-------------|---------|
| `HistoryManager` | 144-316 | Verlaufsverwaltung mit JSON-Index + Dateien |
| `RegionOverlay` | 323-427 | Region-Auswahl-Overlay |
| `WindowPickerDialog` | 429-517 | Fenster-Auswahl-Dialog |
| `CaptureEngine` | 519-690 | Screenshot-Aufnahme (Region, Vollbild, Fenster, Scroll) |
| `_Theme` | 694-713 | Farbschema-Konstanten |
| `Annotation` | 717-731 | Dataclass fur Annotation-Daten |
| `AnnotationEditor` | 734-2525 | Haupt-Editor mit UI, Tools, Export |
| `_ScrollingRegionOverlay` | 2530-2615 | Scrolling-Capture Overlay |
| `ScreenshotApp` | 2617-2937 | App-Hauptklasse, Tray, Hotkeys |

### Plattform-Abstraktion
- `IS_WINDOWS` / `IS_MACOS` Flags steuern plattformspezifischen Code
- Separate Implementierungen fur: Hotkeys, Fenster-Capture, Zwischenablage, Fonts, DPI-Handling
- Bedingte Dependencies in `requirements.txt` (`; sys_platform == "..."`)

### Daten-Speicherung (HistoryManager)
```
history/
  index.json          -- Manifest aller Eintrage (atomare Schreibvorgange)
  img_TIMESTAMP.png   -- Bearbeitetes Bild
  orig_TIMESTAMP.png  -- Original (unverandert)
  thumb_TIMESTAMP.png -- Thumbnail (120x80)
```

---

## Bekannte Einschrankungen

- **Scrolling Capture:** Funktioniert nur fur vertikales Scrollen; komplexe Layouts (z.B. parallax) konnen zu Artefakten fuhren
- **Fenster-Capture macOS:** Benotigt Bildschirmaufnahme-Berechtigung
- **Single-File:** Bei ~3.000 Zeilen wird die Datei gross -- ein Refactoring in Module ist fur die Zukunft sinnvoll
- **Keine Tests:** Unit-Tests fehlen noch

## Offene TODOs

> Aus dem Code Review -- priorisiert:

### Hoch
- [ ] Thread-Safety: `RegionOverlay` und `CaptureEngine` nutzen Tkinter aus Background-Threads -- auf `after()`-Callbacks umstellen
- [ ] Scrolling Capture robust machen (Abbruch-Erkennung, Duplikat-Frames)

### Mittel
- [ ] Unit-Tests einfuhren (pytest) fur HistoryManager, Annotation-Logik
- [ ] Konfigurationsdatei fur Benutzereinstellungen (JSON/TOML)
- [ ] Tooltip-Timer mit `after()` statt sofortiger Anzeige
- [ ] Anpassbare Hotkeys

### Niedrig
- [ ] Code in Module aufteilen (`editor.py`, `capture.py`, `history.py`, `ui_theme.py`)
- [ ] Logging statt `print()` fur Fehlerbehandlung
- [ ] Dark Mode Support

---

## Weiterentwicklung

Das Projekt nutzt eine `CLAUDE.md` Datei, die automatisch von Claude Code gelesen wird. Sie enthalt Projektkontext, Konventionen und offene Issues -- ideal fur KI-gestutzte Weiterentwicklung.

```bash
# Mit Claude Code weiterarbeiten:
cd screenshot-tool
claude
# Claude liest automatisch CLAUDE.md und kennt das Projekt
```

---

## Lizenz

Dieses Projekt ist derzeit ohne explizite Lizenz. Bitte vor offentlicher Nutzung eine Lizenz hinzufugen.

---

## Mitwirkende

- **Daniel** -- Ursprungliches Windows-Tool
- **Fabian** -- Cross-Platform-Erweiterung, Editor-Features, Code Review (mit Claude Code)
