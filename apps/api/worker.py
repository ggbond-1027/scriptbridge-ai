from __future__ import annotations

import argparse
import asyncio
import json

from .queue import run_worker_loop


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ScriptBridge external job worker.")
    parser.add_argument("--worker-id", default="scriptbridge-worker", help="Stable worker identity shown in queue status.")
    parser.add_argument("--max-jobs", type=int, default=None, help="Stop after processing this many jobs. Omit to run forever.")
    parser.add_argument("--idle-sleep", type=float, default=None, help="Seconds to sleep when no external job is available.")
    args = parser.parse_args()

    try:
        result = asyncio.run(
            run_worker_loop(
                worker_id=args.worker_id,
                max_jobs=args.max_jobs,
                idle_sleep_seconds=args.idle_sleep,
            )
        )
    except KeyboardInterrupt:
        return

    print(json.dumps({"worker": result.worker.model_dump(mode="json"), "processed": result.processed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
