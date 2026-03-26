"""
SignBridge – NGT Gebarentaal → Live Transcriptie
Zuyd Hogeschool | Lectoraat Data Intelligence
=================================================

Projectstructuur:
    SignBridge.py           ← dit bestand  (UI + hoofdlus)
    gebaren_classifier.py   ← NGT gebaar-herkenning (25 woorden)
    gebaren/                ← PNG uitlegkaartjes per gebaar

Vereisten:
    pip install opencv-python mediapipe numpy pyttsx3

Gebruik:
    cd App && python SignBridge.py

Bediening:
    G / ESC    = gebarenreferentie aan/uit
    N / P      = volgend / vorig gebaar
    + / -      = delay verhogen / verlagen
    M          = spraak aan/uit
    BACKSPACE  = wis laatste woord
    C          = wis transcriptie
    Q / F      = fullscreen toggle / afsluiten
"""

import sys, os, glob, time, threading, queue
import cv2
import numpy as np

# ── Eigen module ──────────────────────────────────────────────────────────────
try:
    from gebaren_classifier import classify_ngt, MultiHandBuffer, WOORDENLIJST
except ImportError:
    print("\n[FOUT] gebaren_classifier.py niet gevonden.")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
#  TTS – robuuste implementatie voor Windows, macOS en Linux
#
#  Windows: win32com.client (SAPI) – meest betrouwbaar, geen COM-problemen
#  macOS:   subprocess met 'say'
#  Linux:   subprocess met 'espeak'
#  Fallback: pyttsx3 met nieuwe engine PER woord (langzamer maar werkt)
#
#  Elke aanroep van speak() start een losse daemon-thread zodat de
#  camera-loop NOOIT blokkeert, ook niet bij langzame TTS.
# ══════════════════════════════════════════════════════════════════════════════

import platform, subprocess
TTS_AVAILABLE = False
_tts_lock     = threading.Lock()   # voorkom overlappende spraak

def _detect_tts():
    """Detecteer welke TTS-methode beschikbaar is. Geeft string terug."""
    if platform.system() == "Windows":
        try:
            import win32com.client
            win32com.client.Dispatch("SAPI.SpVoice")
            return "sapi"
        except Exception:
            pass
    if platform.system() == "Darwin":
        return "say"
    if platform.system() == "Linux":
        if subprocess.run(["which","espeak"], capture_output=True).returncode == 0:
            return "espeak"
    try:
        import pyttsx3
        e = pyttsx3.init(); e.stop()
        return "pyttsx3"
    except Exception:
        pass
    return None

_TTS_METHOD = _detect_tts()
TTS_AVAILABLE = _TTS_METHOD is not None

if not TTS_AVAILABLE:
    print("  [INFO] Geen TTS gevonden. Windows: pip install pywin32 | Linux: sudo apt install espeak")
else:
    print(f"  [TTS] methode: {_TTS_METHOD}")

def speak(text):
    """Spreek tekst uit in eigen daemon-thread. Niet-blokkerend."""
    if not TTS_AVAILABLE or not text:
        return

    def _run(t):
        if not _tts_lock.acquire(blocking=False):
            return   # al aan het spreken, sla over
        try:
            if _TTS_METHOD == "sapi":
                import win32com.client
                sapi = win32com.client.Dispatch("SAPI.SpVoice")
                # Probeer Nederlandse stem
                for voice in sapi.GetVoices():
                    if "nl" in voice.GetDescription().lower() or                        "dutch" in voice.GetDescription().lower() or                        "netherlands" in voice.GetDescription().lower():
                        sapi.Voice = voice
                        break
                sapi.Rate = 1   # -10 (langzaam) tot 10 (snel), 0=normaal
                sapi.Speak(t)

            elif _TTS_METHOD == "say":
                subprocess.run(["say", "-r", "180", t],
                               capture_output=True, timeout=10)

            elif _TTS_METHOD == "espeak":
                subprocess.run(["espeak", "-v", "nl", "-s", "160", t],
                               capture_output=True, timeout=10)

            elif _TTS_METHOD == "pyttsx3":
                import pyttsx3
                eng = pyttsx3.init()
                eng.setProperty("rate", 155)
                voices = eng.getProperty("voices")
                nl_v = next((v for v in voices if "nl" in v.id.lower()), None)
                if nl_v:
                    eng.setProperty("voice", nl_v.id)
                eng.say(t)
                eng.runAndWait()
                eng.stop()
        except Exception:
            pass
        finally:
            _tts_lock.release()

    threading.Thread(target=_run, args=(text,), daemon=True).start()


