# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Sound-activated audio recorder for Raspberry Pi / Linux systems. `auto_record.py` monitors the
default audio input, starts a WAV recording when noise crosses a calibrated threshold, and stops
after a period of silence. `web_server.py` is a small FastAPI app that lists, plays, downloads,
deletes, and classifies the resulting recordings.

## Setup

```
sudo apt install portaudio19-dev pip python3-venv
python3 -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
```

`wav2csv.py` additionally requires `numpy` and `matplotlib` (not in requirements.txt):
```
pip install numpy matplotlib
```

## Running

```
source ./venv/bin/activate
python auto_record.py [debug] [calibrate | disabled]
python web_server.py          # serves UI at http://localhost:3000
```

- `calibrate`: run interactive threshold calibration (needs 2s quiet, then a 0.5s trigger-level
  noise) and writes `data/calibrated`. Do this once per environment/device before relying on
  auto-triggering.
- `disabled`: start the recorder without recording enabled (toggled at runtime via `data/record`
  file presence, or via the web UI button).
- `debug`: also logs to stdout in addition to the log file.

There is no test suite in this repository.

### Analyzing recordings

`wav2csv.py` is meant to be run interactively (`python -i wav2csv.py <wav file>`) to inspect a
recording: it writes a `.csv` of raw samples and leaves the data in a numpy array for plotting
(`plot_array`, `plot_stairs`) via `matplotlib`.

## Architecture

**State is filesystem-based, not in a database or shared process.** `auto_record.py` and
`web_server.py` are independent processes (run as separate systemd units in production) that
coordinate purely through files in `DATA_DIR` (`data/`):

- `data/record` — presence toggles recording on/off. Both the recorder (reads it every audio
  block) and the web server (writes it on button press) touch this file. This is the only
  cross-process communication mechanism in the system.
- `data/calibrated` — single float noise threshold, written by `auto_record.py calibrate`, read
  at recorder startup.
- `data/<timestamp>.wav` + `data/<timestamp>.json` — a completed recording and its metadata
  (`sound_file`, `basename`, `json_file`, `timestamp`, `length`). The web server treats the JSON
  files as its entire index — `get_file_list()` in `web_server.py` just globs `*.json` in
  `DATA_DIR` and sorts by embedded timestamp. There is no separate database.
- `data/<class>/` (e.g. `airplane`, `dog`, `siren`) — classification is done by moving the wav+json
  pair out of `data/` into a subdirectory (`post_file` action handler in `web_server.py`); classes
  are hardcoded as a list in that handler, not configurable.
- Recordings are written to a `.tmp` file first and only renamed to `.wav` (with a `.json`
  sidecar written) once they reach the minimum length (2s) in `ensure_close_file`; shorter
  recordings are discarded. Never assume a `.tmp` file is a stable recording.

**Recorder state machine** (`AutoRecordSession` in `auto_record.py`): two states, `listening` and
`recording`, driven by a `collections.deque` of `AudioDataBlock`s read from PyAudio in fixed-size
blocks (`BLOCK_SIZE` frames at `RATE` 8kHz, 2 channel, 16-bit). Key thresholds are counts of
consecutive noisy/silent blocks, not wall-clock timers:
- 2-of-3 recent blocks noisy → transition listening → recording (`run_listen_logic`).
- silence sustained past `SILENCE_WRITE_DURATION` → stop writing buffered audio but keep waiting.
- silence sustained past `SILENCE_TRIGGER_DURATION` (10s) → transition recording → listening and
  finalize the file (`run_record_logic`).
When changing timing behavior, adjust the block-count constants near the top of the file — they
are all derived from `RATE`/`BLOCK_SIZE`, not raw seconds.

**Web server** (`web_server.py`) is a single-file FastAPI app rendering one Jinja2 template
(`main.html` in the repo root — `Jinja2Templates(directory=".")`). It imports `auto_record.py`
directly to reuse `DATA_DIR`/`RECORD_ENABLED_FILE` constants and the `AudioDataBlock` class (also
used by `wav2csv.py`) — these three files should be kept in sync when changing `DATA_DIR` layout
or the recording metadata schema. `clean_files()` runs once at server startup to prune JSON
sidecars whose WAV file is missing; it is not run continuously.

## Deployment

Runs via systemd (`auto_record.service`, `auto_record_server.service`) for boot-time start. The
default audio input device can differ between an interactive desktop session and systemd context
(and on Raspberry Pi may need `/etc/asound.conf` configuration) — if audio capture works from the
CLI but not as a service, check the device selection logic in `start_session()` and consult
`auto_record_log.txt`.
