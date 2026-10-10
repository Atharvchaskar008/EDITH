"""Check a running server end to end: every route, against its latest finished run.

    python scripts/check_server.py                 check the server on port 8000
    python scripts/check_server.py --run           start a fresh run first and wait for it (about 7 minutes)
    python scripts/check_server.py --url https://edith.onrender.com     check the public showcase

Prints one line per check and exits with 1 if any failed. It asks for one
what-if burn and one satellite check, so it takes about half a minute.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
import urllib.error
import urllib.request

failed: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS  " if ok else "FAIL  ") + name + (": " + detail if detail else ""), flush=True)
    if not ok:
        failed.append(name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="where the server is")
    parser.add_argument("--run", action="store_true", help="start a fresh run and wait for it before checking")
    args = parser.parse_args()

    def call(path: str, method: str = "GET", body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(args.url + path, method=method, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=900) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if response.headers.get_content_type() == "application/json" else raw)

    if args.run:
        started = time.time()
        _, begun = call("/run", "POST", {"synthetic": False, "quick": True, "mode": None})
        print(f"      run {begun['run_id']} {'was already in progress' if begun['already_running'] else 'started'}; waiting", flush=True)
        while True:
            time.sleep(5)
            _, status = call(f"/run/{begun['run_id']}/status")
            if status["status"] != "RUNNING":
                break
        stages = [entry["stage"] for i, entry in enumerate(status["log"]) if i == 0 or entry["stage"] != status["log"][i - 1]["stage"]]
        check("fresh run", status["status"] == "DONE", f"{status['status']} after {time.time() - started:.0f} s; {' > '.join(stages)}" + (f"; {status.get('error')}" if status.get("error") else ""))

    def refused(path: str, method: str = "GET") -> bool:
        try:
            call(path, method)
        except urllib.error.HTTPError as error:
            return error.code == 403
        return False

    _, monitor = call("/monitor")
    show_only = bool(monitor.get("read_only"))
    if show_only:
        check("show-only server", not monitor["scheduler_on"] and refused("/run", "POST") and refused("/objects/search?q=ISS"),
              "a recorded showcase: it refuses to start runs, burn searches and satellite checks")
    else:
        check("scheduler", bool(monitor["scheduler_on"] and monitor["next_run"]), f"on, next automatic run {str(monitor['next_run'])[:16]} UTC, {monitor['run_count']} finished runs")
    _, latest = call("/latest")
    source = "CelesTrak and Space-Track" if (latest.get("catalog") or {}).get("spacetrack") else "CelesTrak only"
    check("latest run", latest["status"] == "DONE",
          f"{latest['run_id']}: {latest['screen']['objects_screened']:,} objects from {source}, {latest['events']:,} passes, {latest['levels']}, {latest['duration_s']:.0f} s")
    _, events = call("/events?limit=100000")
    check("events", len(events) == latest["events"], f"{len(events):,} listed")
    measured = sum(e["sigma_source"] == "MEASURED" for e in events)
    forecast = sum(e.get("pc_predicted_final") is not None for e in events)
    history = sum(len(e.get("history") or []) > 1 for e in events)
    check("add-on packs in the run", min(measured, forecast) > 0, f"measured uncertainty on {measured:,} passes, model forecast on {forecast:,}, history on {history:,}")

    reds = [e for e in events if e["risk_level"] == "RED"]
    states = collections.Counter("Burn ready" if e["plan_decision"] == "MANEUVER" else e["plan_reason"] or "no reason" for e in reds)
    check("every red pass has a burn or a reason", "no reason" not in states, ", ".join(f"{k} {v}" for k, v in states.most_common()) or "no red passes")
    burns = [call(f"/events/{e['event_id']}/plan")[1] for e in reds if e["plan_decision"] == "MANEUVER"]
    clean = all(p["secondary_conjunctions_created"] == 0 and p["other_passes_worsened"] == 0 and p["return_burn_time"] for p in burns)
    check("burns", len(burns) == latest["plans"]["maneuver"] and clean, f"{len(burns)} burns, each with a return burn, 0 new and 0 worsened passes")
    if burns:
        _, detail = call(f"/events/{burns[0]['event_id']}")
        check("event detail", len(detail["track"]["times_s"]) == 241 and bool(detail["track"]["maneuvered_km"]) and bool(detail["encounter"]["miss_after_km"]))
        briefing = call(f"/runs/latest/files/briefings/{burns[0]['event_id']}.briefing.json")[0]
        message = call(f"/runs/latest/files/cdm/{burns[0]['event_id']}.cdm.txt")[0]
        check("briefing and warning message are served", briefing == 200 and message == 200)
    _, priority = call("/events?level=RED&own_fleet=false&limit=100000")
    check("priority list", len(priority) <= len(reds), f"{len(priority)} of {len(reds)} red passes are not inside one fleet")

    watched = next((e for e in events if e["risk_level"] == "AMBER" and not e["own_fleet"]), None)
    if show_only:
        check("burn on request is refused", watched is None or refused(f"/events/{watched['event_id']}/plan", "POST"))
    elif watched:
        t = time.time()
        _, asked = call(f"/events/{watched['event_id']}/plan", "POST")
        check("burn on request", asked["what_if"] is True and bool(asked["requested_at"]),
              f"{watched['primary_name']} / {watched['secondary_name']} (amber): {asked['decision']} as a what-if in {time.time() - t:.0f} s")
    found = [] if show_only else call("/objects/search?q=ISS")[1]
    if found:
        t = time.time()
        _, passes = call(f"/objects/{found[0]['norad_id']}/passes")
        check("satellite check", passes["objects_screened"] > 0, f"{found[0]['name']}: {len(passes['passes'])} passes within {passes['threshold_km']:g} km, {passes['objects_screened']:,} objects, {time.time() - t:.0f} s")
    _, fleets = call("/fleets")
    check("fleets", len(fleets) > 0, f"{len(fleets)} fleets; {fleets[0]['fleet']}: {fleets[0]['red_to_act_on']} to act on, {fleets[0]['red_own_fleet']} inside the fleet" if fleets else "")
    _, alerts = call("/alerts")
    check("alerts", isinstance(alerts, list), f"{len(alerts)} changes since the previous run")
    _, addons = call("/addons")
    wanted = latest["levels"]["RED"] + latest["levels"]["AMBER"]
    check("briefings and warning messages", addons["briefings_for_latest_run"] == wanted == addons["cdm_for_latest_run"], f"{wanted} of each; packs {addons['packs']}")

    for name, path, good in (
        ("validation", "/validation", lambda v: v["same_input"]["all_matches"]["matched"] > 0),
        ("proof", "/proof", lambda p: len(p["error_growth"]["kinds"]) > 0),
        ("2009 replay", "/replay/2009", lambda r: r["events"][0]["secondary_name"] == "COSMOS 2251"),
    ):
        try:
            check(name, good(call(path)[1]))
        except urllib.error.HTTPError as error:
            check(name, False, f"{error.code}: it needs the add-on packs and its own build step")
    for path in ("/", "/static/dashboard.css", "/static/dashboard.js", "/landing", "/docs"):
        try:
            code = call(path)[0]
        except urllib.error.HTTPError as error:
            code = error.code
        check("page " + path, code == 200)

    print("\n" + ("ALL CHECKS PASSED" if not failed else "FAILED: " + ", ".join(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
