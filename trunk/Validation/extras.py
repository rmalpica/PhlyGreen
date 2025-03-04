"""saving some common functions here to keep the code D.R.Y."""

import json
import os
from pathlib import Path


def make_cat_dir(*args):
    """
    Concatenate and create directories at the same time
    If directory already exists, append numbers to it
    """
    base_directory = os.path.join(*args)
    directory = base_directory
    i = 0
    while os.path.exists(directory):
        i += 1
        directory = f"{base_directory}-{i}"

    Path(directory).mkdir(parents=True, exist_ok=True)
    return directory


def dump_json(data, jsonfn):
    """Given a dictionary, this will dump it to a json file"""
    with open(jsonfn, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def load_json(jsonfn):
    """Load a json file to a dictionary"""
    with open(jsonfn, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data
