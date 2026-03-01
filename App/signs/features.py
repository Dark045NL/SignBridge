"""
Feature extractie voor NGT gebaar-herkenning.
Zet ruwe MediaPipe landmarks om naar meetbare kenmerken.
"""

import numpy as np


def get_lm(hl):
    """Geeft een (21, 3) array van hand-landmarks terug."""
    return np.array([[lm.x, lm.y, lm.z] for lm in hl.landmark])


def finger_states(lm):
    """Geeft [duim, wijs, middel, ring, pink] terug als booleans (uitgestrekt=True)."""
    tips  = [4, 8, 12, 16, 20]
    pips  = [3, 6, 10, 14, 18]
    thumb = lm[tips[0]][0] < lm[pips[0]][0]
    r     = [thumb]
    for i in range(1, 5):
        r.append(lm[tips[i]][1] < lm[pips[i]][1])
    return r


def norm_lm(lm):
    """Normaliseert landmarks relatief aan de pols (landmark 0)."""
    origin = lm[0]
    scale  = np.linalg.norm(lm[9] - lm[0]) + 1e-6
    return (lm - origin) / scale


def tip_dist(lm, i, j):
    """Afstand tussen vingertop i en j, genormaliseerd op handgrootte."""
    tips = [4, 8, 12, 16, 20]
    hs   = np.linalg.norm(lm[9] - lm[0]) + 1e-6
    return np.linalg.norm(lm[tips[i]] - lm[tips[j]]) / hs


def palm_open(lm):
    """Mate van openheid van de hand (groter = meer open)."""
    tips = [8, 12, 16, 20]
    hs   = np.linalg.norm(lm[9] - lm[0]) + 1e-6
    return np.mean([np.linalg.norm(lm[t] - lm[0]) for t in tips]) / hs


def wrist_angle(lm):
    """Hoek van de pols in graden (rotatie links/rechts)."""
    v = lm[9] - lm[0]
    return np.degrees(np.arctan2(v[0], -v[1]))
