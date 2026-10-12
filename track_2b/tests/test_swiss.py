"""The Swiss topology: its file loads, the names table covers its nodes, the stream speaks its names."""

import json

import mixed3
from spec import Spec, load_topology, validate
from swiss import build, names


def test_names_cover_the_topology_and_rows_resolve():
    topology = load_topology("swiss")
    table = names()
    assert set(table) == set(topology.nodes) and len(topology.nodes) == 24
    assert all(forms.get(lang) for forms in table.values() for lang in ("de", "fr", "it", "en"))
    rows = build(seed=1)
    assert set(rows) == {"v3_swiss_en", "v3_swiss_de", "v3_swiss_fr", "v3_swiss_it"}
    for items in rows.values():
        assert len(items) > 200
        for row in items:
            spec = validate(Spec.from_json(row["expect"]), topology)
            assert spec.applies, (row["text"], spec.status)
    german = " ".join(r["text"] for r in rows["v3_swiss_de"])
    assert "Genf" in german and "Geneva" not in german
    assert any("Ginevra" in r["text"] for r in rows["v3_swiss_it"])


def test_stream_names_follow_the_topology():
    mixed3.set_topology("swiss")
    try:
        assert mixed3.NAMES["fr"]["Genève"] == "Genève" and mixed3.NAMES["en"]["Genève"] == "Geneva"
        assert "Bern" not in mixed3.OUTSIDE and "Milan" in mixed3.OUTSIDE
        assert mixed3.render("via {v}", {"v": "Zürich"}, "it") == "via Zurigo"
    finally:
        mixed3.set_topology("nobel-eu")
    assert "Bern" in mixed3.OUTSIDE and mixed3.render("via {v}", {"v": "Zurich"}, "de") == "via Zürich"
    assert json.loads(json.dumps(mixed3.NAMES))  # plain data
