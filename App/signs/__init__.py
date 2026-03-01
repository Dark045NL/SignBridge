"""
Signs-pakket voor SignBridge NGT gebaar-classificatie.

Mapstructuur:
    features.py        – feature extractie (landmarks, hoeken, afstanden)
    groeten.py         – HALLO, DAG, TOT_ZIENS, BEDANKT, GRAAG_GEDAAN
    basiswoorden.py    – JA, NEE, HELP, STOP
    kwaliteit.py       – GOED, SLECHT, MEER, MINDER
    voornaamwoorden.py – IK, JIJ, WIJ
    context.py         – NAAM, SCHOOL, LEREN, WERKEN, WATER
    getallen.py        – EEN, TWEE, DRIE
    overig.py          – VRAAG
"""

from .features import (
    get_lm,
    finger_states,
    norm_lm,
    tip_dist,
    palm_open,
    wrist_angle,
)
from .groeten        import SIGNS as _GROETEN
from .basiswoorden   import SIGNS as _BASISWOORDEN
from .kwaliteit      import SIGNS as _KWALITEIT
from .voornaamwoorden import SIGNS as _VOORNAAMWOORDEN
from .context        import SIGNS as _CONTEXT
from .getallen       import SIGNS as _GETALLEN
from .overig         import SIGNS as _OVERIG

# Volgorde is identiek aan de originele if-keten in classify_ngt
_ALL_SIGNS = (
    _GROETEN
    + _BASISWOORDEN
    + _KWALITEIT
    + _VOORNAAMWOORDEN
    + _CONTEXT
    + _GETALLEN
    + _OVERIG
)


def classify_ngt(hl):
    """
    Classificeert een MediaPipe hand-landmark object naar een NGT-gebaar.
    Geeft de naam van het gebaar terug, of None als er geen match is.
    """
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
