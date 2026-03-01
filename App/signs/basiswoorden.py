"""
Basiswoorden: JA, NEE, HELP, STOP
"""


def check_ja(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if not ix and not mi and not ri and not pi and not th:
        if po < 0.6:
            return "JA"


def check_nee(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and mi and not ri and not pi and not th and td(1, 2) > 0.7:
        return "NEE"


def check_help(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and mi and ri and pi and th and po > 1.0 and nlm[9][1] < 0:
        return "HELP"


def check_stop(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and mi and ri and pi and not th:
        if abs(wa) < 20:
            return "STOP"


SIGNS = [
    check_ja,
    check_nee,
    check_help,
    check_stop,
]
