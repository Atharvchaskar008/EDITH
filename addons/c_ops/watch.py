from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from typing import List, Optional, Set

from compare import compare_runs
from models import load_run, save_alerts, save_events
from notify import print_console, write_feed, write_summary

RUN_ID_REGEX = re.compile(r"^\d{8}T\d{4,6}Z?$")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RUNS_DIR = os.path.normpath(os.path.join(BASE_DIR, "../../data/runs"))
DEFAULT_FEED_PATH = os.path.normpath(os.path.join(BASE_DIR, "out/alert_feed.json"))
STATE_FILE_PATH = os.path.normpath(os.path.join(BASE_DIR, "out/watcher_state.json"))


def is_run_folder_name(name: str) -> bool:
    return bool(RUN_ID_REGEX.match(name))


def is_run_complete(folder_path: str) -> bool:
    events_path = os.path.join(folder_path, "events.json")
    if not os.path.isfile(events_path):
        return False
    done_path = os.path.join(folder_path, "DONE")
    if os.path.isfile(done_path):
        return True
    try:
        mtime = os.path.getmtime(events_path)
        if time.time() - mtime >= 10.0:
            return True
    except OSError:
        pass
    return False


def load_processed_state(state_file: str = STATE_FILE_PATH) -> Set[str]:
    if os.path.isfile(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("processed_runs", []))
        except Exception:
            return set()
    return set()


def save_processed_state(processed: Set[str], state_file: str = STATE_FILE_PATH) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(state_file)), exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({"processed_runs": sorted(list(processed))}, f, indent=2)


def process_single_run(
    run_folder: str,
    runs_dir: str,
    feed_path: str = DEFAULT_FEED_PATH,
    all_runs: Optional[List[str]] = None,
) -> bool:
    """Processes a single complete run folder. Returns True if succeeded."""
    run_id = os.path.basename(os.path.normpath(run_folder))
    print(f"\nProcessing run: {run_id} ({run_folder})")

    # 1. Find previous run that sorts strictly before this one
    if all_runs is None:
        candidates = [
            d for d in os.listdir(runs_dir)
            if is_run_folder_name(d) and os.path.isdir(os.path.join(runs_dir, d))
        ]
    else:
        candidates = all_runs

    prior_runs = sorted([d for d in candidates if d < run_id])
    prev_folder = os.path.join(runs_dir, prior_runs[-1]) if prior_runs else None

    prev_events, prev_plans = [], []
    if prev_folder and os.path.isdir(prev_folder):
        try:
            prev_events, prev_plans = load_run(prev_folder)
        except Exception as e:
            print(f"Warning: Could not load previous run {prev_folder}: {e}")
            prev_events, prev_plans = [], []

    # 2. Load current run
    try:
        curr_events, curr_plans = load_run(run_folder)
    except Exception as e:
        print(f"Error: Failed to load current run {run_folder} (skipping): {e}")
        return False

    # 3. Compare runs
    try:
        updated_events, alerts = compare_runs(
            previous=prev_events,
            current=curr_events,
            current_plans=curr_plans,
            run_id=run_id,
            previous_plans=prev_plans,
        )
    except Exception as e:
        print(f"Error during compare_runs for {run_id}: {e}")
        return False

    # 4. Write alerts.json and updated events.json
    save_alerts(alerts, run_folder)
    save_events(updated_events, run_folder)

    # 5. Update feed, write summary.json, print console table
    write_feed(alerts, feed_path)
    summary_path = os.path.join(run_folder, "summary.json")
    write_summary(
        events=updated_events,
        plans=curr_plans,
        alerts=alerts,
        run_id=run_id,
        path=summary_path,
        previous_events=prev_events,
    )
    print_console(alerts)
    return True


def run_watcher(
    runs_dir: str,
    feed_path: str = DEFAULT_FEED_PATH,
    state_file: str = STATE_FILE_PATH,
    once: bool = False,
    poll_interval: float = 2.0,
) -> None:
    print(f"Watcher started on directory: {runs_dir}")
    print(f"Alert feed output: {feed_path}")

    processed = load_processed_state(state_file)

    while True:
        if os.path.isdir(runs_dir):
            all_entries = sorted([
                d for d in os.listdir(runs_dir)
                if is_run_folder_name(d) and os.path.isdir(os.path.join(runs_dir, d))
            ])
            for run_name in all_entries:
                if run_name in processed:
                    continue
                run_path = os.path.join(runs_dir, run_name)
                if is_run_complete(run_path):
                    ok = process_single_run(run_path, runs_dir, feed_path=feed_path, all_runs=all_entries)
                    if ok:
                        processed.add(run_name)
                        save_processed_state(processed, state_file)

        if once:
            print("Completed --once processing. Exiting.")
            break
        time.sleep(poll_interval)


def replay_runs(
    replay_dir: str,
    feed_path: str = DEFAULT_FEED_PATH,
    pause_seconds: float = 1.0,
) -> None:
    print(f"Replaying runs from: {replay_dir}")
    if not os.path.isdir(replay_dir):
        print(f"Error: replay directory '{replay_dir}' not found.")
        return

    all_entries = sorted([
        d for d in os.listdir(replay_dir)
        if is_run_folder_name(d) and os.path.isdir(os.path.join(replay_dir, d))
    ])

    if not all_entries:
        print(f"No run folders matching run_id pattern found in {replay_dir}.")
        return

    for idx, run_name in enumerate(all_entries):
        run_path = os.path.join(replay_dir, run_name)
        process_single_run(run_path, replay_dir, feed_path=feed_path, all_runs=all_entries)
        if idx < len(all_entries) - 1:
            time.sleep(pause_seconds)


def main():
    parser = argparse.ArgumentParser(description="Watch or replay conjunction run folders and generate alerts.")
    parser.add_argument("--runs", default=DEFAULT_RUNS_DIR, help="Path to runs directory")
    parser.add_argument("--feed", default=DEFAULT_FEED_PATH, help="Path to alert feed JSON")
    parser.add_argument("--state", default=STATE_FILE_PATH, help="Path to state tracking JSON")
    parser.add_argument("--once", action="store_true", help="Process available runs once and exit")
    parser.add_argument("--replay", help="Replay run folders from given directory with pauses")
    parser.add_argument("--pause", type=float, default=1.0, help="Pause duration between replay runs in seconds")

    args = parser.parse_args()

    if args.replay:
        replay_runs(args.replay, feed_path=args.feed, pause_seconds=args.pause)
    else:
        run_watcher(
            runs_dir=args.runs,
            feed_path=args.feed,
            state_file=args.state,
            once=args.once,
        )


if __name__ == "__main__":
    main()
