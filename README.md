# SignBridge
**NGT Gebarentaal → Live Transcriptie**
Zuyd Hogeschool | Lectoraat Data Intelligence

## Installatie
```bash
pip install -r requirements.txt
```

## Starten
```bash
cd App
python SignBridge.py
```

## TTS (spraak)
- **Windows**: `pip install pywin32`  ← beste optie, gebruikt Windows SAPI
- **macOS**: werkt automatisch via `say`
- **Linux**: `sudo apt install espeak`
- Fallback: `pip install pyttsx3`

## Bediening
| Toets | Actie |
|-------|-------|
| `F` | fullscreen toggle |
| `G` / `ESC` | gebarenreferentie aan/uit |
| `N` / `P` | volgend / vorig gebaar |
| `+` / `-` | delay verhogen / verlagen |
| `M` | spraak aan/uit |
| `BACKSPACE` | wis laatste woord |
| `C` | wis transcriptie |
| `Q` | afsluiten |
