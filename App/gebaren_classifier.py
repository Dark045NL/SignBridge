"""
gebaren_classifier.py
=====================
NGT Gebaar-classifier voor SignBridge
Zuyd Hogeschool | Lectoraat Data Intelligence

Dit module bevat:
  - Feature-extractie functies (landmarks → meetwaarden)
  - GestureBuffer (smoothing over meerdere frames)
  - classify_ngt()  (rule-based classifier, 25 woorden)

Gebruik vanuit SignBridge.py:
    from gebaren_classifier import classify_ngt, GestureBuffer

Woordenlijst (25 gebaren):
    HALLO, DAG, TOT_ZIENS, BEDANKT, GRAAG_GEDAAN,
    JA, NEE, HELP, STOP, GOED, SLECHT, MEER, MINDER,
    IK, JIJ, WIJ, NAAM, SCHOOL, LEREN, WERKEN,
    WATER, EEN, TWEE, DRIE, VRAAG

Uitbreiden:
    Voeg onderaan classify_ngt() een nieuwe regel toe, bijv.:
        if ix and not mi and not ri and not pi and not th:
            return "NIEUW_GEBAAR"
    en voeg het woord toe aan WOORDENLIJST hieronder.
"""

import numpy as np
from collections import deque, Counter

# ── Publieke woordenlijst (voor UI en referentie) ─────────────────────────────
WOORDENLIJST = [
    "HALLO", "DAG", "TOT_ZIENS", "BEDANKT", "GRAAG_GEDAAN",
    "JA", "NEE", "HELP", "STOP", "GOED", "SLECHT", "MEER", "MINDER",
    "IK", "JIJ", "WIJ", "NAAM", "SCHOOL", "LEREN", "WERKEN",
    "WATER", "EEN", "TWEE", "DRIE", "VRAAG",
]

# ── Smoothing-instellingen ────────────────────────────────────────────────────
STABIEL_FRAMES   = 24     # aantal frames in de buffer
STABIEL_DREMPEL  = 0.65   # minimale fractie overeenkomende frames


# ══════════════════════════════════════════════════════════════════════════════
#  Feature extractie
#  Input:  MediaPipe HandLandmarks object
#  Output: numpy arrays / scalaire meetwaarden
# ══════════════════════════════════════════════════════════════════════════════

def get_lm(hand_landmarks):
    """
    Zet MediaPipe landmarks om naar een (21, 3) numpy array.
    Indices 0-20 corresponderen met de standaard MediaPipe hand-topologie.
    """
    return np.array([[lm.x, lm.y, lm.z] for lm in hand_landmarks.landmark])


def finger_states(lm):
    """
    Bepaalt per vinger of hij gestrekt is.

    Methode:
      - Duim: vergelijk x-coördinaat tip vs. PIP (gespiegeld via cv2.flip)
      - Overige vingers: tip.y < pip.y  →  gestrekt (hogere y = lager in beeld)

    Geeft terug: [duim, wijsvinger, middelvinger, ringvinger, pink]  (bool)
    """
    tips = [4, 8, 12, 16, 20]
    pips = [3, 6, 10, 14, 18]
    thumb = lm[tips[0]][0] < lm[pips[0]][0]
    result = [thumb]
    for i in range(1, 5):
        result.append(lm[tips[i]][1] < lm[pips[i]][1])
    return result


def norm_lm(lm):
    """
    Normaliseer landmarks:
      - Centreer op pols (landmark 0)
      - Schaal op handgrootte (afstand pols → middelste knuckle, landmark 9)

    Maakt de classifier onafhankelijk van afstand tot camera.
    """
    origin = lm[0]
    scale  = np.linalg.norm(lm[9] - lm[0]) + 1e-6
    return (lm - origin) / scale


def tip_dist(lm, finger_i, finger_j):
    """
    Genormaliseerde afstand tussen twee vingertips.
    finger_i en finger_j zijn indices 0-4 (duim=0, pink=4).
    """
    tips = [4, 8, 12, 16, 20]
    hand_size = np.linalg.norm(lm[9] - lm[0]) + 1e-6
    return np.linalg.norm(lm[tips[finger_i]] - lm[tips[finger_j]]) / hand_size


def palm_open(lm):
    """
    Maat voor hoe open de hand is:
    gemiddelde afstand van de vier vingertips (excl. duim) tot de pols,
    genormaliseerd op handgrootte.
    Hoge waarde (~1.4+) = open hand; lage waarde (<0.7) = gesloten vuist.
    """
    hand_size = np.linalg.norm(lm[9] - lm[0]) + 1e-6
    return np.mean([np.linalg.norm(lm[t] - lm[0]) for t in [8, 12, 16, 20]]) / hand_size


