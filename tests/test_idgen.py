import os
from mcp_server.idgen import next_id


def test_next_id_creates_file_and_returns_int(tmp_path):
    cp = str(tmp_path / "id_counter.txt")
    v = next_id(cp)
    assert isinstance(v, int) and v > 0
    assert os.path.exists(cp)


def test_next_id_strictly_increasing(tmp_path):
    cp = str(tmp_path / "id_counter.txt")
    a = next_id(cp)
    b = next_id(cp)
    c = next_id(cp)
    assert a < b < c


def test_next_id_persists_across_calls(tmp_path):
    cp = str(tmp_path / "id_counter.txt")
    next_id(cp); next_id(cp)
    with open(cp) as f:
        stored = int(f.read().strip())
    nxt = next_id(cp)
    assert nxt == stored + 1


def test_next_id_corrupt_file_falls_back(tmp_path):
    cp = str(tmp_path / "id_counter.txt")
    with open(cp, "w") as f:
        f.write("not-an-int")
    v = next_id(cp)               # must not raise
    assert isinstance(v, int) and v > 0
