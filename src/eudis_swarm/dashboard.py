"""Console launcher for the local Streamlit playback dashboard."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the packaged Streamlit application and forward trace arguments."""

    parser = argparse.ArgumentParser(
        description="Launch the local EUDIS swarm trace playback dashboard."
    )
    parser.add_argument(
        "trace",
        nargs="?",
        default="trace.json",
        help="trace JSON path (default: trace.json)",
    )
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if importlib.util.find_spec("streamlit") is None:
        parser.error("Streamlit is unavailable; install the 'dashboard' extra")
    application = Path(__file__).with_name("dashboard_app.py")
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(application),
        "--",
        "--trace",
        arguments.trace,
    ]
    return subprocess.run(command, check=False).returncode


__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
