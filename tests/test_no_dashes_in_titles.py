"""Source titles reach the page: no em or en dash in a manifest's visible
fields (the project's prose rule), and every manifest still parses."""

import glob

import yaml

VISIBLE = ("title", "source_name", "citation", "short", "template", "answers", "license", "message", "label")


def _strings(node, key=None):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _strings(v, k)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v, key)
    elif isinstance(node, str) and key in VISIBLE:
        yield key, node


def test_manifest_visible_text_has_no_em_or_en_dash():
    bad = []
    for p in glob.glob("deployments/*/manifests/*.yaml"):
        for k, s in _strings(yaml.safe_load(open(p))):
            if "—" in s or "–" in s:
                bad.append(f"{p}: {k}: {s[:60]}")
    assert not bad, bad