# ── MediaPipe ─────────────────────────────────────────────────────────────────
try:
    import mediapipe as mp
    _hands_mod  = mp.solutions.hands
    _draw_mod   = mp.solutions.drawing_utils
    _styles_mod = mp.solutions.drawing_styles
except AttributeError:
    try:
        from mediapipe.python.solutions import hands          as _hands_mod
        from mediapipe.python.solutions import drawing_utils  as _draw_mod
        from mediapipe.python.solutions import drawing_styles as _styles_mod
    except ImportError:
        print("[FOUT] MediaPipe niet geladen. pip install mediapipe==0.10.9")
        sys.exit(1)

mp_hands  = _hands_mod
mp_draw   = _draw_mod
mp_styles = _styles_mod


# ══════════════════════════════════════════════════════════════════════════════
#  Design-systeem  ·  "Neural Ink"
#  Donker glassmorfisme · neon-groen op near-black · strak en futuristisch
# ══════════════════════════════════════════════════════════════════════════════

# BGR kleurpalet
BG_DEEP    = ( 8,  10,  14)   # bijna-zwart achtergrond
BG_PANEL   = (15,  18,  24)   # paneel achtergrond
BG_CARD    = (22,  26,  36)   # kaart / sub-paneel
BG_GLASS   = (30,  35,  48)   # glassmorfisme laag
BORDER     = (45,  52,  68)   # subtiele randen
NEON       = (20, 240, 130)   # neon-groen accent  ← merkkeur
NEON_DIM   = (10, 140,  75)   # gedimde neon
NEON_GLOW  = (60, 255, 160)   # highlight
AMBER      = ( 0, 190, 255)   # oranje-amber voor "bezig"
RED_ALERT  = (40,  40, 220)   # rood voor geen hand
WHITE      = (255, 255, 255)
OFF_WHITE  = (200, 210, 225)
MUTED      = (100, 115, 140)
ZUYD_RED   = ( 30,  30, 200)

FONT   = cv2.FONT_HERSHEY_SIMPLEX
FONT_S = 0.38
FONT_M = 0.50
FONT_L = 0.65

# Timing
STABIEL_DREMPEL  = 0.65
PAUZE_SECONDEN   = 1.6
COOLDOWN_DEFAULT = 2.2
COOLDOWN_MIN     = 0.8
COOLDOWN_MAX     = 5.0
COOLDOWN_STEP    = 0.2

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
GEBAREN_DIR = os.path.join(SCRIPT_DIR, "gebaren")


# ══════════════════════════════════════════════════════════════════════════════
#  Teken-utilities
# ══════════════════════════════════════════════════════════════════════════════

def filled_rect(img, x1, y1, x2, y2, color, alpha=1.0):
    """
    Teken gevuld rechthoek. Alpha >= 0.75 → direct (geen blend, sneller).
    Alpha < 0.75 → echte blend. Vermijd alpha-calls in de hot-path.
    """
    if alpha >= 0.75:
        # Blend kleur met achtergrond in software – sneller dan addWeighted
        blended = tuple(int(c * alpha) for c in color)
        cv2.rectangle(img, (x1,y1), (x2,y2), blended, -1)
    else:
        roi = img[y1:y2, x1:x2]
        if roi.size > 0:
            overlay = np.full_like(roi, color[::-1] if len(color)==3 else color)
            # color is BGR
            overlay[:] = color
            cv2.addWeighted(overlay, alpha, roi, 1-alpha, 0, roi)

def border_rect(img, x1, y1, x2, y2, color, thickness=1):
    cv2.rectangle(img, (x1,y1), (x2,y2), color, thickness)

def glow_text(img, text, x, y, fs, color, thickness=1):
    """Tekst met zachte glow-halo."""
    # Glow laag (dikker, iets transparanter)
    glow_col = tuple(min(255, int(c*1.4)) for c in color)
    cv2.putText(img, text, (x,y), FONT, fs, glow_col, thickness+2, cv2.LINE_AA)
    cv2.putText(img, text, (x,y), FONT, fs, color,    thickness,   cv2.LINE_AA)

