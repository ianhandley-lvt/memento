#!/usr/bin/env python3
"""One-time migration for anyone upgrading to a memento version that has
`memento report`'s nightly-sync-yield section: nightly-sync.sh only started
appending to sync_history.jsonl once that feature landed, so runs from
before then are invisible to the report. This recovers them by re-parsing
the plain-text logs nightly-sync.sh has always written under
~/.local/share/memento/logs/nightly-sync-*.log.

Safe to re-run: dedupes against sync_history.jsonl's existing lines.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path.home() / ".local/share/memento/logs"
START_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) START: (.+)$")


def label_for(description: str) -> str | None:
    if description == "import Claude sessions (all projects)":
        return "claude_sessions"
    if description == "import Cursor conversations":
        return "cursor_sessions"
    match = re.match(r"import Confluence pages \((.+)\)$", description)
    return f"confluence:{match.group(1)}" if match else None


def parse_log(path: Path) -> list[dict]:
    lines = path.read_text().splitlines()
    entries = []
    index = 0
    while index < len(lines):
        match = START_RE.match(lines[index])
        if not match:
            index += 1
            continue
        timestamp_str, description = match.groups()
        label = label_for(description)
        index += 1
        if label is None:
            continue
        blob_lines = []
        while index < len(lines) and not START_RE.match(lines[index]) and not lines[index].startswith(tuple(f"{year}-" for year in range(2020, 2100))):
            blob_lines.append(lines[index])
            index += 1
        try:
            data = json.loads("\n".join(blob_lines))
        except json.JSONDecodeError:
            continue
        logged_at = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).isoformat()
        entries.append({
            "label": label,
            "logged_at": logged_at,
            "discovered": data.get("discovered", 0),
            "activated": data.get("activated", 0),
            "blocked": data.get("blocked", 0),
            "failed": data.get("failed", 0),
            "pending_retry": data.get("pending_retry", 0),
        })
    return entries


def main() -> None:
    artifacts_root = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if artifacts_root is None:
        sys.exit("usage: backfill-sync-history.py <artifacts_root>  (see `memento config show` for the path)")
    out_path = artifacts_root / "sync_history.jsonl"

    parsed = [entry for path in sorted(LOG_DIR.glob("nightly-sync-*.log")) for entry in parse_log(path)]
    existing = set(out_path.read_text().splitlines()) if out_path.exists() else set()
    combined = sorted(existing | {json.dumps(entry) for entry in parsed}, key=lambda line: json.loads(line)["logged_at"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(combined) + "\n")
    print(f"wrote {len(combined)} entries to {out_path} ({len(parsed)} parsed from {LOG_DIR})")


if __name__ == "__main__":
    main()
