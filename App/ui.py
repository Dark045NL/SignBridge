"""
ui.py – Alle tekenfuncties voor SignBridge
Zuyd Hogeschool | Lectoraat Data Intelligence

Exports:
    draw_frame(canvas, state) – tekent het volledige UI-frame
    build_vignette(w, h)      – genereert vignette-masker (eenmalig cachen)
"""

import cv2
import numpy as np
import time

# ── Design-systeem "Neural Ink" (BGR) ────────────────────────────────────────
BG_DEEP   = (  8,  10,  14)
BG_PANEL  = ( 15,  18,  24)
BG_CARD   = ( 22,  26,  36)
BG_GLASS  = ( 30,  35,  48)
BORDER    = ( 45,  52,  68)
NEON      = ( 20, 240, 130)
NEON_DIM  = ( 10, 140,  75)
NEON_GLOW = ( 60, 255, 160)
AMBER     = (  0, 190, 255)
RED_ALERT = ( 40,  40, 220)
OFF_WHITE = (200, 210, 225)
MUTED     = (100, 115, 140)

F   = cv2.FONT_HERSHEY_SIMPLEX
FS  = 0.38   # small
FM  = 0.50   # medium
FL  = 0.65   # large


# ── Primitives ────────────────────────────────────────────────────────────────

def _rect(img, x1, y1, x2, y2, color):
    cv2.rectangle(img, (x1, y1), (x2, y2), color, -1)

def _border(img, x1, y1, x2, y2, color, t=1):
    cv2.rectangle(img, (x1, y1), (x2, y2), color, t)

def _text(img, txt, x, y, fs, color, bold=False):
    cv2.putText(img, txt, (x, y), F, fs, color, 2 if bold else 1, cv2.LINE_AA)

def _glow(img, txt, x, y, fs, color):
    glow = tuple(min(255, int(c * 1.4)) for c in color)
    cv2.putText(img, txt, (x, y), F, fs, glow, 3, cv2.LINE_AA)
    cv2.putText(img, txt, (x, y), F, fs, color, 1, cv2.LINE_AA)

def _pill(img, txt, x, y, bg, fg, fs=FS):
    (tw, th), _ = cv2.getTextSize(txt, F, fs, 1)
    _rect(img, x - 6, y - th - 4, x + tw + 6, y + 4, bg)
    _text(img, txt, x, y, fs, fg)

def _hbar(img, x, y, w, h, ratio, full=NEON):
    _rect(img, x, y, x + w, y + h, BG_GLASS)
    fill = int(w * np.clip(ratio, 0, 1))
    if fill > 0:
        _rect(img, x, y, x + fill, y + h, full)
        glow = tuple(min(255, int(c * 1.3)) for c in full)
        cv2.line(img, (x, y + 1), (x + fill, y + 1), glow, 1)
    _border(img, x, y, x + w, y + h, BORDER)


# ── Vignette (eenmalig berekenen) ─────────────────────────────────────────────

def build_vignette(w: int, h: int) -> np.ndarray:
    cy, cx = h // 2, w // 2
    Y, X   = np.ogrid[:h, :w]
    dist   = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2, dtype=np.float32)
    dist  /= dist.max()
    mask   = 1 - np.clip(dist * 1.2 - 0.3, 0, 0.5)
    return np.stack([mask] * 3, axis=2)


# ── Hand-label ────────────────────────────────────────────────────────────────

def draw_hand_label(frame, landmarks, label, gesture, stable, w, h):
    wrist = landmarks.landmark[0]
    px    = int(wrist.x * w)
    py    = max(40, int(wrist.y * h) - 22)
    color = NEON if stable else (AMBER if gesture else MUTED)
    _pill(frame, f"{label}: {gesture}" if gesture else label,
          px - 4, py, BG_CARD, color, fs=0.44)


# ── Camera-paneel ─────────────────────────────────────────────────────────────

