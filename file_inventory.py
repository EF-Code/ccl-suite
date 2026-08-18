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
