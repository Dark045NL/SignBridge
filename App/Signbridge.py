"""
SignBridge – NGT Gebarentaal → Live Transcriptie
Zuyd Hogeschool | Lectoraat Data Intelligence

Projectstructuur:
    SignBridge.py           ← hoofdlus (dit bestand)
    ui.py                   ← alle tekenfuncties
    tts.py                  ← text-to-speech
    gebaren_classifier.py   ← gebaar-herkenning
    gebaren/                ← PNG uitlegkaartjes

Installatie:
    pip install opencv-python mediapipe numpy
    pip install pywin32       (Windows spraak)
    sudo apt install espeak   (Linux spraak)

Starten:
    cd App && python SignBridge.py

Bediening:
    F          fullscreen toggle
    G / ESC    gebarenreferentie aan/uit
    N / P      volgend / vorig gebaar
    + / -      delay verhogen / verlagen
    M          spraak aan/uit
    BACKSPACE  wis laatste woord
    C          wis transcriptie
    Q          afsluiten
"""

import sys, os, glob, time
import cv2
import numpy as np

# ── Eigen modules ─────────────────────────────────────────────────────────────
try:
    from gebaren_classifier import classify_ngt, MultiHandBuffer, WOORDENLIJST
    from tts import speak, AVAILABLE as TTS_AVAILABLE
    from ui import (build_vignette, draw_hand_label, draw_camera_panel,
                    draw_transcript_panel, draw_header, draw_divider,
                    draw_gesture_overlay)
except ImportError as e:
    print(f"\n[FOUT] {e}")
    print("Zorg dat alle bestanden in dezelfde map staan.\n")
    sys.exit(1)

# ── MediaPipe ─────────────────────────────────────────────────────────────────
try:
    import mediapipe as mp
    _h = mp.solutions.hands
    _d = mp.solutions.drawing_utils
    _s = mp.solutions.drawing_styles
except AttributeError:
    from mediapipe.python.solutions import hands as _h, \
        drawing_utils as _d, drawing_styles as _s

# ── Constanten ────────────────────────────────────────────────────────────────
WIN         = "SignBridge"
CHAT_RATIO  = 0.33
PAUSE_S     = 1.6
CD_DEFAULT  = 2.2
CD_MIN, CD_MAX, CD_STEP = 0.8, 5.0, 0.2

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
GEBAREN_DIR = os.path.join(SCRIPT_DIR, "gebaren")


def get_screen_size() -> tuple[int, int]:
    try:
        import tkinter as tk
        r = tk.Tk(); r.withdraw()
        w, h = r.winfo_screenwidth(), r.winfo_screenheight()
        r.destroy()
        if w > 400 and h > 300:
            return w, h
    except Exception:
        pass
    return 1920, 1080


def get_win_size(fallback_w, fallback_h) -> tuple[int, int]:
    try:
        r = cv2.getWindowImageRect(WIN)
        if r[2] > 200 and r[3] > 200:
            return r[2], r[3]
    except Exception:
        pass
    return fallback_w, fallback_h


def load_gestures() -> dict:
    imgs = {}
    if not os.path.isdir(GEBAREN_DIR):
        return imgs
    for p in sorted(glob.glob(os.path.join(GEBAREN_DIR, "*.png"))):
        img = cv2.imread(p)
        if img is not None:
            imgs[os.path.splitext(os.path.basename(p))[0]] = img
    return imgs


