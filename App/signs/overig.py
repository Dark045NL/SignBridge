"""
Overige gebaren: VRAAG
"""


def check_vraag(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if not ix and not mi and not ri and pi and th:
        return "VRAAG"


SIGNS = [
    check_vraag,
]