def pill_label(img, text, x, y, bg_color, text_color, fs=FONT_S, pad_x=8, pad_y=4):
    """Klein label met achtergrond-pill."""
    (tw, th), _ = cv2.getTextSize(text, FONT, fs, 1)
    filled_rect(img, x-pad_x, y-th-pad_y, x+tw+pad_x, y+pad_y, bg_color, alpha=0.85)
    cv2.putText(img, text, (x, y), FONT, fs, text_color, 1, cv2.LINE_AA)

def hbar(img, x, y, w, h, value, full_color=NEON, empty_color=BG_GLASS,
         border_color=BORDER, show_glow=True):
    """Moderne voortgangsbalk."""
    filled_rect(img, x, y, x+w, y+h, empty_color)
    fill = int(w * np.clip(value, 0, 1))
    if fill > 0:
        filled_rect(img, x, y, x+fill, y+h, full_color)
        # Glow-lijn bovenop
        if show_glow and fill > 2:
            glow_c = tuple(min(255, int(c*1.3)) for c in full_color)
            cv2.line(img, (x, y+1), (x+fill, y+1), glow_c, 1)
    border_rect(img, x, y, x+w, y+h, border_color)

def scanline_overlay(img, alpha=0.03):
    """Subtiele scanlines voor extra depth."""
    h, w = img.shape[:2]
    for y in range(0, h, 3):
        cv2.line(img, (0,y), (w,y), (0,0,0), 1)
    # Zwaar maar mooi: doe het via blend
    # (lichte versie: gewoon elke 3 regels een donkere lijn)


# ══════════════════════════════════════════════════════════════════════════════
#  Gebarenkaartjes
# ══════════════════════════════════════════════════════════════════════════════

def load_gesture_images():
    imgs = {}
    if not os.path.isdir(GEBAREN_DIR):
        return imgs
    for path in sorted(glob.glob(os.path.join(GEBAREN_DIR,"*.png"))):
        name = os.path.splitext(os.path.basename(path))[0]
        img  = cv2.imread(path)
        if img is not None:
            imgs[name] = img
    return imgs


def get_win_size(win_name, fallback_w=1920, fallback_h=1080):
    """
    Lees de actuele venstergrootte.
    Probeert meerdere methoden in volgorde:
      1. getWindowImageRect  (nieuwere OpenCV)
      2. getWindowProperty   (oudere OpenCV)
      3. fallback waarde
    """
    # Methode 1 – meest betrouwbaar
    try:
        r = cv2.getWindowImageRect(win_name)
        if r[2] > 200 and r[3] > 200:
            return r[2], r[3]
    except Exception:
        pass
    # Methode 2 – via WND_PROP
    try:
        w = int(cv2.getWindowProperty(win_name, cv2.WND_PROP_ASPECT_RATIO))
        if w > 0:
            pass  # niet betrouwbaar genoeg
    except Exception:
        pass
    # Fallback: schermresolutie
    return fallback_w, fallback_h


# ══════════════════════════════════════════════════════════════════════════════
#  Hand-label in camera view
# ══════════════════════════════════════════════════════════════════════════════

def draw_hand_label(frame, hand_landmarks, label, gesture, stable, cam_w, cam_h):
    wrist = hand_landmarks.landmark[0]
    px = int(wrist.x * cam_w)
    py = max(40, int(wrist.y * cam_h) - 22)
    color = NEON if stable else (AMBER if gesture else MUTED)
    text  = f"{label}: {gesture}" if gesture else label
    pill_label(frame, text, px-4, py, BG_CARD, color, fs=0.44)


# ══════════════════════════════════════════════════════════════════════════════
#  CAMERA PANEEL  (links)
# ══════════════════════════════════════════════════════════════════════════════