def draw_camera_panel(cam, hand_info, fps, last_word,
                      header_h, cooldown, elapsed, speech_on):
    h, w = cam.shape[:2]

    # Verdonker bovenstrip
    cam[0:header_h + 32, :] = (cam[0:header_h + 32, :] * 0.45).astype(np.uint8)

    # Sub-header
    _rect(cam, 0, header_h, w, header_h + 30, BG_PANEL)
    cv2.line(cam, (0, header_h + 30), (w, header_h + 30), BORDER, 1)
    hc = len(hand_info)
    _text(cam, f"{hc} hand{'en' if hc != 1 else ''} gedetecteerd",
          14, header_h + 20, FS, NEON if hc else MUTED)
    _text(cam, f"{fps:.0f} fps", w - 58, header_h + 20, FS, MUTED)

    # Groot gebaar label
    primary = next((hi for hi in hand_info if hi["stable"]), None) or \
              next((hi for hi in hand_info if hi["detected"]), None)
    if primary:
        show  = primary["stable"] or primary["detected"]
        color = NEON if primary["stable"] else AMBER
        fs    = 1.0 if len(show) > 6 else (1.7 if len(show) > 3 else 2.4)
        tw, th2 = cv2.getTextSize(show, F, fs, 3)[0]
        bx = w - tw - 24
        by = header_h + 40
        _rect(cam, bx - 12, by - 8, w - 8, by + th2 + 12, BG_CARD)
        _border(cam, bx - 12, by - 8, w - 8, by + th2 + 12, color)
        _glow(cam, show, bx, by + th2, fs, color)
        sub = "STABIEL" if primary["stable"] else "DETECTIE"
        _pill(cam, f"● {sub}", bx - 12, by + th2 + 26, BG_CARD,
              NEON if primary["stable"] else AMBER, fs=0.38)

    # Status-paneel linksonder
    py = h - 210
    _rect(cam, 0, py, 280, h, BG_PANEL)
    _border(cam, 0, py, 280, h, BORDER)
    cv2.line(cam, (0, py), (280, py), NEON_DIM, 1)
    y = py + 18

    if hand_info:
        for hi in hand_info:
            col = NEON if hi["label"] == "Rechts" else (90, 200, 255)
            _text(cam, f"{hi['label']}hand", 12, y, FS, col)
            y += 16
            _hbar(cam, 12, y, 200, 7, hi["conf"], full=col)
            y += 20
    else:
        _pill(cam, "● GEEN HAND", 12, y + 4, BG_CARD, RED_ALERT, fs=0.42)
        y += 28

    cv2.line(cam, (8, y + 2), (272, y + 2), BORDER, 1); y += 10
    ratio  = min(elapsed / max(cooldown, 0.01), 1.0)
    cd_col = NEON if ratio >= 1.0 else AMBER
    _text(cam, "DELAY", 12, y, FS, MUTED)
    _text(cam, "KLAAR" if ratio >= 1.0 else f"{cooldown - elapsed:.1f}s",
          220, y, FS, cd_col)
    y += 12
    _hbar(cam, 12, y, 256, 8, ratio, full=cd_col); y += 18
    _text(cam, f"VERTRAGING  {cooldown:.1f}s   [+/-]", 12, y, FS, MUTED); y += 18
    _text(cam, "SPRAAK  ● AAN" if speech_on else "SPRAAK  ○ UIT",
          12, y, FS, NEON if speech_on else MUTED); y += 18
    if last_word:
        _text(cam, f"↳  {last_word}", 12, y, FM, NEON_GLOW)

    _text(cam, "G=gebaren  +/-=delay  M=spraak  BKSP=wis  C=reset  Q=stop",
          10, h - 8, 0.30, MUTED)


# ── Transcriptie-paneel ───────────────────────────────────────────────────────

def _wrap(words, max_px, fs=0.62):
    lines, line, line_w = [], [], 0
    for wd in words:
        tw = cv2.getTextSize(wd + " ", F, fs, 1)[0][0]
        if line_w + tw > max_px - 32 and line:
            lines.append(" ".join(line)); line = [wd]; line_w = tw
        else:
            line.append(wd); line_w += tw
    if line:
        lines.append(" ".join(line))
    return lines

