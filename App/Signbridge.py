"""
SignBridge: NGT Gebarentaal → Tekst
Zuyd Hogeschool | Lectoraat Data Intelligence
=============================================


    pip install opencv-python mediapipe numpy

Gebruik:
    python SignBridge.py

    Q = afsluiten
    BACKSPACE = wis laatste woord
    C = wis hele transcriptie

NGT-woordenlijst (25 gebaren):
    HALLO, DAG, TOT_ZIENS, BEDANKT, GRAAG_GEDAAN,
    JA, NEE, HELP, STOP, GOED, SLECHT, MEER, MINDER,
    IK, JIJ, WIJ, NAAM, SCHOOL, LEREN, WERKEN,
    WATER, EEN, TWEE, DRIE, VRAAG
"""

import sys
import cv2
import numpy as np
import time
import textwrap
from collections import deque, Counter
from signs.features      import get_lm, finger_states, norm_lm, tip_dist, palm_open, wrist_angle
from signs.groeten       import SIGNS as _GROETEN
from signs.basiswoorden  import SIGNS as _BASISWOORDEN
from signs.kwaliteit     import SIGNS as _KWALITEIT
from signs.voornaamwoorden import SIGNS as _VOORNAAMWOORDEN
from signs.context       import SIGNS as _CONTEXT
from signs.getallen      import SIGNS as _GETALLEN
from signs.overig        import SIGNS as _OVERIG

_ALL_SIGNS = (
    _GROETEN + _BASISWOORDEN + _KWALITEIT + _VOORNAAMWOORDEN
    + _CONTEXT + _GETALLEN + _OVERIG
)


def classify_ngt(hl):
    lm  = get_lm(hl)
    f   = finger_states(lm)
    th, ix, mi, ri, pi = f
    def td(i, j): return tip_dist(lm, i, j)
    po  = palm_open(lm)
    wa  = wrist_angle(lm)
    nlm = norm_lm(lm)
    kwargs = dict(lm=lm, th=th, ix=ix, mi=mi, ri=ri, pi=pi,
                  td=td, po=po, wa=wa, nlm=nlm)
    for check_fn in _ALL_SIGNS:
        result = check_fn(**kwargs)
        if result:
            return result
    return None

# ── MediaPipe – compatibel met 0.8 t/m 0.10 ──────────────────────────────────
try:
    import mediapipe as mp
    # Probeer de klassieke solutions-API (0.8/0.9/vroeg-0.10)
    _hands_mod  = mp.solutions.hands
    _draw_mod   = mp.solutions.drawing_utils
    _styles_mod = mp.solutions.drawing_styles
    _NEW_API    = False
except AttributeError:
    # Nieuwe 0.10+ API zonder mp.solutions
    _NEW_API = True
    try:
        from mediapipe.python.solutions import hands as _hands_mod
        from mediapipe.python.solutions import drawing_utils  as _draw_mod
        from mediapipe.python.solutions import drawing_styles as _styles_mod
    except ImportError:
        print("\n[FOUT] Kan MediaPipe niet laden.")
        print("Probeer: pip install mediapipe==0.10.9\n")
        sys.exit(1)

mp_hands  = _hands_mod
mp_draw   = _draw_mod
mp_styles = _styles_mod

# ── Palet (BGR) ───────────────────────────────────────────────────────────────
WHITE      = (255, 255, 255)
GREEN      = (60,  210, 90 )
ORANGE     = (0,   165, 255)
ZUYD_RED   = (30,  30,  200)
DARK       = (22,  22,  28 )
PANEL_BG   = (18,  18,  28 )
HEADER_BG  = (14,  14,  22 )
GRAY       = (65,  65,  65 )
LGRAY      = (155, 155, 155)
ACCENT     = (90,  185, 255)
WORD_COLOR = (120, 230, 120)

# ── Layout ────────────────────────────────────────────────────────────────────
CAM_W    = 780
CAM_H    = 580
PANEL_W  = 400
WIN_W    = CAM_W + PANEL_W
WIN_H    = CAM_H
HEADER_H = 56
FONT     = cv2.FONT_HERSHEY_SIMPLEX

# ── Timing ────────────────────────────────────────────────────────────────────
STABIEL_FRAMES  = 20
STABIEL_DREMPEL = 0.62
PAUZE_SECONDEN  = 1.4
COOLDOWN        = 1.5


# ══════════════════════════════════════════════════════════════════════════════
#  Smoothing buffer
# ══════════════════════════════════════════════════════════════════════════════

