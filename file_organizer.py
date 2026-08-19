"""Safe dry-run file organiser."""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from file_inventory import FileRecord, resolve_approved_root, safe_relative_path
