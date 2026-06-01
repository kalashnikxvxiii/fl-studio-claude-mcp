# fl-studio-claude-mcp

Control **FL Studio** from **Claude** through an MCP server — on **Linux**, with FL Studio
running under **Wine**.

Existing FL-Studio MCP integrations target Windows/macOS and mostly do piano-roll note
generation. This one runs on **Linux/Wine** and drives FL's **full controller API**
(transport, mixer, channels, plugins) by exploiting the one scripting callback that still
works under Wine: `OnMidiMsg`.

> Status: early. Transport, mixer and channel control work end-to-end. See
> [docs/DESIGN.md](docs/DESIGN.md) for how/why it works.

## How it works (short)

```
Claude ⇄ MCP server (Linux) ──command.json──▶ shared folder ◀──read── FL controller script
                            └──MIDI note──▶ hw:4,0 ▶ Wine ▶ OnMidiMsg() ──executes──┘
                            ◀─────────────── result.json ◀──write──────────────────┘
```

The MCP server writes a command, pokes FL with a single MIDI note (which fires the
controller script's `OnMidiMsg`), the script runs the command via the full FL API and
writes the result back. Files are shared because Wine and Linux see the same filesystem.

## Requirements

- FL Studio running under Wine on Linux (this repo assumes a prefix at
  `~/.local/share/wineprefixes/flstudio`; pass yours to the installer).
- `snd-virmidi` (ALSA virtual MIDI), your user in the `audio` group.
- Python 3.10+, Claude Code CLI.

## Install

```bash
./setup/install.sh [WINEPREFIX]
```

This copies the controller script into FL, creates a venv with the `mcp` SDK, makes
`snd-virmidi` persistent, and registers the MCP server with Claude Code.

**One manual step in FL** (Wine MIDI can't be scripted): `Options > MIDI settings`, enable
a `Virtual Raw MIDI` input, set its **Controller type** to **FLClaudeMCP**.

Then, in Claude: *"run fl_ping"* — you should get FL's version, tempo and play state.

## Tools

| Tool | Action |
|---|---|
| `fl_ping` | version + tempo + play state |
| `fl_get_project` | full project read: context + channels (steps w/ pitch+velocity) + mixer |
| `fl_read_notes` | read notes exported by the Export Notes piano-roll script |
| `fl_write_notes(notes, mode, channel, pattern)` | write notes into the open clip (replace/merge); pre-selects channel/pattern |
| `fl_search_library(query, kind, plugin, limit, refresh)` | search installed instruments/effects/presets/samples by name/plugin/category |
| `fl_get_state` | deprecated alias of `fl_get_project` |
| `fl_play` / `fl_stop` / `fl_record` | transport |
| `fl_set_tempo(bpm)` | set tempo |
| `fl_mixer_set_volume(track, volume)` | mixer volume |
| `fl_mixer_set_pan(track, pan)` | mixer pan |
| `fl_mixer_mute(track)` / `fl_mixer_solo(track)` | mute / solo |
| `fl_channel_select(index)` | select a channel |
| `fl_pattern_select(index)` | jump to a pattern |
| `fl_set_steps` / `fl_get_steps` / `fl_clear_steps` | step sequencer |

### Reading piano-roll notes

Controller scripts can't read piano-roll notes directly. To let Claude see them:
1. In FL, open the clip in the **Piano Roll**.
2. Menu (hamburger) > **Tools** > **Scripting** > **Export Notes**.
3. Ask Claude to call `fl_read_notes`.

`setup/install.sh` copies `Export Notes.pyscript` into FL's *Piano roll scripts* folder.
The export is written there (the piano-roll sandbox can't write elsewhere); the MCP
server reads it from that folder.

### Writing piano-roll notes

1. Ask Claude to compose; it calls `fl_write_notes` (optionally pre-selecting a
   channel/pattern) and tells you what to open.
2. Open that clip in the **Piano Roll**.
3. Menu (hamburger) > **Tools** > **Scripting** > **Import Notes**.

`mode="replace"` rewrites the clip; `mode="merge"` adds, skipping exact duplicates
(same pitch + start). Notes are positioned in beats and converted with the clip's PPQ.

### Finding sounds

`fl_search_library` indexes FL's on-disk library (plugin database, ~7k instrument
presets, factory samples) by path metadata and caches it. Ask Claude for "a reese bass"
or "a reverb"; it searches, and when several candidates fit it proposes a short list
with reasons rather than guessing. Loading the chosen sound into FL is still manual
(the controller API can't load plugins). First search builds `library_index.json`;
pass `refresh=True` after you install new content.

## Layout

```
fl_device/device_FLClaudeMCP.py   the executor that runs inside FL
mcp_server/fl_mcp_server.py       the MCP server (stdio)
setup/                            installer + snd-virmidi persistence
docs/DESIGN.md                    architecture & the Wine constraints
```

## License

MIT