def wrist_angle(lm):
    """
    Hoek van de hand t.o.v. verticaal (in graden).
    Berekend via de vector pols (0) → middelste knuckle (9).
    0° = rechtop; positief = gekanteld naar rechts.
    """
    v = lm[9] - lm[0]
    return np.degrees(np.arctan2(v[0], -v[1]))


# ══════════════════════════════════════════════════════════════════════════════
#  Smoothing buffer
#  Verzamelt de laatste N voorspellingen en geeft de meest stabiele terug.
# ══════════════════════════════════════════════════════════════════════════════

class GestureBuffer:
    """
    Houdt een rolling window van gebaar-voorspellingen bij.

    stable() geeft alleen een resultaat terug als één gebaar
    ten minste STABIEL_DREMPEL van de frames inneemt.
    Dit filtert korte/valse detecties weg.
    """

    def __init__(self, size=STABIEL_FRAMES):
        self.buf = deque(maxlen=size)

    def update(self, gesture):
        """Voeg nieuwste voorspelling toe (mag None zijn)."""
        self.buf.append(gesture)

    def stable(self):
        """
        Geeft (best_gesture, confidence) terug als stabiel,
        anders (None, confidence).
        """
        valid = [g for g in self.buf if g is not None]
        if not valid or len(self.buf) < self.buf.maxlen // 2:
            return None, 0.0
        best, freq = Counter(valid).most_common(1)[0]
        conf = freq / len(self.buf)
        return (best, conf) if conf >= STABIEL_DREMPEL else (None, conf)

    def reset(self):
        """Wis de buffer (bijv. na handverlies)."""
        self.buf.clear()


# ══════════════════════════════════════════════════════════════════════════════
#  NGT Gebaar-classifier  (25 woorden)
#
#  Aanpak: rule-based op basis van:
#    - finger_states  (welke vingers zijn gestrekt)
#    - tip_dist       (afstand tussen specifieke vingers)
#    - palm_open      (hoe open is de hand)
#    - wrist_angle    (kantelhoek hand)
#    - norm_lm        (genormaliseerde absolute posities)
#
#  Noot: echte NGT-gebaren zijn vaak dynamisch (beweging over tijd).
#  Deze implementatie benadert de statische handvorm die bij elk
#  gebaar hoort, geschikt voor demonstratiedoeleinden.
#
#  Uitbreiden: voeg een nieuwe if-regel toe onderaan deze functie
#  en voeg het woord toe aan WOORDENLIJST bovenaan dit bestand.
# ══════════════════════════════════════════════════════════════════════════════

