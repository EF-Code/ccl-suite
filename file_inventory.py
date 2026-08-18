"""Day 2 file inventory scanner."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_CHUNK_SIZE = 1024 * 1024
DEFAULT_PROJECT_ROOT = Path(os.getenv("CCL_PROJECT_ROOT", "projects"))
DEFAULT_JSON_NAME = "manifest.json"
DEFAULT_CSV_NAME = "manifest.csv"
MIME_COMMAND = ("file", "--brief", "--mime-type")
@dataclass(frozen=True)
class FileRecord:
    """One manifest row for a regular file."""

    relative_path: str
    name: str
    extension: str
    mime_type: str
    size_bytes: int
    modified_at: str
    sha256: str