def draw_camera_panel(cam, hand_info, fps, last_word,
                      header_h, cooldown, elapsed, speech_on):
    h, w = cam.shape[:2]

    # Donkere strip bovenaan voor leesbaarheid (geen copy/blend nodig)
    cam[0:header_h+32, :] = (cam[0:header_h+32, :] * 0.45).astype(np.uint8)

    # ── Sub-header strip ──────────────────────────────────────────────────
    filled_rect(cam, 0, header_h, w, header_h+30, BG_PANEL, alpha=0.80)
    cv2.line(cam, (0, header_h+30), (w, header_h+30), BORDER, 1)

    hc = len(hand_info)
    hand_str = f"{hc} hand{'en' if hc!=1 else ''} gedetecteerd"
    cv2.putText(cam, hand_str, (14, header_h+20), FONT, FONT_S,
                NEON if hc else MUTED, 1, cv2.LINE_AA)
    cv2.putText(cam, f"{fps:.0f} fps", (w-58, header_h+20), FONT, FONT_S,
                MUTED, 1, cv2.LINE_AA)

    # ── Groot gebaar display rechts boven ─────────────────────────────────
    primary = next((hi for hi in hand_info if hi["stable"]), None) or \
              next((hi for hi in hand_info if hi["detected"]), None)

    show  = (primary["stable"] or primary["detected"]) if primary else None
    color = NEON if (primary and primary["stable"]) else \
            (AMBER if primary else MUTED)

    if show:
        # Achtergrond-box
        fs  = 1.0 if len(show) > 6 else (1.7 if len(show) > 3 else 2.4)
        tw  = cv2.getTextSize(show, FONT, fs, 3)[0][0]
        th2 = cv2.getTextSize(show, FONT, fs, 3)[0][1]
        bx  = w - tw - 24
        by  = header_h + 40
        filled_rect(cam, bx-12, by-8, w-8, by+th2+12, BG_CARD, alpha=0.75)
        border_rect(cam, bx-12, by-8, w-8, by+th2+12, color)
        glow_text(cam, show, bx, by+th2, fs, color, thickness=2)

        sub = "STABIEL" if (primary and primary["stable"]) else "DETECTIE"
        sub_col = NEON if (primary and primary["stable"]) else AMBER
        pill_label(cam, f"● {sub}", bx-12, by+th2+26, BG_CARD, sub_col, fs=0.38)

    # ── Status-paneel linksonder ──────────────────────────────────────────
    panel_y = h - 210
    panel_h = 200
    filled_rect(cam, 0, panel_y, 280, h, BG_PANEL, alpha=0.82)
    border_rect(cam, 0, panel_y, 280, h, BORDER)
    cv2.line(cam, (0, panel_y), (280, panel_y), NEON_DIM, 1)

    y = panel_y + 18

    # Per-hand zekerheidsbalken
    if hand_info:
        for hi in hand_info:
            lbl_col = NEON if hi["label"] == "Rechts" else (90, 200, 255)
            cv2.putText(cam, f"{hi['label']}hand", (12, y), FONT, FONT_S,
                        lbl_col, 1, cv2.LINE_AA)
            y += 16
            hbar(cam, 12, y, 200, 7, hi["conf"],
                 full_color=lbl_col, show_glow=True)
            y += 20
    else:
        pill_label(cam, "● GEEN HAND", 12, y+4, BG_CARD, RED_ALERT, fs=0.42)
        y += 28

    # Cooldown balk
    cv2.line(cam, (8, y+2), (272, y+2), BORDER, 1); y += 10
    ratio = min(elapsed / max(cooldown, 0.01), 1.0)
    cd_col = NEON if ratio >= 1.0 else AMBER
    cv2.putText(cam, "DELAY", (12, y), FONT, FONT_S, MUTED, 1, cv2.LINE_AA)
    cd_lbl = "KLAAR" if ratio>=1.0 else f"{cooldown-elapsed:.1f}s"
    cv2.putText(cam, cd_lbl, (220, y), FONT, FONT_S, cd_col, 1, cv2.LINE_AA)
    y += 12
    hbar(cam, 12, y, 256, 8, ratio, full_color=cd_col, show_glow=True)
    y += 18

    # Delay instelling
    cv2.putText(cam, f"VERTRAGING  {cooldown:.1f}s   [+/-]",
                (12, y), FONT, FONT_S, MUTED, 1, cv2.LINE_AA)
    y += 18

    # Spraak
    sp_col = NEON if speech_on else MUTED
    sp_txt = "SPRAAK  ●  AAN" if speech_on else "SPRAAK  ○  UIT"
    cv2.putText(cam, sp_txt, (12, y), FONT, FONT_S, sp_col, 1, cv2.LINE_AA)
    y += 18

    # Laatste woord
    if last_word:
        cv2.putText(cam, f"↳  {last_word}", (12, y), FONT, FONT_M,
                    NEON_GLOW, 1, cv2.LINE_AA)

    # Sneltoetsen onderin
    hints = "G=gebaren  +/-=delay  M=spraak  BKSP=wis  C=reset  Q=stop"
    cv2.putText(cam, hints, (10, h-8), FONT, 0.30, MUTED, 1, cv2.LINE_AA)