def draw_transcript_panel(words, active, pw, ph, header_h, last_spoken, speech_on):
    panel = np.full((ph, pw, 3), BG_PANEL, dtype=np.uint8)

    # Sub-header
    _rect(panel, 0, header_h, pw, header_h + 30, BG_CARD)
    cv2.line(panel, (0, header_h + 30), (pw, header_h + 30), BORDER, 1)
    _text(panel, "LIVE TRANSCRIPTIE", 14, header_h + 20, FS, NEON)
    wc = f"{len(words)} WOORDEN"
    _text(panel, wc, pw - cv2.getTextSize(wc, F, FS, 1)[0][0] - 12,
          header_h + 20, FS, MUTED)

    # Woorden
    all_w  = words + ([f"[{active}]"] if active else [])
    lines  = _wrap(all_w, pw) if all_w else []
    y      = header_h + 50
    max_y  = ph - 90
    lh     = min(30, max(20, (max_y - y) // max(len(lines), 1))) if lines else 26
    fst    = min(0.68, max(0.46, lh / 42))

    for line in lines:
        if y > max_y:
            break
        is_act = (line == lines[-1]) and active
        if is_act:
            lw = cv2.getTextSize(line, F, fst, 1)[0][0]
            _rect(panel, 10, y - lh + 4, 14 + lw + 8, y + 6, BG_GLASS)
        _text(panel, line, 14, y, fst, NEON_GLOW if is_act else OFF_WHITE)
        y += lh

    # Cursor
    if int(time.time() * 2) % 2 == 0 and y > header_h + 50:
        cx = 14 + (cv2.getTextSize(lines[-1], F, fst, 1)[0][0] + 3 if lines else 0)
        _text(panel, "▋", cx, y - lh, fst * 0.8, NEON)

    # Bodem
    _rect(panel, 0, ph - 80, pw, ph, BG_CARD)
    cv2.line(panel, (0, ph - 80), (pw, ph - 80), NEON_DIM, 1)
    if last_spoken and speech_on:
        _pill(panel, f"♪  {last_spoken}", 14, ph - 52, BG_GLASS, NEON)
    _text(panel, "Hand weghalen voegt spatie toe", 14, ph - 28, FS, MUTED)
    _text(panel, "SignBridge  ·  Zuyd Hogeschool  ·  Lectoraat Data Intelligence",
          14, ph - 10, 0.30, MUTED)
    return panel


# ── Header ────────────────────────────────────────────────────────────────────

def draw_header(img, win_w, header_h, speech_on, cooldown):
    _rect(img, 0, 0, win_w, header_h, BG_DEEP)
    cv2.line(img, (0, header_h - 1), (win_w, header_h - 1), NEON_DIM, 1)
    cv2.line(img, (0, header_h),     (win_w, header_h),     BORDER,   1)

    hy = int(header_h * 0.68)
    _glow(img, "SignBridge", 16, hy, FL, NEON)
    sx = 16 + cv2.getTextSize("SignBridge", F, FL, 2)[0][0] + 18
    _text(img, "NGT Gebarentaal  →  Live Tekst", sx, int(header_h * 0.68), FS, MUTED)

    badges = [
        ("SPRAAK AAN" if speech_on else "SPRAAK UIT", NEON if speech_on else MUTED),
        (f"DELAY {cooldown:.1f}s", AMBER),
        ("ZUYD HOGESCHOOL", MUTED),
    ]
    bx = win_w - 14
    for txt, tc in reversed(badges):
        tw = cv2.getTextSize(txt, F, FS, 1)[0][0]
        bx -= tw + 20
        _rect(img, bx - 6, int(header_h * 0.25), bx + tw + 8, int(header_h * 0.82), BG_GLASS)
        _border(img, bx - 6, int(header_h * 0.25), bx + tw + 8, int(header_h * 0.82), BORDER)
        _text(img, txt, bx, hy, FS, tc)
        bx -= 8


# ── Divider ───────────────────────────────────────────────────────────────────

def draw_divider(img, cam_w, win_h, header_h):
    cv2.line(img, (cam_w - 1, header_h), (cam_w - 1, win_h), BG_DEEP,  2)
    cv2.line(img, (cam_w,     header_h), (cam_w,     win_h), BORDER,   1)
    cv2.line(img, (cam_w + 1, header_h), (cam_w + 1, win_h), BG_DEEP,  1)


# ── Gebarenreferentie-overlay ─────────────────────────────────────────────────

def draw_gesture_overlay(img, gesture_imgs, ref_idx, win_w, win_h, header_h):
    keys = [k for k in gesture_imgs if not k.startswith("_")]
    if not keys:
        return
    idx   = ref_idx % len(keys)
    card  = gesture_imgs[keys[idx]]
    cw    = max(200, int(win_w * 0.26))
    ch    = int(card.shape[0] * (cw / card.shape[1]))
    small = cv2.resize(card, (cw, ch))
    x0, y0 = win_w - cw - 16, header_h + 10
    x1, y1 = min(win_w - 8, x0 + cw), min(win_h - 30, y0 + ch)
    sw, sh  = x1 - x0, y1 - y0
    if sw <= 0 or sh <= 0:
        return
    _rect(img, x0 - 4, y0 - 4, x1 + 4, y1 + 30, BG_DEEP)
    roi = img[y0:y1, x0:x1].copy()
    cv2.addWeighted(small[:sh, :sw], 0.92, roi, 0.08, 0, img[y0:y1, x0:x1])
    _border(img, x0 - 4, y0 - 4, x1 + 4, y1 + 30, NEON_DIM)
    cv2.line(img, (x0 - 4, y0 - 4), (x1 + 4, y0 - 4), NEON, 1)
    nav = f"◀ P    {idx + 1} / {len(keys)}    N ▶"
    ntw = cv2.getTextSize(nav, F, FS, 1)[0][0]
    _text(img, nav, x0 + (cw - ntw) // 2, y1 + 20, FS, MUTED)
