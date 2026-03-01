"""
Groet-gebaren: HALLO, DAG, TOT_ZIENS, BEDANKT, GRAAG_GEDAAN
"""


def check_hallo(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and mi and ri and pi and th and po > 1.4:
        return "HALLO"


def check_dag(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and mi and ri and pi and not th and po > 1.2:
        return "DAG"


def check_tot_ziens(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and mi and not ri and not pi and not th and td(1, 2) < 0.6:
        return "TOT_ZIENS"


def check_bedankt(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if ix and mi and ri and pi and not th and po < 1.3:
        return "BEDANKT"


def check_graag_gedaan(lm, th, ix, mi, ri, pi, td, po, wa, nlm):
    if th and not ix and not mi and not ri and not pi:
        if lm[4][1] < lm[3][1]:
            return "GRAAG_GEDAAN"


SIGNS = [
    check_hallo,
    check_dag,
    check_tot_ziens,
    check_bedankt,
    check_graag_gedaan,
]
