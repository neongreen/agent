#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
from typing import Any, Optional


def filter_keys(obj: Any, key_mode: Optional[str] = None, key_re: Optional[str] = None) -> Any:
    """
    Recursively filter keys in a dict based on regex and mode.
    key_mode: '+' to keep only keys matching key_re, '-' to remove keys matching key_re, None for no filter.
    """
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            if key_mode == "+" and key_re and not re.search(key_re, k):
                continue
            if key_mode == "-" and key_re and re.search(key_re, k):
                continue
            new_obj[k] = filter_keys(v, key_mode, key_re)
        return new_obj
    elif isinstance(obj, list):
        return [filter_keys(i, key_mode, key_re) for i in obj]
    else:
        return obj


def filter_type(obj: Any, type_mode: Optional[str] = None, type_re: Optional[str] = None) -> Any:
    """
    Filter a list of log entries by message_type or action_type using regex and mode.
    type_mode: '+' to keep only matching, '-' to remove matching, None for no filter.
    """
    ALWAYS_KEEP = {"timestamp", "task_uuid", "task_level", "message_type", "action_type", "action_status"}
    if isinstance(obj, list):
        filtered = []
        for entry in obj:
            t = entry.get("message_type") or entry.get("action_type")
            if type_mode == "+" and type_re and (not t or not re.search(type_re, t)):
                continue
            if type_mode == "-" and type_re and t and re.search(type_re, t):
                # Instead of removing, keep only ALWAYS_KEEP keys
                filtered.append({k: v for k, v in entry.items() if k in ALWAYS_KEEP})
                continue
            filtered.append(entry)
        return filtered
    return obj


def main():
    parser = argparse.ArgumentParser(
        description="Show given Eliot log with optional key filtering and eliot-tree output."
    )
    parser.add_argument("--file", metavar="FILE", help="The log file to view (default: latest log in ~/.ok/logs/)")
    parser.add_argument(
        "-k", metavar="[+-]REGEX", help="Key filter: +REGEX to keep, -REGEX to remove keys matching regex"
    )
    parser.add_argument(
        "-t",
        metavar="[+-]REGEX",
        help="Type filter: +REGEX to keep, -REGEX to remove message/action types matching regex",
    )
    args, eliot_tree_args = parser.parse_known_args()

    # Find default log file if not provided
    log_file = args.file
    if not log_file:
        import glob
        import os

        log_dir = os.path.expanduser("~/.ok/logs/")
        log_files = sorted(glob.glob(os.path.join(log_dir, "*")), key=os.path.getmtime, reverse=True)
        log_file = log_files[0] if log_files else None

    if log_file:
        infile = open(log_file, "r")
    else:
        infile = sys.stdin

    # Parse key filter
    key_mode = key_re = None
    if args.k:
        if args.k.startswith("+"):
            key_mode = "+"
            key_re = args.k[1:]
        elif args.k.startswith("-"):
            key_mode = "-"
            key_re = args.k[1:]

    # Parse type filter
    type_mode = type_re = None
    if args.t:
        if args.t.startswith("+"):
            type_mode = "+"
            type_re = args.t[1:]
        elif args.t.startswith("-"):
            type_mode = "-"
            type_re = args.t[1:]

    # Read and filter each line
    filtered_objs = []
    for line in infile:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        filtered = filter_keys(obj, key_mode, key_re)
        filtered_objs.append(filtered)

    # If type filter is set, apply it to the list of log entries
    if type_mode and type_re:
        filtered_objs = filter_type(filtered_objs, type_mode, type_re)

    filtered_lines = [json.dumps(obj, ensure_ascii=False) for obj in filtered_objs]

    if args.file:
        infile.close()

    # Pipe to eliot-tree
    eliot_tree_cmd = ["uv", "run", "eliot-tree"] + eliot_tree_args
    proc = subprocess.Popen(eliot_tree_cmd, stdin=subprocess.PIPE)
    proc.communicate(input=("\n".join(filtered_lines) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
