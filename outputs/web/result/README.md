# Auto-eject A1

A web app for the **Bambu Lab A1 only** (256 × 256 mm bed). It turns one part into
a supervised loop of *N* prints, pushing each finished part off the bed with the
Factorian Designs end block.

The Python core lives in `autoeject/` (no web imports); the FastAPI app and static
UI live in `app/`; tests live in `tests/`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/check` | Measure an STL and return pass/warn/fail with reasons. |
| POST | `/api/build` | Slice an STL (or patch a sliced `.gcode.3mf`) and return an N-copy `.gcode.3mf`. |
| POST | `/api/simulate` | Replay the eject moves and report pushes, collisions and misses. |

Multipart uploads use the field name `file`; the iteration count is the form
field `n`. Everything is synchronous and A1-only. A failing verdict blocks the
download; a warning is shown but does not block.

> **Supervised use only.** The heat/cool cycle does not prove that the part has
> released. Inspect the bed and the exit path between copies; do not run the loop
> unattended.

## Run locally

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Open <http://127.0.0.1:8000/> and upload an STL, or a pre-sliced `.gcode.3mf`.
Run the tests with:

```bash
uv run pytest -q
```

To slice in-process, point the app at a BambuStudio CLI and its installed A1
profiles:

```bash
export BAMBU_CLI=/path/to/bambustudio/AppRun
export BAMBU_PROFILE_ROOT=/path/to/bambustudio/resources/profiles/BBL
```

Without `BAMBU_CLI` the STL path returns a synchronous error and directs you to
the pre-sliced fallback.

### Export a sliced plate from Bambu Studio

1. Open the part in Bambu Studio, select the **Bambu Lab A1** printer and a
   process/filament profile, and slice it.
2. Use **File → Export → Export plate sliced file** (or the plate context menu
   **Export plate sliced file…**) and save the `.gcode.3mf`.
3. Upload that file to the app. Only the stock end block, between
   `; MACHINE_END_GCODE_START` and `; EXECUTABLE_BLOCK_END`, is replaced; the
   `Metadata/plate_1.gcode.md5` companion is recomputed.

## Deploy

`railway.toml` builds the `Dockerfile` and starts
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`. The Dockerfile leaves the
BambuStudio CLI install block commented out, so a plain image build does not
silently download an unpinned slicer.