class GestureBuffer:
    def __init__(self, size=STABIEL_FRAMES):
        self.buf = deque(maxlen=size)

    def update(self, g):
        self.buf.append(g)

    def stable(self):
        valid = [g for g in self.buf if g is not None]
        if not valid or len(self.buf) < self.buf.maxlen // 2:
            return None, 0.0
        best, freq = Counter(valid).most_common(1)[0]
        conf = freq / len(self.buf)
        return (best, conf) if conf >= STABIEL_DREMPEL else (None, conf)


# ══════════════════════════════════════════════════════════════════════════════
#  Camera-paneel
# ══════════════════════════════════════════════════════════════════════════════

def draw_conf_bar(img, x, y, w, h, value):
    cv2.rectangle(img, (x, y), (x+w, y+h), GRAY, -1)
    fill  = int(w * np.clip(value, 0, 1))
    color = GREEN if value >= STABIEL_DREMPEL else ORANGE
    if fill > 0:
        cv2.rectangle(img, (x, y), (x+fill, y+h), color, -1)
    cv2.rectangle(img, (x, y), (x+w, y+h), LGRAY, 1)

def draw_camera_panel(cam, detected, stable, conf, fps, hand_count, last_word):
    h, w = cam.shape[:2]
    cv2.rectangle(cam, (0, HEADER_H), (w, HEADER_H+26), (20,20,24), -1)
    cv2.putText(cam, "Camera  &  Detectie",   (14, HEADER_H+18), FONT, 0.58, LGRAY, 1)
    cv2.putText(cam, f"FPS {fps:.0f}",        (w-78, HEADER_H+18), FONT, 0.50, LGRAY, 1)

    show  = stable if stable else (detected or "-")
    color = GREEN if stable else (ORANGE if detected else LGRAY)
    fs    = 1.4 if len(show) > 6 else (2.2 if len(show) > 3 else 3.0)
    tw    = cv2.getTextSize(show, FONT, fs, 3)[0][0]
    th2   = cv2.getTextSize(show, FONT, fs, 3)[0][1]
    cv2.putText(cam, show, (w - tw - 12, HEADER_H + 26 + th2 + 18), FONT, fs, color, 3)
    sub = "STABIEL" if stable else ("detecteren..." if detected else "geen gebaar")
    cv2.putText(cam, sub, (w-170, HEADER_H+26+th2+46), FONT, 0.44, color, 1)

    sc = GREEN if hand_count else ZUYD_RED
    st = f"{hand_count} hand gevonden" if hand_count else "Geen hand zichtbaar"
    cv2.putText(cam, st,           (14, h-118), FONT, 0.50, sc,   1)
    cv2.putText(cam, "Zekerheid",  (14, h-96),  FONT, 0.40, LGRAY, 1)
    draw_conf_bar(cam, 14, h-86, 200, 11, conf)
    if last_word:
        cv2.putText(cam, f"Herkend: {last_word}", (14, h-62), FONT, 0.52, WORD_COLOR, 1)
    cv2.putText(cam, "Q=stop  BACKSPACE=wis woord  C=wis alles",
                (14, h-18), FONT, 0.37, (85,85,85), 1)


# ══════════════════════════════════════════════════════════════════════════════
#  Transcriptie-paneel
# ══════════════════════════════════════════════════════════════════════════════

LINE_H = 22
PAD    = 14

def wrap_words(words, max_w, fs=0.62):
    lines  = []
    line   = []
    line_w = 0
    for wd in words:
        tw = cv2.getTextSize(wd + " ", FONT, fs, 1)[0][0]
        if line_w + tw > max_w - PAD*2 and line:
            lines.append(" ".join(line))
            line   = [wd]
            line_w = tw
        else:
            line.append(wd)
            line_w += tw
    if line:
        lines.append(" ".join(line))
    return lines

