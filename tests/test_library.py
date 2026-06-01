from mcp_server.library import classify_fst, classify_wav


def test_classify_fst_instrument_preset():
    p = "/x/Data/Patches/Plugin presets/Generators/Sytrus/Bass/Reese.fst"
    r = classify_fst(p)
    assert r["name"] == "Reese"
    assert r["plugin"] == "Sytrus"
    assert r["category"] == "Bass"
    assert r["kind"] == "preset"


def test_classify_fst_plugin_database_generator():
    p = "/x/Data/System/Plugin databases/Plugin database (simple)/Generators/Synth classic/FLEX.fst"
    r = classify_fst(p)
    assert r["name"] == "FLEX"
    assert r["kind"] == "instrument"
    assert r["category"] == "Synth classic"


def test_classify_fst_plugin_database_effect():
    p = "/x/Data/System/Plugin databases/Plugin database (simple)/Effects/Delay reverb/Fruity Reeverb 2.fst"
    r = classify_fst(p)
    assert r["name"] == "Fruity Reeverb 2"
    assert r["kind"] == "effect"
    assert r["category"] == "Delay reverb"


def test_classify_wav():
    p = "/x/Data/Patches/Packs/Drums/Kicks/Kick 01.wav"
    r = classify_wav(p)
    assert r["name"] == "Kick 01"
    assert r["kind"] == "sample"
    assert r["category"] == "Kicks"
    assert r["plugin"] is None


import os
from mcp_server.library import scan_library, search


def _make_tree(tmp_path):
    files = [
        "Data/System/Plugin databases/Plugin database (simple)/Generators/Synth classic/FLEX.fst",
        "Data/System/Plugin databases/Plugin database (simple)/Effects/Delay reverb/Fruity Reeverb 2.fst",
        "Data/Patches/Plugin presets/Generators/Sytrus/Bass/Reese.fst",
        "Data/Patches/Plugin presets/Generators/Sytrus/Lead/Supersaw.fst",
        "Data/Patches/Packs/Drums/Kicks/Kick 01.wav",
    ]
    for f in files:
        full = tmp_path / f
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("x")
    return [str(tmp_path / "Data")]


def test_scan_library_counts(tmp_path):
    roots = _make_tree(tmp_path)
    index = scan_library(roots)
    kinds = sorted(r["kind"] for r in index)
    assert kinds == ["effect", "instrument", "preset", "preset", "sample"]


def test_search_filters_and_ranks(tmp_path):
    index = scan_library(_make_tree(tmp_path))
    res = search(index, "reverb")
    assert res[0]["name"] == "Fruity Reeverb 2"
    res2 = search(index, "", kind="sample")
    assert len(res2) == 1 and res2[0]["name"] == "Kick 01"
    res3 = search(index, "supersaw", plugin="Sytrus")
    assert res3[0]["name"] == "Supersaw"


def test_search_missing_root_is_skipped(tmp_path):
    index = scan_library([str(tmp_path / "nonexistent")])
    assert index == []
