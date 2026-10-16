"""Record fully live Gemini hearings so the desk can replay them when quota runs out.

Runs each file with Gemini in every seat and writes recordings/<alert>.json
only if every seat answered live. Spends real tokens. Usage:

    python scripts/record.py            # every file
    python scripts/record.py HL-4374    # one file
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quorum import config, hearing, store, warehouse  # noqa: E402
from quorum.cases import ALERTS  # noqa: E402

OUT = config.ROOT / "recordings"


async def record(alert_id: str) -> bool:
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append(event)
        if event["type"] in {"seat", "sealed", "error"}:
            detail = event.get("source") or event.get("disposition") or event.get("message")
            print(f"  {event['t'] / 1000:6.1f}s {event['type']:7} {event.get('seat', ''):20} {detail}")

    print(alert_id)
    record = await hearing.convene(alert_id, emit, requested="live")
    sources = record["sources"]
    if not all(source in {"gemini", "desk"} for source in sources.values()):
        print(f"  not recorded: seats fell back {[name for name, source in sources.items() if source not in {'gemini', 'desk'}]}")
        return False
    OUT.mkdir(exist_ok=True)
    recording = {"alert_id": alert_id, "hearing_id": record["id"], "recorded_at": record["sealed_at"],
                 "models": events[0]["models"], "events": events, "record": record}
    (OUT / f"{alert_id}.json").write_text(json.dumps(recording, ensure_ascii=False, indent=1))
    print(f"  recorded {len(events)} events, {record['ms'] / 1000:.1f}s, tokens {record['tokens']}")
    return True


async def main(ids: list[str]) -> None:
    if config.configure_gemini() == "none":
        sys.exit("Set GEMINI_API_KEY in .env first.")
    store.init()
    warehouse.warm()
    results = [await record(alert_id) for alert_id in ids]
    print(f"{sum(results)}/{len(results)} recorded")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or [alert["id"] for alert in ALERTS]))
