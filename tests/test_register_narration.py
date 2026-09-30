"""Register sentences say what was counted. The schools and NYCHA
registers hold only exposed assets, so their count must not read as every
asset in range; the MTA and hospital layers hold every asset, so their
count is every asset in range even when only the nearest are checked."""

from riprap.core.burr.answer_checks import _register_counts

BROOKLYN_HEIGHTS = (40.6905, -73.9935)  # 189 Atlantic Avenue
ROCKAWAY = (40.5947, -73.7668)


def test_helper_plural_scope_and_nearest():
    from app.registers._loader import narrative

    one = narrative("hospital", "hospitals", 1, 3000, 0, 0)
    assert one.startswith("1 hospital within 3000 m of this address: 0 inside")
    capped = narrative("MTA subway entrance", "MTA subway entrances", 43, 800, 1, 2, n_checked=8)
    assert capped.startswith("43 MTA subway entrances within 800 m of this address; of the nearest 8: 1 inside")
    assert "nearest" not in narrative("hospital", "hospitals", 3, 3000, 0, 0, n_checked=3)
    assert _register_counts(capped + ".") == (43, 1, 2)  # the answer checks still parse it


def test_exposed_only_register_names_its_scope():
    from app.registers import exposure

    s = exposure.summary_for_point(*BROOKLYN_HEIGHTS, "doe_schools")
    assert s["n_schools"] == 0
    assert s["narrative"].startswith("0 flood-exposed NYC DOE schools within 1500 m of this address "
                                     "(the register lists only schools found inside the 2012 Sandy")
    assert "not every school" in s["narrative"]
    assert _register_counts(s["narrative"] + ".") == (0, 0, 0)
    n = exposure.summary_for_point(*ROCKAWAY, "nycha")
    assert "flood-exposed NYCHA development" in n["narrative"] and "not every development" in n["narrative"]


def test_exposed_register_counts_every_row_in_range_and_lists_the_nearest():
    from app.registers import exposure

    s = exposure.summary_for_point(*ROCKAWAY, "doe_schools", radius_m=3000, max_n=2)
    assert s["n_schools"] > 2 and len(s["schools"]) == 2
    assert s["narrative"].startswith(f"{s['n_schools']} flood-exposed NYC DOE schools")


def test_full_layer_count_is_every_entrance_in_range():
    from app.registers import exposure

    s = exposure.summary_for_point(*BROOKLYN_HEIGHTS, "mta_entrances")
    assert s["n_entrances"] > s["n_checked"] == len(s["entrances"]) == 8
    assert f"; of the nearest {s['n_checked']}:" in s["narrative"]
