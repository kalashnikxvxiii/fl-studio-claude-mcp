from mcp_server.preflight import check_environment


def _run(midi_exists, fl_running, ping_result):
    return check_environment(
        midi_dev="/dev/snd/midiC4D0",
        fl_proc="FL64.exe",
        ping_fn=lambda: ping_result,
        _midi_exists=lambda p: midi_exists,
        _proc_running=lambda n: fl_running,
    )


def test_virmidi_missing():
    r = _run(False, False, None)
    assert r["ready"] is False
    assert r["checks"][0]["name"] == "virmidi" and r["checks"][0]["ok"] is False
    assert "modprobe" in r["hint"]


def test_fl_not_running():
    r = _run(True, False, None)
    assert r["ready"] is False
    assert r["checks"][1]["name"] == "fl_running" and r["checks"][1]["ok"] is False
    assert "flstudio" in r["hint"]


def test_controller_not_responding():
    r = _run(True, True, None)        # ping returns None -> no response
    assert r["ready"] is False
    assert r["checks"][2]["name"] == "controller" and r["checks"][2]["ok"] is False
    assert "Controller type" in r["hint"]


def test_all_ready():
    r = _run(True, True, {"version": 40, "tempo": 126.0})
    assert r["ready"] is True
    assert all(c["ok"] for c in r["checks"])
    assert "ready" in r["hint"].lower()
