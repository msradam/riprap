"""FEMA zone X ("an area of minimal flood hazard") reads as an absence.

Live, "Are the subway entrances near 1 East 161st Street, Bronx in a flood
scenario?" got no answer: the model led with "no" on the register (0 of
8 entrances inside Sandy or the DEP scenario) and cited the FEMA zone X
sentence beside it, and the lead rule read zone X as a result."""
from riprap.core.burr import answer_checks as ac

ZONE_X = ("This address sits in FEMA flood zone X (an area of minimal flood hazard), per NFHL FIRM panel "
          "3604970083F, effective 2007.")
ZONE_AE = "This address sits in FEMA flood zone AE (a Special Flood Hazard Area), per NFHL FIRM panel 3604970192F."
REGISTER = ("18 MTA subway entrances within 800 m of this address; of the nearest 8: 0 inside the 2012 Sandy "
            "inundation extent and 0 inside the DEP extreme stormwater scenario (2080 sea-level rise)")


def test_zone_x_is_an_absence_and_zone_ae_a_result():
    assert not ac.reports_result(ZONE_X)
    assert ac.reports_result(ZONE_AE)


def test_a_no_on_the_register_beside_zone_x_holds():
    docs = {"fema_nfhl": ZONE_X, "mta_entrance_exposure": REGISTER}
    q = "Are the subway entrances near 1 East 161st Street, Bronx in a flood scenario?"
    assert ac.check_lead("no", ["mta_entrance_exposure", "fema_nfhl"], q, docs) == []
    assert ac.check_lead("no", ["mta_entrance_exposure", "fema_nfhl"], q, {**docs, "fema_nfhl": ZONE_AE})
