"""
Getalgebaren: EEN, TWEE, DRIE
"""


def check_een(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and not mi and not ri and not pi and not th:
        return "EEN"


def check_twee(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and mi and not ri and not pi and not th and td(1, 2) < 0.55:
        return "TWEE"


def check_drie(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and mi and ri and not pi and not th:
        return "DRIE"


SIGNS = [
    check_een,
    check_twee,
    check_drie,
]
