"""
Kwaliteitsgebaren: GOED, SLECHT, MEER, MINDER
"""


def check_goed(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if th and not ix and not mi and not ri and not pi:
        if lm[4][1] > lm[3][1]:
            return "GOED"


def check_slecht(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if th and not ix and not mi and not ri and not pi:
        if lm[4][1] > lm[2][1] + 0.05:
            return "SLECHT"


def check_meer(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if not ix and not mi and not ri and not pi:
        if td(0, 1) < 0.35 and td(0, 2) < 0.45:
            return "MEER"


def check_minder(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if not ix and not mi and not ri and not pi and not th:
        if po > 0.6:
            return "MINDER"


SIGNS = [
    check_goed,
    check_slecht,
    check_meer,
    check_minder,
]
