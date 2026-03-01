"""
Voornaamwoord-gebaren: IK, JIJ, WIJ
"""


def check_ik(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and not mi and not ri and not pi and not th:
        if lm[8][0] < lm[5][0] + 0.05:
            return "IK"


def check_jij(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and not mi and not ri and not pi and not th:
        if lm[8][0] > lm[5][0] + 0.05:
            return "JIJ"


def check_wij(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and mi and ri and pi and th and po > 1.1 and abs(wa) > 25:
        return "WIJ"


SIGNS = [
    check_ik,
    check_jij,
    check_wij,
]