def draw_transcript_panel(words, active_word, pw, ph):
    panel = np.full((ph, pw, 3), PANEL_BG, dtype=np.uint8)
    cv2.rectangle(panel, (0, HEADER_H), (pw, HEADER_H+26), (20,20,24), -1)
    cv2.putText(panel, "Live Transcriptie", (14, HEADER_H+18), FONT, 0.60, LGRAY, 1)
    cv2.line(panel, (0, HEADER_H+26), (pw, HEADER_H+26), GRAY, 1)

    all_words = words + ([f"[{active_word}]"] if active_word else [])
    lines     = wrap_words(all_words, pw) if all_words else []

    y     = HEADER_H + 26 + LINE_H + 8
    max_y = ph - 60
    for line in lines:
        if y > max_y:
            break
        is_last = (line == lines[-1]) and active_word
        color   = ACCENT if is_last else WHITE
        cv2.putText(panel, line, (PAD, y), FONT, 0.62, color, 1, cv2.LINE_AA)
        y += LINE_H

    if lines and int(time.time() * 2) % 2 == 0:
        cx = PAD + cv2.getTextSize(lines[-1], FONT, 0.62, 1)[0][0] + 2
        cv2.putText(panel, "|", (cx, y - LINE_H), FONT, 0.62, ACCENT, 1)

    cv2.line(panel, (0, ph-44), (pw, ph-44), GRAY, 1)
    cv2.putText(panel, f"{len(words)} woorden herkend", (PAD, ph-24), FONT, 0.42, LGRAY, 1)
    cv2.putText(panel, "Haal hand weg voor spatie",     (PAD, ph-6),  FONT, 0.37, (80,80,80), 1)
    return panel


# ══════════════════════════════════════════════════════════════════════════════
#  Hoofdlus
# ══════════════════════════════════════════════════════════════════════════════

def main():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)

    buf         = GestureBuffer()
    words       = []
    last_word   = ""
    last_add_t  = 0.0
    last_hand_t = time.time()
    space_given = False
    prev_t      = time.time()

    print("\n  SignBridge — NGT Gebarentaal naar Tekst")
    print("  Zuyd Hogeschool | Lectoraat Data Intelligence")
    print("  Q=stop | BACKSPACE=wis woord | C=wis alles\n")

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.70,
        min_tracking_confidence=0.60,
    ) as hands:

        while True:
            ret, raw = cap.read()
            if not ret:
                break

            frame = cv2.flip(raw, 1)
            frame = cv2.resize(frame, (CAM_W, CAM_H))
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res   = hands.process(rgb)

            detected = None; stable = None; conf = 0.0; hand_count = 0
            now = time.time()

            if res.multi_hand_landmarks:
                hand_count  = 1
                hl          = res.multi_hand_landmarks[0]
                last_hand_t = now
                space_given = False

                # Skeleton tekenen
                mp_draw.draw_landmarks(
                    frame, hl,
                    mp_hands.HAND_CONNECTIONS,
                    mp_styles.get_default_hand_landmarks_style(),
                    mp_styles.get_default_hand_connections_style(),
                )
                detected = classify_ngt(hl)

            buf.update(detected)
            stable, conf = buf.stable()

            # Woord toevoegen
            if stable and stable != last_word and now - last_add_t > COOLDOWN:
                words.append(stable)
                last_word  = stable
                last_add_t = now
                print(f"  + {stable}  →  {' '.join(w for w in words if w != ' ')}")

            # Automatische spatie na pauze
            if (not hand_count
                    and now - last_hand_t > PAUZE_SECONDEN
                    and not space_given
                    and words
                    and words[-1] != " "):
                words.append(" ")
                space_given = True
                last_word   = ""

            fps    = 1.0 / (now - prev_t + 1e-6)
            prev_t = now

            # Panelen tekenen
            active = stable if stable else detected
            draw_camera_panel(frame, detected, stable, conf, fps, hand_count, last_word)
            display_words = [w for w in words if w != " "]
            transcript = draw_transcript_panel(
                display_words,
                active if (active and active != last_word) else None,
                PANEL_W, CAM_H
            )

            combined = np.hstack([frame, transcript])

            # Globale header
            cv2.rectangle(combined, (0, 0), (WIN_W, HEADER_H), HEADER_BG, -1)
            cv2.putText(combined,
                "SignBridge  |  NGT Gebarentaal naar Tekst  |  Zuyd Hogeschool",
                (14, 37), FONT, 0.63, WHITE, 2)
            cv2.line(combined, (0, HEADER_H), (WIN_W, HEADER_H), GRAY, 1)
            cv2.line(combined, (CAM_W, 0),    (CAM_W, WIN_H),    GRAY, 2)

            cv2.imshow("SignBridge — Zuyd Hogeschool", combined)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            elif key == 8:   # BACKSPACE
                while words and words[-1] == " ":
                    words.pop()
                if words:
                    print(f"  - '{words.pop()}' verwijderd")
                last_word = words[-1] if words else ""
            elif key == ord("c"):
                words = []; last_word = ""
                print("  Transcriptie gewist.")

    cap.release()
    cv2.destroyAllWindows()
    clean = " ".join(w for w in words if w != " ")
    print(f"\n  Eindtranscriptie: '{clean}'")


if __name__ == "__main__":
    main()