# ══════════════════════════════════════════════════════════════════════════════
#  TRANSCRIPTIE PANEEL  (rechts)
# ══════════════════════════════════════════════════════════════════════════════

def wrap_words(words, max_px, fs=0.62):
    lines=[]; line=[]; line_w=0
    for wd in words:
        tw = cv2.getTextSize(wd+" ", FONT, fs, 1)[0][0]
        if line_w+tw > max_px-32 and line:
            lines.append(" ".join(line)); line=[wd]; line_w=tw
        else:
            line.append(wd); line_w+=tw
    if line: lines.append(" ".join(line))
    return lines

def draw_transcript_panel(words, active_word, pw, ph, header_h, last_spoken, speech_on):
    panel = np.full((ph, pw, 3), BG_PANEL, dtype=np.uint8)

    # Sub-header
    filled_rect(panel, 0, header_h, pw, header_h+30, BG_CARD)
    cv2.line(panel, (0, header_h+30), (pw, header_h+30), BORDER, 1)
    cv2.putText(panel, "LIVE TRANSCRIPTIE", (14, header_h+20),
                FONT, FONT_S, NEON, 1, cv2.LINE_AA)
    # Woordteller rechts
    wc_txt = f"{len(words)} WOORDEN"
    wc_tw  = cv2.getTextSize(wc_txt, FONT, FONT_S, 1)[0][0]
    cv2.putText(panel, wc_txt, (pw-wc_tw-12, header_h+20),
                FONT, FONT_S, MUTED, 1, cv2.LINE_AA)

    # Tekst-gebied
    all_w  = words + ([f"[{active_word}]"] if active_word else [])
    lines  = wrap_words(all_w, pw) if all_w else []

    y       = header_h + 50
    max_y   = ph - 90
    line_h  = min(30, max(20, (max_y-y)//max(len(lines),1))) if lines else 26
    fs_text = min(0.68, max(0.46, line_h/42))

    for i, line in enumerate(lines):
        if y > max_y: break
        is_active = (line == lines[-1]) and active_word
        color     = NEON_GLOW if is_active else OFF_WHITE
        # Actieve regel: subtiele achtergrond highlight
        if is_active:
            lw = cv2.getTextSize(line, FONT, fs_text, 1)[0][0]
            filled_rect(panel, 10, y-line_h+4, 14+lw+8, y+6, BG_GLASS, alpha=0.6)
        cv2.putText(panel, line, (14, y), FONT, fs_text, color, 1, cv2.LINE_AA)
        y += line_h

    # Knipperende cursor
    if int(time.time()*2) % 2 == 0 and y > header_h+50:
        cx = 14
        if lines:
            cx += cv2.getTextSize(lines[-1], FONT, fs_text, 1)[0][0] + 3
        cv2.putText(panel, "▋", (cx, y-line_h), FONT, fs_text*0.8,
                    NEON, 1, cv2.LINE_AA)

    # ── Bodem-balk ────────────────────────────────────────────────────────
    filled_rect(panel, 0, ph-80, pw, ph, BG_CARD)
    cv2.line(panel, (0, ph-80), (pw, ph-80), BORDER, 1)
    # Neon accent-lijn
    cv2.line(panel, (0, ph-80), (pw, ph-80), NEON_DIM, 1)

    if last_spoken and speech_on:
        pill_label(panel, f"♪  {last_spoken}", 14, ph-52,
                   BG_GLASS, NEON, fs=FONT_S)

    cv2.putText(panel, "Hand weghalen voegt spatie toe",
                (14, ph-28), FONT, FONT_S, MUTED, 1, cv2.LINE_AA)
    cv2.putText(panel, "SignBridge  ·  Zuyd Hogeschool  ·  Lectoraat Data Intelligence",
                (14, ph-10), FONT, 0.30, MUTED, 1, cv2.LINE_AA)

    return panel


# ══════════════════════════════════════════════════════════════════════════════
#  GLOBALE HEADER
# ══════════════════════════════════════════════════════════════════════════════

def draw_header(combined, win_w, header_h, speech_on, cooldown):
    filled_rect(combined, 0, 0, win_w, header_h, BG_DEEP)

    # Neon accent-lijn onderaan header
    cv2.line(combined, (0, header_h-1), (win_w, header_h-1), NEON_DIM, 1)
    cv2.line(combined, (0, header_h),   (win_w, header_h),   BORDER,   1)

    # Logo / naam
    glow_text(combined, "SignBridge", 16, int(header_h*0.70),
              FONT_L, NEON, thickness=2)

    # Subtitel
    sub = "NGT Gebarentaal  →  Live Tekst"
    sub_x = 16 + cv2.getTextSize("SignBridge", FONT, FONT_L, 2)[0][0] + 18
    cv2.putText(combined, sub, (sub_x, int(header_h*0.68)), FONT, FONT_S,
                MUTED, 1, cv2.LINE_AA)

    # Rechts: badges
    bx = win_w - 14
    badges = []
    badges.append(("SPRAAK AAN" if speech_on else "SPRAAK UIT",
                   NEON if speech_on else MUTED,
                   BG_GLASS))
    badges.append((f"DELAY {cooldown:.1f}s", AMBER, BG_GLASS))
    badges.append(("ZUYD HOGESCHOOL", MUTED, BG_CARD))

    for txt, tc, bc in reversed(badges):
        tw = cv2.getTextSize(txt, FONT, FONT_S, 1)[0][0]
        bx -= tw + 20
        filled_rect(combined, bx-6, int(header_h*0.25),
                    bx+tw+8, int(header_h*0.82), bc, alpha=0.9)
        border_rect(combined, bx-6, int(header_h*0.25),
                    bx+tw+8, int(header_h*0.82), BORDER)
        cv2.putText(combined, txt, (bx, int(header_h*0.68)),
                    FONT, FONT_S, tc, 1, cv2.LINE_AA)
        bx -= 8


# ══════════════════════════════════════════════════════════════════════════════
#  GEBARENREFERENTIE OVERLAY
# ══════════════════════════════════════════════════════════════════════════════

def draw_gesture_overlay(combined, gesture_imgs, ref_idx, win_w, win_h, header_h):
    keys = [k for k in gesture_imgs if not k.startswith("_")]
    if not keys: return
    idx   = ref_idx % len(keys)
    card  = gesture_imgs[keys[idx]]

    cw = max(200, int(win_w * 0.26))
    ch = int(card.shape[0] * (cw / card.shape[1]))
    small = cv2.resize(card, (cw, ch))

    # Positie: rechts naast transcriptie, net onder header
    x0 = win_w - cw - 16
    y0 = header_h + 10
    x1, y1 = min(win_w-8, x0+cw), min(win_h-30, y0+ch)
    sw, sh  = x1-x0, y1-y0
    if sw<=0 or sh<=0: return

    # Glassmorfisme achtergrond
    filled_rect(combined, x0-4, y0-4, x1+4, y1+30, BG_DEEP, alpha=0.85)
    roi = combined[y0:y1, x0:x1].copy()
    cv2.addWeighted(small[:sh,:sw], 0.92, roi, 0.08, 0, combined[y0:y1,x0:x1])

    # Neon border
    border_rect(combined, x0-4, y0-4, x1+4, y1+30, NEON_DIM, 1)
    cv2.line(combined, (x0-4, y0-4), (x1+4, y0-4), NEON, 1)  # top accent

    # Navigatie
    nav = f"◀ P    {idx+1} / {len(keys)}    N ▶"
    ntw = cv2.getTextSize(nav, FONT, FONT_S, 1)[0][0]
    cv2.putText(combined, nav, (x0 + (cw-ntw)//2, y1+20),
                FONT, FONT_S, MUTED, 1, cv2.LINE_AA)


# ══════════════════════════════════════════════════════════════════════════════
#  VERTICALE SCHEIDINGSLIJN
# ══════════════════════════════════════════════════════════════════════════════

def draw_divider(combined, cam_w, win_h, header_h):
    # Meervoudige lijnen voor diepte-effect
    cv2.line(combined, (cam_w-1, header_h), (cam_w-1, win_h), BG_DEEP, 2)
    cv2.line(combined, (cam_w,   header_h), (cam_w,   win_h), BORDER,  1)
    cv2.line(combined, (cam_w+1, header_h), (cam_w+1, win_h), BG_DEEP, 1)


# ══════════════════════════════════════════════════════════════════════════════
#  HOOFDLUS
# ══════════════════════════════════════════════════════════════════════════════

WIN_NAME   = "SignBridge"
CHAT_RATIO = 0.33

def get_screen_resolution():
    """Haal schermresolutie op via tkinter, val terug op 1920x1080."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
        if w > 400 and h > 300:
            return w, h
    except Exception:
        pass
    return 1920, 1080


def main():
    # ── Venster aanmaken VOOR fullscreen ─────────────────────────────────────
    cv2.namedWindow(WIN_NAME, cv2.WINDOW_NORMAL)

    screen_w, screen_h = get_screen_resolution()
    print(f"  Scherm: {screen_w}x{screen_h}")

    # Zet venster op schermgrootte, verplaats naar (0,0), activeer fullscreen
    cv2.resizeWindow(WIN_NAME, screen_w, screen_h)
    cv2.moveWindow(WIN_NAME, 0, 0)
    cv2.setWindowProperty(WIN_NAME, cv2.WND_PROP_FULLSCREEN,
                          cv2.WINDOW_FULLSCREEN)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    gesture_imgs = load_gesture_images()
    print(f"  {len(gesture_imgs)} gebarenkaartjes geladen")
    print(f"  {len(WOORDENLIJST)} gebaren actief")

    buf             = MultiHandBuffer()
    words           = []
    last_word       = ""
    last_add_t      = 0.0
    last_seen       = {"Left": 0.0, "Right": 0.0}
    space_given     = False
    prev_t          = time.time()
    _vignette_mask  = None   # cache: herberekend alleen bij resize

    cooldown    = COOLDOWN_DEFAULT
    show_ref    = False
    ref_idx     = 0
    speech_on   = TTS_AVAILABLE
    last_spoken = ""

    print(f"\n  SignBridge — fullscreen gestart")
    print(f"  Spraak: {'AAN' if TTS_AVAILABLE else 'UIT (pip install pyttsx3)'}")
    print("  Q=stop  G=gebaren  M=spraak  +/-=delay\n")

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.70,
        min_tracking_confidence=0.60,
    ) as hands:

        while True:
            ret, raw = cap.read()
            if not ret:
                break

            win_w, win_h = get_win_size(WIN_NAME,
                                          fallback_w=screen_w,
                                          fallback_h=screen_h)

            header_h = max(48, int(win_h * 0.075))
            chat_w   = max(220, int(win_w * CHAT_RATIO))
            cam_w    = win_w - chat_w
            cam_h    = win_h

            frame = cv2.flip(raw, 1)
            frame = cv2.resize(frame, (cam_w, cam_h))

            # Vignette-masker: eenmalig berekenen als grootte verandert
            if (_vignette_mask is None
                    or _vignette_mask.shape[:2] != (cam_h, cam_w)):
                cy_, cx_ = cam_h//2, cam_w//2
                Y_, X_   = np.ogrid[:cam_h, :cam_w]
                dist_    = np.sqrt((X_-cx_)**2 + (Y_-cy_)**2, dtype=np.float32)
                dist_   /= dist_.max()
                _vignette_mask = (1 - np.clip(dist_*1.2-0.3, 0, 0.5))
                _vignette_mask = np.stack([_vignette_mask]*3, axis=2)

            frame = (frame * _vignette_mask).astype(np.uint8)

            # MediaPipe op halve resolutie voor snelheid (~2x FPS winst)
            mp_scale = 0.5 if cam_w > 800 else 1.0
            if mp_scale < 1.0:
                small_rgb = cv2.resize(frame,
                    (int(cam_w*mp_scale), int(cam_h*mp_scale)))
                rgb = cv2.cvtColor(small_rgb, cv2.COLOR_BGR2RGB)
            else:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = hands.process(rgb)

            now        = time.time()
            hand_info  = []
            seen_labels = set()

            if res.multi_hand_landmarks and res.multi_handedness:
                for hl, hd in zip(res.multi_hand_landmarks, res.multi_handedness):
                    raw_label = hd.classification[0].label
                    label     = "Rechts" if raw_label == "Left" else "Links"
                    mp_label  = raw_label

                    # Skeleton – aangepaste kleur per hand
                    mp_draw.draw_landmarks(
                        frame, hl, mp_hands.HAND_CONNECTIONS,
                        mp_styles.get_default_hand_landmarks_style(),
                        mp_styles.get_default_hand_connections_style(),
                    )

                    detected = classify_ngt(hl)
                    buf.update(mp_label, detected)
                    stable, conf = buf.stable(mp_label)

                    last_seen[mp_label] = now
                    seen_labels.add(mp_label)

                    draw_hand_label(frame, hl, label, stable or detected,
                                    bool(stable), cam_w, cam_h)

                    hand_info.append({
                        "label":    label,
                        "detected": detected,
                        "stable":   stable,
                        "conf":     conf,
                    })

                    elapsed = now - last_add_t
                    if stable and stable != last_word and elapsed >= cooldown:
                        words.append(stable)
                        last_word  = stable
                        last_add_t = now
                        print(f"  + {stable}  [{label}]")
                        if speech_on:
                            speak(stable)
                            last_spoken = stable

            for mp_label in ("Left","Right"):
                if mp_label not in seen_labels:
                    buf.reset(mp_label)

            if not any(hi["stable"] for hi in hand_info):
                last_word = ""

            both_gone = (now - last_seen["Left"]  > PAUZE_SECONDEN and
                         now - last_seen["Right"] > PAUZE_SECONDEN)
            if both_gone and not space_given and words and words[-1] != " ":
                words.append(" ")
                space_given = True
                last_word   = ""
            if not both_gone:
                space_given = False

            fps    = 1.0 / (now - prev_t + 1e-6)
            prev_t = now

            # ── Teken UI ──────────────────────────────────────────────────
            elapsed_since = now - last_add_t
            draw_camera_panel(frame, hand_info, fps, last_word,
                              header_h, cooldown, elapsed_since, speech_on)

            display_words = [w for w in words if w != " "]
            active = next((hi["stable"] or hi["detected"]
                           for hi in hand_info
                           if hi["stable"] or hi["detected"]), None)
            transcript = draw_transcript_panel(
                display_words,
                active if (active and active != last_word) else None,
                chat_w, cam_h, header_h, last_spoken, speech_on
            )

            combined = np.hstack([frame, transcript])

            # Scheidingslijn + header (over gecombineerd canvas)
            draw_divider(combined, cam_w, win_h, header_h)
            draw_header(combined, win_w, header_h, speech_on, cooldown)

            if show_ref and gesture_imgs:
                draw_gesture_overlay(combined, gesture_imgs, ref_idx,
                                     win_w, win_h, header_h)

            cv2.imshow(WIN_NAME, combined)
            key = cv2.waitKey(1) & 0xFF

            if   key == ord("q"): break
            elif key == ord("f"):
                # Toggle fullscreen
                fs = cv2.getWindowProperty(WIN_NAME, cv2.WND_PROP_FULLSCREEN)
                if fs == cv2.WINDOW_FULLSCREEN:
                    cv2.setWindowProperty(WIN_NAME, cv2.WND_PROP_FULLSCREEN,
                                          cv2.WINDOW_NORMAL)
                    cv2.resizeWindow(WIN_NAME, 1280, 720)
                else:
                    cv2.resizeWindow(WIN_NAME, screen_w, screen_h)
                    cv2.moveWindow(WIN_NAME, 0, 0)
                    cv2.setWindowProperty(WIN_NAME, cv2.WND_PROP_FULLSCREEN,
                                          cv2.WINDOW_FULLSCREEN)
            elif key == ord("g") or key == 27:   # G of ESC
                show_ref = not show_ref
            elif key == ord("n"): ref_idx += 1
            elif key == ord("p"): ref_idx -= 1
            elif key == ord("m"):
                speech_on = (not speech_on) and TTS_AVAILABLE
                print(f"  Spraak: {'AAN' if speech_on else 'UIT'}")
            elif key in (ord("+"), ord("=")):
                cooldown = min(COOLDOWN_MAX, round(cooldown+COOLDOWN_STEP,1))
                print(f"  Delay: {cooldown:.1f}s")
            elif key == ord("-"):
                cooldown = max(COOLDOWN_MIN, round(cooldown-COOLDOWN_STEP,1))
                print(f"  Delay: {cooldown:.1f}s")
            elif key == 8:
                while words and words[-1]==" ": words.pop()
                if words:
                    print(f"  - '{words.pop()}' verwijderd")
                last_word = words[-1] if words else ""
            elif key == ord("c"):
                words=[]; last_word=""; last_spoken=""
                print("  Transcriptie gewist.")

    cap.release()
    cv2.destroyAllWindows()
    clean = " ".join(w for w in words if w!=" ")
    print(f"\n  Eindtranscriptie: '{clean}'")


if __name__ == "__main__":
    main()
