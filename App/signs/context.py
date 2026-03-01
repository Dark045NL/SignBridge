"""
Contextgebaren: NAAM, SCHOOL, LEREN, WERKEN, WATER
"""


def check_naam(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if not ix and not mi and not ri and not pi and th:
        if td(0, 1) < 0.4:
            return "NAAM"


def check_school(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if not ix and not mi and not ri and not pi and th:
        if lm[4][0] > lm[8][0]:
            return "SCHOOL"


def check_leren(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and not mi and not ri and not pi and th:
        return "LEREN"


def check_werken(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and mi and ri and not pi and not th:
        return "WERKEN"


def check_water(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and mi and ri and not pi and th:
        return "WATER"


SIGNS = [
    check_naam,
    check_school,
    check_leren,
    check_werken,
    check_water,
]
