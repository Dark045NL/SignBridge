# SignBridge
NGT Gebarentaal → Live Transcriptie | Zuyd Hogeschool

## Installatie
```bash
pip install opencv-python mediapipe numpy
pip install pywin32        # Windows spraak
```

## Starten
```bash
cd App && python SignBridge.py
```

## Structuur
```
App/
├── SignBridge.py          # hoofdlus        ~150 regels
├── ui.py                  # tekenfuncties   ~275 regels
├── tts.py                 # spraak          ~85  regels
├── gebaren_classifier.py  # herkenning      ~365 regels
└── gebaren/               # 25 PNG kaartjes
```

## Bediening
| Toets | Actie |
|-------|-------|
| F | fullscreen toggle |
| G / ESC | gebaren-referentie |
| N / P | navigeer gebaren |
| + / - | delay aanpassen |
| M | spraak aan/uit |
| BACKSPACE | wis woord |
| C | wis alles |
| Q | afsluiten |
