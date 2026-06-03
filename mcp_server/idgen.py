"""Persistent monotonic id counter — survives server restarts so command ids never
collide with the device's last-seen id. Pure, FL-independent."""
import os
import time


def next_id(counter_path):
    """Return the next id (strictly increasing across calls and restarts) and persist
    it. Missing/corrupt counter file → seed from a millisecond timestamp."""
    try:
        with open(counter_path) as f:
            cur = int(f.read().strip())
    except (OSError, ValueError):
        cur = int(time.time() * 1000)
    nxt = cur + 1
    try:
        os.makedirs(os.path.dirname(counter_path), exist_ok=True)
        with open(counter_path, "w") as f:
            f.write(str(nxt))
    except OSError:
        pass
    return nxt