def classify_ngt(hand_landmarks):
    """
    Classificeert een MediaPipe HandLandmarks object naar een NGT-woord.

    Parameters:
        hand_landmarks: mediapipe.framework.formats.landmark_pb2.NormalizedLandmarkList

    Returns:
        str  – herkend woord uit WOORDENLIJST
        None – geen herkenning
    """
    lm = get_lm(hand_landmarks)
    f  = finger_states(lm)
    th, ix, mi, ri, pi = f   # duim, wijs, midden, ring, pink

    # Hulpfuncties lokaal gebonden aan lm
    def td(i, j): return tip_dist(lm, i, j)
    po  = palm_open(lm)
    wa  = wrist_angle(lm)
    nlm = norm_lm(lm)

    # ── Begroeting / sociale gebaren ──────────────────────────────────────────

    # HALLO – open hand, alle vingers gespreid, palm naar voren
    if ix and mi and ri and pi and th and po > 1.4:
        return "HALLO"

    # DAG – vier vingers gestrekt, duim gebogen, zwaaibeweging
    if ix and mi and ri and pi and not th and po > 1.2:
        return "DAG"

    # TOT_ZIENS – V-teken: wijs + midden gestrekt, dicht bij elkaar
    if ix and mi and not ri and not pi and not th and td(1, 2) < 0.6:
        return "TOT_ZIENS"

    # BEDANKT – B-hand: vier vingers samen gestrekt, duim in
    if ix and mi and ri and pi and not th and po < 1.3:
        return "BEDANKT"

    # GRAAG_GEDAAN – duim omhoog (tip hoger dan eerste knuckle)
    if th and not ix and not mi and not ri and not pi:
        if lm[4][1] < lm[3][1]:
            return "GRAAG_GEDAAN"

    # ── Ja / Nee ──────────────────────────────────────────────────────────────

    # JA – gesloten vuist (alle vingers en duim ingevouwen)
    if not ix and not mi and not ri and not pi and not th:
        if po < 0.6:
            return "JA"

    # NEE – V wijd gespreid: wijs + midden ver uit elkaar
    if ix and mi and not ri and not pi and not th and td(1, 2) > 0.7:
        return "NEE"

    # ── Instructie-gebaren ────────────────────────────────────────────────────

    # HELP – open hand, palm omhoog (knuckle-y negatief na normalisatie)
    if ix and mi and ri and pi and th and po > 1.0 and nlm[9][1] < 0:
        return "HELP"

    # STOP – B-hand verticaal: vier vingers omhoog, hand rechtop
    if ix and mi and ri and pi and not th:
        if abs(wa) < 20:
            return "STOP"

    # GOED – duim zijwaarts/horizontaal
    if th and not ix and not mi and not ri and not pi:
        if lm[4][1] > lm[3][1]:
            return "GOED"

    # SLECHT – duim omlaag (tip lager dan tweede knuckle)
    if th and not ix and not mi and not ri and not pi:
        if lm[4][1] > lm[2][1] + 0.05:
            return "SLECHT"

    # MEER – O-hand: duim raakt wijsvinger en middelvinger
    if not ix and not mi and not ri and not pi:
        if td(0, 1) < 0.35 and td(0, 2) < 0.45:
            return "MEER"

    # MINDER – C-hand open: gebogen vingers, geen duim
    if not ix and not mi and not ri and not pi and not th:
        if po > 0.6:
            return "MINDER"

    # ── Persoonlijke voornaamwoorden ──────────────────────────────────────────

    # IK – wijsvinger wijst naar eigen lichaam (links van knuckle)
    if ix and not mi and not ri and not pi and not th:
        if lm[8][0] < lm[5][0] + 0.05:
            return "IK"

    # JIJ – wijsvinger wijst naar gesprekspartner (rechts van knuckle)
    if ix and not mi and not ri and not pi and not th:
        if lm[8][0] > lm[5][0] + 0.05:
            return "JIJ"

    # WIJ – open hand schuins gekanteld
    if ix and mi and ri and pi and th and po > 1.1 and abs(wa) > 25:
        return "WIJ"

    # ── Contextuele gebaren ───────────────────────────────────────────────────

    # NAAM – N-hand: duim gestrekt, wijs en midden dicht bij duim
    if not ix and not mi and not ri and not pi and th:
        if td(0, 1) < 0.4:
            return "NAAM"

    # SCHOOL – S-hand: vuist, duim aan de buitenkant
    if not ix and not mi and not ri and not pi and th:
        if lm[4][0] > lm[8][0]:
            return "SCHOOL"

    # LEREN – L-hand: duim + wijsvinger gestrekt (L-vorm)
    if ix and not mi and not ri and not pi and th:
        return "LEREN"

    # WERKEN – W-hand: wijs + midden + ring gestrekt
    if ix and mi and ri and not pi and not th:
        return "WERKEN"

    # ── Objecten ─────────────────────────────────────────────────────────────

    # WATER – W-hand variant met duim
    if ix and mi and ri and not pi and th:
        return "WATER"

    # ── Cijfers ──────────────────────────────────────────────────────────────

    # EEN – één wijsvinger omhoog
    if ix and not mi and not ri and not pi and not th:
        return "EEN"

    # TWEE – V-teken, vingers dicht bij elkaar
    if ix and mi and not ri and not pi and not th and td(1, 2) < 0.55:
        return "TWEE"

    # DRIE – wijs + midden + ring gestrekt
    if ix and mi and ri and not pi and not th:
        return "DRIE"

    # ── Overig ───────────────────────────────────────────────────────────────

    # VRAAG – Y-hand: duim + pink gestrekt
    if not ix and not mi and not ri and pi and th:
        return "VRAAG"

    # Geen herkenning
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  Multi-hand ondersteuning
#  Twee aparte GestureBuffers, één per hand (links / rechts)
# ══════════════════════════════════════════════════════════════════════════════

class MultiHandBuffer:
    """
    Beheert twee onafhankelijke GestureBuffers voor linker- en rechterhand.

    Gebruik:
        buf = MultiHandBuffer()
        buf.update("Left",  classify_ngt(hl_left))
        buf.update("Right", classify_ngt(hl_right))
        stable_l, conf_l = buf.stable("Left")
        stable_r, conf_r = buf.stable("Right")
        buf.reset("Left")   # hand verdwenen
    """

    def __init__(self):
        self._bufs = {
            "Left":  GestureBuffer(),
            "Right": GestureBuffer(),
        }

    def update(self, hand_label, gesture):
        self._bufs[hand_label].update(gesture)

    def stable(self, hand_label):
        return self._bufs[hand_label].stable()

    def reset(self, hand_label):
        self._bufs[hand_label].reset()

    def reset_all(self):
        for b in self._bufs.values():
            b.reset()
