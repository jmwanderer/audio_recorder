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
from typing import Any, Tuple, Union

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

import auto_record

# Initialize fast api and logging
app = FastAPI()
templates = Jinja2Templates(directory=".")
logger = logging.getLogger("uvicorn.error")


def get_file_list():
    """
    Read the contents of the JSON information files in the data directory
    and return list of dictionary elements sorted by the timestamp.
    """
    result = []
    logger.debug("get file list")
    entries = os.listdir(auto_record.DATA_DIR)
    for entry in entries:
        if entry.endswith(".json"):
            path = os.path.join(auto_record.DATA_DIR, entry)
            f = open(path, 'r')
            info = json.loads(f.read())
            f.close()

            # Change timestamp from text to datetime.dateime
            info["timestamp"] = datetime.datetime.fromisoformat(info["timestamp"])
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


@app.get("/", response_class=HTMLResponse)
def main_page(request: Request):
    """
    Serve root page using main.html
    List of recordings
    """
    recording = get_record_setting()
    entries = get_file_list()
    return templates.TemplateResponse(
        request=request, name="main.html", 
        context={"entries": entries,
                 "recording": recording}
    )

@app.get("/file/{filename}", response_class=HTMLResponse)
def read_file(filename, request: Request):
    """
    Serve a specific recording file
    """
    entry = lookup_file(filename)
    if entry is not None:
        path = os.path.join(auto_record.DATA_DIR, entry["sound_file"])
        with open(path, 'rb') as file:
            data = file.read()
            return Response(content=data, media_type='audio/wav')
    raise HTTPException(status_code=404)

@app.post("/", response_class=RedirectResponse)
def post_record(record: Annotated[str, Form()]):
    """
    Handle enable and disable recording.
    """
    logger.info(f"record = {record}")
    if record == "start":
        set_record_setting(True)
    else:
        set_record_setting(False)
    return RedirectResponse("/", status_code=301)



@app.post("/file/{filename}", response_class=RedirectResponse)
def post_file(filename: str, action: Annotated[str, Form()]):
    """
    Handle delete file.
    """
    entry = lookup_file(filename)
    if entry is None:
        raise HTTPException(status_code=404)
    sound_file_path = os.path.join(auto_record.DATA_DIR, entry["sound_file"])
    json_file_path = os.path.join(auto_record.DATA_DIR, entry["json_file"])

    if action == "delete":
        logger.info(f"delete {filename}")
        os.remove(sound_file_path)
        os.remove(json_file_path)
    return RedirectResponse("/", status_code=301)

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
    uvicorn.run(app, log_config=LOGGING_CONFIG, host="0.0.0.0", port=3000)
