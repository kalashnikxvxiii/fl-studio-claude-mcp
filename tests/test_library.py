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
