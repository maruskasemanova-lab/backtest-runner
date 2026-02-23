#!/usr/bin/env python3
"""
Print the next BMAD story from backlog (priority + status based).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
BOARD_PATH = ROOT / "bmad" / "backlog" / "story-board.json"
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
STATUS_ORDER = {"todo": 0, "in_progress": 1, "blocked": 2, "done": 3}


def load_board() -> Dict[str, Any]:
    return json.loads(BOARD_PATH.read_text(encoding="utf-8"))


def sort_key(story: Dict[str, Any]) -> tuple:
    return (
        PRIORITY_ORDER.get(str(story.get("priority", "")).upper(), 99),
        STATUS_ORDER.get(str(story.get("status", "")).lower(), 99),
        str(story.get("id", "")),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Select next BMAD story from backlog")
    parser.add_argument("--id", type=str, default="", help="Specific story ID")
    parser.add_argument("--all", action="store_true", help="Print all non-done stories")
    args = parser.parse_args()

    board = load_board()
    stories: List[Dict[str, Any]] = board.get("stories", [])
    if args.id:
        matches = [
            s for s in stories if str(s.get("id", "")).upper() == args.id.upper()
        ]
        if not matches:
            raise SystemExit(f"Story not found: {args.id}")
        chosen = matches[0]
        print(json.dumps(chosen, indent=2))
        return

    open_stories = [s for s in stories if str(s.get("status", "")).lower() != "done"]
    open_stories.sort(key=sort_key)

    if args.all:
        print(json.dumps(open_stories, indent=2))
        return

    todos = [s for s in open_stories if str(s.get("status", "")).lower() == "todo"]
    chosen = todos[0] if todos else (open_stories[0] if open_stories else None)
    if not chosen:
        print("No open stories.")
        return

    print(json.dumps(chosen, indent=2))


if __name__ == "__main__":
    main()