def main():
    # Venster + fullscreen
    sw, sh = get_screen_size()
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, sw, sh)
    cv2.moveWindow(WIN, 0, 0)
    cv2.setWindowProperty(WIN, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    gestures     = load_gestures()
    buf          = MultiHandBuffer()
    words        = []
    last_word    = ""
    last_add_t   = 0.0
    last_seen    = {"Left": 0.0, "Right": 0.0}
    space_given  = False
    prev_t       = time.time()
    vig_cache    = None          # vignette-masker cache
    cooldown     = CD_DEFAULT
    show_ref     = False
    ref_idx      = 0
    speech_on    = TTS_AVAILABLE
    last_spoken  = ""

    print(f"\n  SignBridge  |  {len(WOORDENLIJST)} gebaren  |  TTS: {TTS_AVAILABLE}")
    print("  Q=stop  F=fullscreen  G=gebaren  M=spraak  +/-=delay\n")

    with _h.Hands(max_num_hands=2,
                  min_detection_confidence=0.70,
                  min_tracking_confidence=0.60) as hands:
        while True:
            ret, raw = cap.read()
            if not ret:
                break

            ww, wh  = get_win_size(sw, sh)
            hdr     = max(48, int(wh * 0.075))
            chat_w  = max(220, int(ww * CHAT_RATIO))
            cam_w   = ww - chat_w
            cam_h   = wh

            # Frame voorbereiden
            frame = cv2.flip(raw, 1)
            frame = cv2.resize(frame, (cam_w, cam_h))

            # Vignette (gecacht)
            if vig_cache is None or vig_cache.shape[:2] != (cam_h, cam_w):
                vig_cache = build_vignette(cam_w, cam_h)
            frame = (frame * vig_cache).astype(np.uint8)

            # MediaPipe op halve resolutie
            scale     = 0.5 if cam_w > 800 else 1.0
            mp_frame  = cv2.resize(frame, (int(cam_w * scale), int(cam_h * scale)))
            res       = hands.process(cv2.cvtColor(mp_frame, cv2.COLOR_BGR2RGB))

            now        = time.time()
            hand_info  = []
            seen       = set()

            if res.multi_hand_landmarks and res.multi_handedness:
                for hl, hd in zip(res.multi_hand_landmarks, res.multi_handedness):
                    raw_lbl = hd.classification[0].label
                    label   = "Rechts" if raw_lbl == "Left" else "Links"

                    _d.draw_landmarks(frame, hl, _h.HAND_CONNECTIONS,
                                      _s.get_default_hand_landmarks_style(),
                                      _s.get_default_hand_connections_style())

                    detected = classify_ngt(hl)
                    buf.update(raw_lbl, detected)
                    stable, conf = buf.stable(raw_lbl)

                    last_seen[raw_lbl] = now
                    seen.add(raw_lbl)
                    draw_hand_label(frame, hl, label, stable or detected,
                                    bool(stable), cam_w, cam_h)
                    hand_info.append({"label": label, "detected": detected,
                                      "stable": stable, "conf": conf})

                    if stable and stable != last_word and (now - last_add_t) >= cooldown:
                        words.append(stable)
                        last_word = stable; last_add_t = now
                        print(f"  + {stable}  [{label}]")
                        if speech_on:
                            speak(stable); last_spoken = stable

            for lbl in ("Left", "Right"):
                if lbl not in seen:
                    buf.reset(lbl)

            if not any(hi["stable"] for hi in hand_info):
                last_word = ""

            both_gone = all(now - last_seen[l] > PAUSE_S for l in ("Left", "Right"))
            if both_gone and not space_given and words and words[-1] != " ":
                words.append(" "); space_given = True; last_word = ""
            if not both_gone:
                space_given = False

            fps    = 1.0 / (now - prev_t + 1e-6)
            prev_t = now
            elapsed = now - last_add_t

            # ── UI ────────────────────────────────────────────────────────
            draw_camera_panel(frame, hand_info, fps, last_word,
                              hdr, cooldown, elapsed, speech_on)

            display = [w for w in words if w != " "]
            active  = next((hi["stable"] or hi["detected"] for hi in hand_info
                            if hi["stable"] or hi["detected"]), None)
            panel   = draw_transcript_panel(
                display, active if (active and active != last_word) else None,
                chat_w, cam_h, hdr, last_spoken, speech_on)

            out = np.hstack([frame, panel])
            draw_divider(out, cam_w, wh, hdr)
            draw_header(out, ww, hdr, speech_on, cooldown)

            if show_ref and gestures:
                draw_gesture_overlay(out, gestures, ref_idx, ww, wh, hdr)

            cv2.imshow(WIN, out)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            elif key == ord("f"):
                fs = cv2.getWindowProperty(WIN, cv2.WND_PROP_FULLSCREEN)
                if fs == cv2.WINDOW_FULLSCREEN:
                    cv2.setWindowProperty(WIN, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                    cv2.resizeWindow(WIN, 1280, 720)
                else:
                    cv2.resizeWindow(WIN, sw, sh)
                    cv2.moveWindow(WIN, 0, 0)
                    cv2.setWindowProperty(WIN, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            elif key in (ord("g"), 27):   show_ref = not show_ref
            elif key == ord("n"):         ref_idx += 1
            elif key == ord("p"):         ref_idx -= 1
            elif key == ord("m"):
                speech_on = (not speech_on) and TTS_AVAILABLE
                print(f"  Spraak: {'AAN' if speech_on else 'UIT'}")
            elif key in (ord("+"), ord("=")):
                cooldown = min(CD_MAX, round(cooldown + CD_STEP, 1))
                print(f"  Delay: {cooldown:.1f}s")
            elif key == ord("-"):
                cooldown = max(CD_MIN, round(cooldown - CD_STEP, 1))
                print(f"  Delay: {cooldown:.1f}s")
            elif key == 8:
                while words and words[-1] == " ": words.pop()
                if words: print(f"  - '{words.pop()}' verwijderd")
                last_word = words[-1] if words else ""
            elif key == ord("c"):
                words = []; last_word = ""; last_spoken = ""
                print("  Transcriptie gewist.")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\n  Eindtranscriptie: '{' '.join(w for w in words if w != ' ')}'")


if __name__ == "__main__":
    main()
