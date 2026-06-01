# FL Studio ↔ Claude — Design

Control FL Studio from Claude (via an MCP server) on **Linux**, where FL Studio runs
under **Wine**. To our knowledge this is the first FL-Studio MCP integration that works
on Linux/Wine and exposes the **full controller API** (transport, mixer, channels,
plugins), not just piano-roll note generation.

## Why this is non-trivial on Linux/Wine

FL Studio has two Python scripting environments:

| Environment | API available | Triggerable from outside? |
|---|---|---|
| **Piano Roll scripts** (`.pyscript`) | only `flpianoroll` (notes) — sandboxed | yes (keyboard) |
| **MIDI Controller scripts** (`device_*.py`) | **full** (`transport`, `mixer`, `channels`, `plugins`, `general`, …) | only via incoming MIDI |

Under Wine the controller script's *continuous* callbacks (`OnIdle`, `OnUpdateBeatIndicator`)
never fire — the MIDI device is reported "already allocated" and the controller stays
inert. **But `OnMidiMsg` DOES fire on incoming MIDI**, and from it the full API is
available. That single fact is the foundation of this project.

## Architecture

```
Claude Code  ⇄  MCP server (Python, Linux)
                   1. write command.json   {id, op, args}   (shared filesystem; Wine sees it)
                   2. send one MIDI note to hw:4,0           (snd-virmidi → Wine → FL)
                          │
                          ▼
                 FL controller script  device_FLClaudeMCP.py
                   OnMidiMsg():  read command.json
                                 if id is new → dispatch op via full FL API
                                 write result.json {id, ok, result|error}
                          │
                   3. MCP polls result.json until id matches → returns to Claude
```

### Transport / channels
- **MIDI trigger**: the MCP writes raw MIDI bytes to the rawmidi device
  `/dev/snd/midiC4D0` (`hw:4,0`). NOT `aplaymidi` to the seq port — snd-virmidi forwards
  rawmidi writes to the seq port *output*, which is what Wine subscribes to.
- **Shared files**: live in the controller-script folder, visible to both sides:
  - Wine: `C:\users\<user>\Documents\Image-Line\FL Studio\Settings\Hardware\FLClaudeMCP\`
  - Linux: `~/.local/share/wineprefixes/flstudio/drive_c/users/<user>/.../FLClaudeMCP/`
- **Dedup**: `OnMidiMsg` fires ~4× per note (note-on/off + channel msgs). The script
  executes a command only when `command.json`'s `id` is greater than the last executed id.

## Components
- `fl_device/device_FLClaudeMCP.py` — the executor that runs inside FL.
- `mcp_server/fl_mcp_server.py` — the MCP server (stdio) registered with Claude Code.
- `setup/` — snd-virmidi persistence, installer.
- `docs/` — this design + usage.

## Known limits
- Note *writing* into a pattern is better done with a Piano-Roll script (sandboxed but
  works); the controller path is for DAW control. (Future module.)
- Requires the user to assign the controller script to a virmidi input in FL once (UI).
- FL must be running with the controller assigned; snd-virmidi must be loaded.
- Probed (2026-06-01): the controller API exposes per-step pitch+velocity
  (`channels.getStepParam(step, param, offset, startPos)` on the *selected* channel;
  `midi.pPitch=0`, `midi.pVelocity=1`), channel types, plugin names, and mixer
  routing — but NOT key/scale (reported as `null`) and NOT piano-roll notes.
- Reading piano-roll notes needs a piano-roll script (`flpianoroll`), launched
  manually from the Piano Roll menu. That sandbox can only write to FL's
  "Piano roll scripts" folder, so `notes_export.json` lands there (not the Hardware
  folder); the MCP server reads it from there.
