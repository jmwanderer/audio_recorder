"""
A simple fast-api based web server to serve audio files.

- one main.html page with
  * A list of audio files
  * The recording enabled status
  * A button to toggel recording enabled
"""
import datetime
import json
import logging
import logging.handlers
import os
from typing import Annotated
from typing import Any, Optional, Union

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates
import uvicorn

import auto_record

# Initialize fast api and logging
app = FastAPI()
templates = Jinja2Templates(directory=".")
logger = logging.getLogger("uvicorn.error")

# Category subdirectories under DATA_DIR that a recording can be classified into
CLASSES = [ "airplane", "dog", "siren", "door", "snore" ]


def clean_files():
    for entry in os.listdir(auto_record.DATA_DIR):
        if entry.endswith(".json"):
            path = os.path.join(auto_record.DATA_DIR, entry)
            f = open(path, 'r')
            info = json.loads(f.read())
            f.close()
            sound_path = os.path.join(auto_record.DATA_DIR, info["sound_file"])
            if not os.path.isfile(sound_path):
                os.remove(path)
    
def get_file_list():
    """
    Read the contents of the JSON information files in the data directory
    and its category subdirectories, and return list of dictionary elements
    sorted by the timestamp.
    """
    result = []
    logger.debug("get file list")
    dirs = [auto_record.DATA_DIR] + [
        os.path.join(auto_record.DATA_DIR, c) for c in CLASSES
    ]
    for dir_path in dirs:
        if not os.path.isdir(dir_path):
            continue
        for entry in os.listdir(dir_path):
            if entry.endswith(".json"):
                path = os.path.join(dir_path, entry)
                f = open(path, 'r')
                info = json.loads(f.read())
                f.close()

                # Change timestamp from text to datetime.dateime
                info["timestamp"] = datetime.datetime.fromisoformat(info["timestamp"])

                # Record where the file actually lives, based on where it was
                # found. Not persisted - the "category" field, not this, is
                # what's saved to the sidecar.
                info["dir"] = dir_path

                # A category is confirmed once the file has actually been
                # moved into that category's subdirectory. Until then
                # (e.g. a category set some other way, without a move)
                # it's only tentative.
                if info.get("category"):
                    info["confirmed"] = dir_path == os.path.join(
                        auto_record.DATA_DIR, info["category"])

                result.append(info)
    result.sort(key=lambda e: e["timestamp"], reverse=True)
    return result

def lookup_file(basename: str) -> Union[dict[str, Any], None]:
    """
    Find a wav file for basename, return the wav filename
    Return None if not found
    """
    for entry in get_file_list():
        if entry["basename"] == basename:
            return entry
    return None


def get_record_setting() -> bool: 
    """
    Return TRUE if recording
    """
    path = os.path.join(auto_record.DATA_DIR, auto_record.RECORD_ENABLED_FILE)
    return os.path.isfile(path)

def set_record_setting(recording: bool):
    """
    Set the recording status
    """
    path = os.path.join(auto_record.DATA_DIR, auto_record.RECORD_ENABLED_FILE)
    if recording:
        f = open(path, 'w')
        f.close()
    else:
        if os.path.isfile(path):
            os.remove(path)


@app.middleware("http")
async def handle_x_forwarded_prefix(request: Request, call_next):
    """
    Use a dynamic prefix addition if running behind a proxy
    """
    # Extract the prefix from the proxy header
    prefix = request.headers.get("X-Forwarded-Prefix", "")

    if prefix:
        # Dynamically set the root path for URL generation and docs
        request.scope["root_path"] = prefix

    return await call_next(request)


@app.get("/", response_class=HTMLResponse)
def main_page(request: Request, date: Optional[str] = None):
    """
    Serve root page using main.html
    List of recordings for a single day, defaulting to today, with
    controls to navigate to the previous/next day.
    """
    day = datetime.date.fromisoformat(date) if date else datetime.date.today()
    recording = get_record_setting()
    all_entries = get_file_list()
    entries = [e for e in all_entries if e["timestamp"].date() == day]

    # Only offer navigation to days that actually have recordings
    dates = { e["timestamp"].date() for e in all_entries }
    prev_day = max((d for d in dates if d < day), default=None)
    next_day = min((d for d in dates if d > day), default=None)

    return templates.TemplateResponse(
        request=request, name="main.html",
        context={"entries": entries,
                 "recording": recording,
                 "day": day,
                 "prev_day": prev_day.isoformat() if prev_day else None,
                 "next_day": next_day.isoformat() if next_day else None}
    )

@app.get("/file/{filename}", response_class=HTMLResponse)
def read_file(filename, request: Request):
    """
    Serve a specific recording file
    """
    entry = lookup_file(filename)
    if entry is not None:
        path = os.path.join(entry["dir"], entry["sound_file"])
        with open(path, 'rb') as file:
            data = file.read()
            return Response(content=data, media_type='audio/wav')
    raise HTTPException(status_code=404)


@app.post("/", response_class=HTMLResponse)
def post_record(request: Request, record: Annotated[str, Form()]):
    """
    Handle enable and disable recording.
    """
    logger.info(f"record = {record}")
    if record == "start":
        set_record_setting(True)
    else:
        set_record_setting(False)

    return templates.TemplateResponse(
        request=request,
        name="recording.html", 
        context={"recording": record == "start"}
    )


@app.post("/file/{filename}", response_class=HTMLResponse)
def post_file(request: Request, filename: str, action: Annotated[str, Form()]):
    """
    Handle update for a file
    """
    entry = lookup_file(filename)
    if entry is None:
        raise HTTPException(status_code=404)
    sound_file_path = os.path.join(entry["dir"], entry["sound_file"])
    json_file_path = os.path.join(entry["dir"], entry["json_file"])

    if action == "delete":
        logger.info(f"delete {filename}")
        os.remove(sound_file_path)
        os.remove(json_file_path)
        return Response(status_code=200)

    if action in CLASSES:
        logger.info(f"move {filename} to {action}")
        class_path = os.path.join(auto_record.DATA_DIR, action)
        os.makedirs(class_path, exist_ok=True)

        with open(json_file_path, 'r') as f:
            info = json.load(f)
        info["category"] = action
        with open(json_file_path, 'w') as f:
            json.dump(info, f)

        new_sound_path = os.path.join(class_path, entry["sound_file"])
        new_json_path = os.path.join(class_path, entry["json_file"])
        os.rename(sound_file_path, new_sound_path)
        os.rename(json_file_path, new_json_path)

        entry["category"] = action
        entry["confirmed"] = True
        return templates.TemplateResponse(
            request=request,
            name="row.html",
            context={"entry": entry}
        )

    return Response(status_code=200)

LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        }
    },
    'handlers': {
        'default': {
            'formatter': 'standard',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'server.log'
        },
    },
    'loggers': {
        'uvicorn': {
           'handlers': [ 'default' ],
           'level' : 'INFO',
        }
    }
}


if __name__ == '__main__':
    print("Connect to http://localhost:3000")
    clean_files()
    # Configuration should only run on a fully trusted network
    uvicorn.run(
        app,
        log_config=LOGGING_CONFIG,
        host="0.0.0.0",
        port=3000,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
