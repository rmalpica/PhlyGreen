"""saving some common functions here to keep the code D.R.Y."""

import json
import os
from pathlib import Path


def make_cat_dir(*args):
    """Concatenate and create directories at the same time"""
    directory = os.path.join(*args)
    Path(directory).mkdir(parents=True, exist_ok=True)
    return directory


def dump_json(dicts, jsonfn):
    """Given a dictionary, this will dump it to a json file"""
    with open(jsonfn, "w", encoding="utf-8") as json_file:
        json.dump(dicts, json_file, indent=4)
