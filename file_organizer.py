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

DEFAULT_SOURCE_DIR = "incoming"
DEFAULT_TARGET_DIR = "working"
DEFAULT_QUARANTINE_DIR = "quarantine"
DEFAULT_JOURNAL_NAME = "organization-journal.json"
DEFAULT_PLAN_NAME = "organization-plan.json"
