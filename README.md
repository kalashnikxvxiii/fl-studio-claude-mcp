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
| `fl_get_state` | full snapshot (mixer tracks, channels, …) |
| `fl_play` / `fl_stop` / `fl_record` | transport |
| `fl_set_tempo(bpm)` | set tempo |
| `fl_mixer_set_volume(track, volume)` | mixer volume |
| `fl_mixer_set_pan(track, pan)` | mixer pan |
| `fl_mixer_mute(track)` / `fl_mixer_solo(track)` | mute / solo |
| `fl_channel_select(index)` | select a channel |

## Layout

```
fl_device/device_FLClaudeMCP.py   the executor that runs inside FL
mcp_server/fl_mcp_server.py       the MCP server (stdio)
setup/                            installer + snd-virmidi persistence
docs/DESIGN.md                    architecture & the Wine constraints
```

## License

MIT
