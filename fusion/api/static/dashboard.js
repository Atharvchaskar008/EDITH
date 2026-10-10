// The operator dashboard. It reads everything from the server's routes (docs/API.md) and keeps no data of its own.
const $ = id => document.getElementById(id);
let picked = null, runId = null, source = "latest", onlyBurns = false;
let idle = "", failed = false;  // what the line beside the Run button says between runs; a failure stays until the next run
let showOnly = false;  // a recorded showcase: nothing can be started, and times are dates because the run does not move
let checked = null, typed = 0;  // the result of checking one satellite, shown when source is "object"
let fleet = null;  // the fleet whose passes the list shows, when one was picked under Fleets
let priority = true, reds = null, shown = null;  // Priority: the dangerous passes that are not inside one fleet
const PASS_HEAD = "<tr><th>Level</th><th>Objects</th><th>Distance</th><th>Risk</th><th>Plan</th></tr>";
// why a dangerous pass has no burn, as the list says it; a pass below the action line is simply watched
const SETTLED = ["NEITHER_CAN_MOVE", "TOO_SOON", "NO_SAFE_BURN"];  // a new search would give the same answer, so no button
const WHY = { NEITHER_CAN_MOVE: "Cannot move", SAME_FLEET: "Own fleet", TOO_SOON: "Too soon", NO_SAFE_BURN: "No safe burn", LIMIT: "Not planned" };
const FLEET_HEAD = "<tr><th>Fleet</th><th>Satellites</th><th>Passes</th><th>Dangerous</th><th>Own fleet</th><th>Burns</th></tr>";
const get = async path => { const r = await fetch(path); if (!r.ok) throw new Error(path); return r.json(); };
const n = x => Number(x).toLocaleString("en-US");
const esc = s => String(s == null ? "" : s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const odds = p => p == null ? "-" : p >= 0.5 ? "likely" : 1 / p > 1e9 ? "under 1 in a billion" : "1 in " + n(Math.round(1 / p));
const dist = km => km < 1 ? Math.round(km * 1000) + " m" : km.toFixed(2) + " km";
const short = km => km < 1 ? Math.round(km * 1000) + " m" : km.toFixed(km < 10 ? 1 : 0) + " km";  // for a picture's axis
const word = level => level ? level[0] + level.slice(1).toLowerCase() : "";
const clock = t => new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });  // in the viewer's own time
const when = t => source === "replay" || showOnly ? new Date(t).toUTCString().slice(5, 22) + " UTC" : "in " + Math.max(0, (new Date(t) - Date.now()) / 3.6e6).toFixed(1) + " h";
const fail = () => { $("error").textContent = "Cannot reach the system."; };

async function loadTop() {
  const r = await get("/latest");
  $("t-objects").textContent = n(r.screen.objects_screened);
  $("t-passes").textContent = n(r.events);
  $("t-red").textContent = n(r.levels.RED);
  reds = r.levels.RED; aboutPriority();
  $("t-burns").textContent = n(r.plans.maneuver);
  $("t-rest").textContent = n(r.levels.AMBER) + " to watch, " + n(r.levels.GREEN) + " safe";
  written = !!(r.addons && r.addons.briefings);
  $("error").textContent = "";
  idle = "Last run " + clock(r.t0) + ".";
  try {
    const m = await get("/monitor");
    if (m.story_url) $("story").href = m.story_url;
    if (m.scheduler_on && m.next_run) idle += " Next " + clock(m.next_run) + ".";
    if (m.read_only) {
      showOnly = true; idle = "Recorded run, " + new Date(r.t0).toUTCString().slice(5, 22) + " UTC. The live system runs every six hours.";
      $("run").hidden = true; document.querySelector(".find input").hidden = true;
    }
  } catch (e) { /* the line is shorter without it */ }
  if (!runId && !failed) $("status").textContent = idle;
  try {
    const v = await get("/validation");
    $("validation").textContent = "Matches CelesTrak to " + v.same_input.all_matches.miss_difference_m.median.toFixed(2) + " m.";
  } catch (e) { $("validation").textContent = ""; }
}

function aboutPriority() {
  if (source !== "latest" || !priority || reds == null || shown == null) return;
  $("about").textContent = shown + " of " + reds + " dangerous. The other " + (reds - shown) + " are inside one fleet.";
}

// one row per fleet: passes to act on, passes inside the fleet (left to its operator), burns planned for it
async function loadFleets() {
  const fleets = (await get("/fleets")).slice(0, 40);
  $("head").innerHTML = FLEET_HEAD;
  $("events").innerHTML = fleets.map(f => `<tr class="row" data-fleet="${esc(f.fleet)}">
      <td class="${f.red_to_act_on ? "RED" : "AMBER"}">${esc(f.fleet)}</td><td>${f.satellites == null ? "-" : n(f.satellites)}</td><td>${n(f.passes)}</td>
      <td class="${f.red_to_act_on ? "RED" : "GREEN"}">${n(f.red_to_act_on)}</td><td>${n(f.red_own_fleet)}</td>
      <td>${f.burns ? f.burns + " (" + (f.dv_total_ms * 1000).toFixed(0) + " mm/s)" : ""}</td></tr>`).join("") || '<tr><td colspan="6">Nothing to show.</td></tr>';
  document.querySelectorAll("tr.row").forEach(row => row.onclick = () => {
    fleet = row.dataset.fleet; picked = null;
    $("about").textContent = fleet + " passes.";
    loadEvents().catch(fail);
  });
}

async function loadEvents() {
  if (source === "fleets" && !fleet) return loadFleets();
  const events = source === "object" ? (checked ? checked.passes.slice(0, 60) : [])
    : await get("/events?limit=" + (priority ? 300 : 60) + "&source=" + (source === "fleets" ? "latest&fleet=" + encodeURIComponent(fleet) : source) +
        (onlyBurns ? "&plan=MANEUVER" : "") + (priority ? "&level=RED&own_fleet=false" : ""));
  $("head").innerHTML = PASS_HEAD;
  shown = events.length; aboutPriority();
  if (source === "replay") {
    const hit = events.find(e => [e.primary_id, e.secondary_id].sort().join() === "22675,24946");
    $("about").textContent = hit ? "They collided on 10 February 2009. Public data a day earlier predicted a " + dist(hit.miss_distance_km) + " miss." : "";
  }
  $("events").innerHTML = events.map(e => {
    const plan = e.plan_decision === "MANEUVER" ? "<b>Burn ready</b>" : e.plan_decision === "MONITOR" ? (WHY[e.plan_reason] || "Watch") : "";
    return `<tr class="row ${e.event_id === picked ? "picked" : ""}" data-id="${esc(e.event_id)}">
      <td class="${e.risk_level}">${word(e.risk_level)}</td>
      <td>${esc(e.primary_name)} / ${esc(e.secondary_name)}${e.synthetic ? ' <span class="tag">TEST</span>' : ""}</td>
      <td>${dist(e.miss_distance_km)}</td><td>${odds(e.pc_max)}</td><td>${plan}</td></tr>`;
  }).join("") || '<tr><td colspan="6">Nothing to show.</td></tr>';
  document.querySelectorAll("tr.row").forEach(row => row.onclick = () => {
    picked = row.dataset.id; loadEvents().catch(fail); loadPlan();
    if (getComputedStyle($("planbox")).position !== "sticky") $("planbox").scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

// how unsure each object's position is: the largest of its three measured errors
const doubt = e => e.sigma_rtn_primary_km && e.sigma_rtn_secondary_km
  ? short(Math.max(...e.sigma_rtn_primary_km)) + " and " + short(Math.max(...e.sigma_rtn_secondary_km)) : "-";

// a pass and its risk, for a card that has no burn
function facts(e) {
  return `<div class="facts">
      <div><b>${when(e.tca)}</b><span>the pass</span></div>
      <div><b>${dist(e.miss_distance_km)}</b><span>distance</span></div>
      <div><b>${odds(e.pc_max)}</b><span>risk, worst case</span></div>
      <div><b>${odds(e.pc)}</b><span>risk, best estimate</span></div>
      <div><b>${e.relative_speed_kms.toFixed(1)} km/s</b><span>closing speed</span></div>
      <div><b>${doubt(e)}</b><span>doubt in each position</span></div>
    </div>`;
}

function burn(p, e) {
  const way = p.dv_rtn_ms[1] > 0 ? "Speed up" : "Slow down";
  const lead = (new Date(e.tca) - new Date(p.burn_time)) / 3.6e6, back = (new Date(p.return_burn_time) - new Date(e.tca)) / 3.6e6;
  const mover = p.maneuvering_id === e.primary_id ? e.primary_name : e.secondary_name;
  // runs made before the other passes were compared have no count of them
  const others = p.other_passes_checked == null
    ? `<b>${p.secondary_conjunctions_created}</b><span>new dangers</span>`
    : `<b>${p.secondary_conjunctions_created} new, ${p.other_passes_worsened} worse</b><span>its other passes${p.other_passes_checked ? ", " + p.other_passes_checked + " checked" : ""}</span>`;
  return `<p class="big">${way} by ${(p.dv_magnitude_ms * 1000).toFixed(0)} mm/s</p>
    <div class="facts">
      <div><b>${lead.toFixed(1)} h before the pass</b><span>the burn, ${p.lead_time_orbits} orbits early</span></div>
      <div><b>${dist(p.miss_before_km)} to ${dist(p.miss_after_km)}</b><span>distance</span></div>
      <div><b>${odds(p.pc_max_before)} to ${odds(p.pc_max_after)}</b><span>risk, worst case</span></div>
      <div>${others}</div>
      <div><b>${esc(mover)}</b><span>the one that moves</span></div>
      <div><b>${when(e.tca)}</b><span>the pass</span></div>
      <div><b>${odds(p.pc_before)} to ${odds(p.pc_after)}</b><span>risk, best estimate</span></div>
      <div><b>${back.toFixed(1)} h after the pass</b><span>burn back to its old orbit</span></div>
    </div><p class="why">${esc(p.rationale)}</p>`;
}

// --- pictures: every one is drawn in the same 250 x 165 frame ---
const W = 250, H = 165, L = 40, R = 6, T = 8, B = 20;
const across = u => L + u * (W - L - R), down = u => T + u * (H - T - B);  // 0..1 over the plot area
const frame = body => `<svg viewBox="0 0 ${W} ${H}" role="img">${body}</svg>`;
const label = (x, y, text, anchor, on) => `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="${anchor || "start"}"${on ? ' class="on"' : ""}>${text}</text>`;

// the gap between the two objects around the closest moment, their paths taken as straight lines
function gapPicture(e, after, afterWord) {
  const v = e.relative_speed_kms, before = e.miss_distance_km, wide = Math.max(before, after || 0);
  const half = 3 * wide / v, top = Math.hypot(wide, v * half);
  const x = s => across((s + half) / (2 * half)), y = km => down(1 - km / top);
  const curve = miss => Array.from({ length: 81 }, (_, i) => {
    const s = half * (i / 40 - 1);
    return (i ? "L" : "M") + x(s).toFixed(1) + " " + y(Math.hypot(miss, v * s)).toFixed(1);
  }).join("");
  const seconds = half < 1 ? half.toFixed(2) : half.toFixed(1);
  let body = `<path d="M${L} ${y(0)}H${W - R}" stroke="#333"/>` +
    label(L, H - 6, "−" + seconds + " s") + label(x(0), H - 6, "closest", "middle") + label(W - R, H - 6, "+" + seconds + " s", "end") +
    label(L - 5, y(top) + 8, short(top), "end") + label(L - 5, y(0), "0", "end") +
    `<path d="${curve(before)}" fill="none" stroke="#fff" stroke-width="1.5"/>`;
  if (after == null) return frame(body + label(x(0), y(before) + 15, dist(before), "middle", true));
  // the two curves are named at the top, in the open mouth of the V
  const name = (row, dash, text) => `<path d="M${x(0) - 66} ${T + 7 + row * 15}h18" stroke="#fff" stroke-width="1.5"${dash ? ' stroke-dasharray="4 3"' : ""}/>` +
    label(x(0) - 42, T + 11 + row * 15, text, "start", true);
  return frame(body + `<path d="${curve(after)}" fill="none" stroke="#fff" stroke-width="1.5" stroke-dasharray="4 3"/>` +
    name(0, false, dist(before) + " now") + name(1, true, dist(after) + " " + afterWord));
}

// every burn on the search grid: when (across) and how hard (up and down), shaded by what it leaves
function burnMap(p) {
  const g = p.search_grid, rows = g.dv_ms.length, cols = g.lead_orbits.length;
  const w = (W - L - R) / cols, h = (H - T - B) / rows;
  const x = j => L + j * w, y = i => T + (rows - 1 - i) * h;
  const shade = (i, j) => g.pc_max_after[i][j] >= 1e-4 ? "#fff"
    : g.pc_max_after[i][j] < 1e-5 && g.pc_after[i][j] < 1e-6 && g.miss_after_km[i][j] > p.miss_before_km ? "#1c1c1c" : "#777";
  let body = "";
  for (let i = 0; i < rows; i++) for (let j = 0; j < cols; j++)
    body += `<rect x="${x(j).toFixed(1)}" y="${y(i).toFixed(1)}" width="${(w + .4).toFixed(1)}" height="${(h + .4).toFixed(1)}" fill="${shade(i, j)}"/>`;
  g.lead_orbits.forEach((lead, j) => { if (Number.isInteger(lead)) body += label(x(j) + w / 2, H - 6, lead, "middle"); });
  body += label(L - 5, T + 9, "faster", "end") + label(L - 5, H - B - 2, "slower", "end");
  if (p.decision === "MANEUVER") {
    const j = g.lead_orbits.indexOf(p.lead_time_orbits);
    const i = g.dv_ms.reduce((best, dv, k) => Math.abs(dv - p.dv_rtn_ms[1]) < Math.abs(g.dv_ms[best] - p.dv_rtn_ms[1]) ? k : best, 0);
    if (j >= 0) body += `<circle cx="${x(j) + w / 2}" cy="${y(i) + h / 2}" r="6" fill="none" stroke="#000" stroke-width="4"/><circle cx="${x(j) + w / 2}" cy="${y(i) + h / 2}" r="6" fill="none" stroke="#fff" stroke-width="1.5"/>`;
  }
  return frame(body);
}

// the worst-case risk of this pass at each run that saw it, and where the model expects it to end
function riskPicture(e) {
  const runs = (e.history || []).filter(r => r.pc_max > 0);
  const logs = runs.map(r => Math.log10(r.pc_max));
  const forecast = e.pc_predicted_final > 0 ? Math.max(-9, Math.log10(e.pc_predicted_final)) : null;
  const all = logs.concat(forecast == null ? [] : [forecast]);
  const hi = Math.max(-3.5, ...all) + .4, lo = Math.min(-5.5, ...all) - .4, steps = all.length - 1;
  const x = i => across(i / (steps || 1)), y = v => down((hi - v) / (hi - lo));
  const time = id => id.slice(9, 11) + ":" + id.slice(11, 13);
  let body = [[-4, "danger"], [-5, "watch"]].map(([v, text]) =>
    `<path d="M${L} ${y(v).toFixed(1)}H${W - R}" stroke="#555" stroke-dasharray="2 4"/>` + label(L - 5, y(v) + 3, text, "end")).join("");
  body += `<path d="${logs.map((v, i) => (i ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1)).join("")}" fill="none" stroke="#fff" stroke-width="1.5"/>`;
  body += logs.map((v, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="2.5" fill="#fff"/>`).join("");
  body += label(L, H - 6, time(runs[0].run_id)) + label(x(logs.length - 1), H - 6, time(runs[runs.length - 1].run_id), forecast == null ? "end" : "middle");
  if (forecast != null) {
    const last = logs.length - 1;
    body += `<path d="M${x(last).toFixed(1)} ${y(logs[last]).toFixed(1)}L${x(steps).toFixed(1)} ${y(forecast).toFixed(1)}" stroke="#fff" stroke-dasharray="2 3"/>` +
      `<circle cx="${(x(steps) - 4).toFixed(1)}" cy="${y(forecast).toFixed(1)}" r="4" fill="#000" stroke="#fff" stroke-width="1.5"/>` + label(x(steps) - 12, y(forecast) + 4, "forecast", "end", true);
  }
  return frame(body);
}

function pictures(d, moved, movedWord) {
  const e = d.event, grid = [moved, d.plan].find(p => p && p.search_grid);
  let html = `<div><h3>Gap at the pass</h3>${gapPicture(e, moved ? moved.miss_after_km : null, movedWord)}<p>Closing at ${e.relative_speed_kms.toFixed(1)} km/s.</p></div>`;
  if (grid) html += `<div><h3>Every burn tried</h3>${burnMap(grid)}<p>Across: orbits before the pass. Dark is safe${grid.decision === "MANEUVER" ? ", the ring is the one chosen" : ""}.</p></div>`;
  if ((e.history || []).length > 1) html += `<div><h3>Risk, run by run</h3>${riskPicture(e)}<p>Worst case at each run${e.pc_predicted_final > 0 ? ". Ring: where the model expects it to end" : ""}.</p></div>`;
  return `<div class="pics">${html}</div>`;
}

// a pass found by checking one satellite: it is not in the run, so it has no plan
function showPass(e) {
  $("plan").innerHTML = `<p class="big">${e.risk_level === "RED" ? "Dangerous" : e.risk_level === "AMBER" ? "Watch" : "Safe"}</p>` + facts(e) + pictures({ event: e });
}

// the two documents written for every dangerous pass of a run: the standard warning message and the briefing
let written = false;
function papers(id) {
  if (!written && source !== "replay") return "";
  const from = "/runs/latest/files/", tail = source === "replay" ? "?source=replay" : "", name = encodeURIComponent(id);
  return `<p class="papers"><a href="${from}cdm/${name}.cdm.txt${tail}" target="_blank">Warning message (CDM)</a><a href="${from}briefings/${name}.briefing.json${tail}" target="_blank">Briefing</a></p>`;
}

async function loadPlan() {
  if (!picked) return;
  const id = picked;
  if (source === "object") { showPass(checked.passes.find(e => e.event_id === id)); return; }
  try {
    const d = await get("/events/" + encodeURIComponent(id) + "?source=" + (source === "replay" ? "replay" : "latest"));
    if (id !== picked) return;
    const p = d.plan, whatIf = d.what_if_plan;
    let html;
    if (!p) html = '<p class="big">Safe</p>' + facts(d.event) + '<p class="why">Low risk. No plan needed.</p>' + pictures(d);
    else if (p.decision === "MANEUVER") html = burn(p, d.event) + papers(id) + pictures(d, p, "after the burn");
    else {
      html = `<p class="big">${p.decision === "MONITOR" ? "Watch" : "No action"}</p>${facts(d.event)}<p class="why">${esc(p.rationale)}</p>`;
      if (whatIf) html += "<h2>What if it moved</h2>" + burn(whatIf, d.event);
      else if (source !== "replay" && !showOnly && !p.requested_at && !SETTLED.includes(p.reason)) html += '<div class="ask"><button id="ask">Plan now</button><span id="asked"></span></div>';
      html += papers(id) + pictures(d, whatIf, "if it moved");
    }
    $("plan").innerHTML = html;
    if ($("ask")) $("ask").onclick = () => askPlan(id);
  } catch (e) { $("plan").innerHTML = '<p class="why">Cannot load this pass.</p>'; }
}

// a run plans only its first few dangerous passes; this searches for a burn for any other one
async function askPlan(id) {
  $("ask").disabled = true;
  $("asked").textContent = "Searching for the smallest safe burn. About 20 seconds, up to a minute.";
  try {
    const r = await fetch("/events/" + encodeURIComponent(id) + "/plan", { method: "POST" });
    const p = await r.json();
    if (id !== picked) return;
    if (!r.ok) { $("asked").textContent = p.detail || "Could not plan this pass."; $("ask").disabled = false; return; }
    // a what-if search that finds no burn is not kept: the decision shown already says why
    if (p.what_if && p.decision !== "MANEUVER") { $("asked").textContent = "No burn to show. " + (p.rationale || ""); return; }
    loadEvents().catch(fail); loadPlan();
  } catch (e) { $("asked").textContent = "Cannot reach the system."; $("ask").disabled = false; }
}

async function loadAlerts() {
  // changes since the previous run, the most serious first, leaving out passes inside one fleet
  const rank = { CRITICAL: 0, WARNING: 1, INFO: 2 };
  const alerts = (await get("/alerts?own_fleet=false")).sort((a, b) => (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3)).slice(0, 5);
  $("alerts").innerHTML = alerts.map(a => `<li>${esc(a.message)}</li>`).join("") || "<li>Nothing new since the previous run.</li>";
}

// --- proof: what the validation pack measured, drawn once in a 340 x 230 frame ---
const PW = 340, PH = 230;
const sheet = body => `<svg viewBox="0 0 ${PW} ${PH}" role="img">${body}</svg>`;

// our closest-approach distance against CelesTrak's for the same passes; a dot on the line is an exact match
function matchPicture(pairs) {
  const logs = pairs.flat().map(Math.log10), lo = Math.min(...logs) - .1, hi = Math.max(...logs) + .1;
  const left = 46, bottom = PH - 26, side = Math.min(PW - left - 8, bottom - 8);
  const x = m => left + (Math.log10(m) - lo) / (hi - lo) * side, y = m => bottom - (Math.log10(m) - lo) / (hi - lo) * side;
  let body = `<path d="M${x(10 ** lo).toFixed(1)} ${y(10 ** lo).toFixed(1)}L${x(10 ** hi).toFixed(1)} ${y(10 ** hi).toFixed(1)}" stroke="#555"/>`;
  for (let p = Math.ceil(lo); p <= Math.floor(hi); p++)
    body += label(x(10 ** p), PH - 8, dist(10 ** p / 1000), "middle") + label(left - 6, y(10 ** p) + 3, dist(10 ** p / 1000), "end");
  body += pairs.map(([theirs, ours]) => `<circle cx="${x(theirs).toFixed(1)}" cy="${y(ours).toFixed(1)}" r="2" fill="#fff" fill-opacity=".85"/>`).join("");
  return sheet(body + label(left + side - 4, bottom - 8, "across: CelesTrak", "end") + label(left + 6, bottom - side + 14, "up: ours"));
}

// how far a public orbit record is from a newer one of the same object, by its age, for each kind of object
function growthPicture(kinds) {
  const lo = -2, hi = 3, left = 46, right = PW - 104, top = 8, bottom = PH - 26;
  const x = d => left + d / 7 * (right - left), y = km => top + (hi - Math.log10(km)) / (hi - lo) * (bottom - top);
  let body = "";
  for (let p = lo; p <= hi; p++)
    body += `<path d="M${left} ${y(10 ** p).toFixed(1)}H${right}" stroke="#262626"/>` + label(left - 6, y(10 ** p) + 3, p < 0 ? Math.round(10 ** p * 1000) + " m" : 10 ** p + " km", "end");
  [1, 3, 5, 7].forEach(d => { body += label(x(d), PH - 8, d + (d === 7 ? " days" : ""), "middle"); });
  const names = { "Other working satellites": "Other working" };
  kinds = kinds.filter(k => k.kind !== "Rocket bodies" && k.kind !== "Iridium NEXT");  // these two lie between debris and dead satellites
  const ends = kinds.map(k => ({ name: names[k.kind] || k.kind, y: y(k.along_track_km[k.along_track_km.length - 1]) })).sort((a, b) => a.y - b.y);
  ends.forEach((e, i) => { if (i && e.y - ends[i - 1].y < 12) e.y = ends[i - 1].y + 12; });  // keep the names apart
  kinds.forEach(k => { body += `<path d="${k.age_days.map((d, i) => (i ? "L" : "M") + x(d).toFixed(1) + " " + y(k.along_track_km[i]).toFixed(1)).join("")}" fill="none" stroke="#fff" stroke-width="1.3"/>`; });
  return sheet(body + ends.map(e => label(right + 6, e.y + 3, e.name, "start", true)).join(""));
}

// of the 10 most dangerous passes, how many stay in the top 10 when one assumption is changed
function keptPicture(rows) {
  const left = 168, full = PW - left - 62, step = 30;
  return sheet(rows.map((r, i) => label(left - 8, 26 + i * step, r.change, "end") +
    `<rect x="${left}" y="${16 + i * step}" width="${(full * r.top10_kept / 10).toFixed(1)}" height="12" fill="#fff"/>` +
    label(left + full * r.top10_kept / 10 + 8, 26 + i * step, r.top10_kept + " of 10", "start", true)).join(""));
}

async function loadProof() {
  const p = await get("/proof"), blocks = [], after = name => short(p.error_growth.kinds.find(k => k.kind === name).after_1_day_km);
  if (p.celestrak && p.celestrak.pairs_m.length) blocks.push(`<h3>Distance, against CelesTrak</h3>${matchPicture(p.celestrak.pairs_m)}
    <p>${p.celestrak.matched} of CelesTrak's ${p.celestrak.pairs_m.length} closest passes, recomputed from the same orbit data. Median difference ${p.celestrak.median_m.toFixed(2)} m.</p>`);
  const band = p.esa.above_one_in_a_million, percent = ((10 ** band.median_difference_log10 - 1) * 100).toFixed(0);
  blocks.push(`<h3>Probability, against ESA</h3><img src="/addons/files/${p.esa.chart}" alt="Our collision probability against the European Space Agency's on the same warnings">
    <p>${n(p.esa.warnings)} real warnings. ${Math.abs(p.esa.median_offset_log10) < .01 ? "No offset. " : ""}For the ${n(band.warnings)} above 1 in a million, the median difference is ${percent}%.</p>`);
  blocks.push(`<h3>Error of public data, by its age</h3>${growthPicture(p.error_growth.kinds)}
    <p>Measured from ${n(p.error_growth.pairs)} pairs of orbit records of ${n(p.error_growth.objects)} objects. After one day: debris ${after("Debris")}, Starlink ${after("Starlink")}.</p>`);
  blocks.push(`<h3>Does the ranking hold?</h3>${keptPicture(p.robustness)}
    <p>Of the 10 most dangerous passes, how many stay in the top 10 when one assumption changes.</p>`);
  $("proof").innerHTML = blocks.map(b => "<div>" + b + "</div>").join("");
  ["proof", "proof-title", "report"].forEach(id => { $(id).hidden = false; });
  if (p.report) { $("full-report").hidden = false; $("full-report").href = "/addons/files/" + p.report; }
}

function refresh() { loadTop().catch(fail); loadEvents().catch(fail); loadAlerts().catch(() => {}); }

$("run").onclick = async () => {
  $("run").disabled = true; failed = false;
  $("status").textContent = "Starting...";
  try {
    const r = await fetch("/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ synthetic: false, quick: true, mode: null }) });
    runId = (await r.json()).run_id;
  } catch (e) { $("run").disabled = false; fail(); }
};

async function poll() {
  if (!runId) return;
  const s = await get("/run/" + runId + "/status");
  const last = s.log.length ? s.log[s.log.length - 1].message : s.stage;
  $("status").textContent = s.status === "RUNNING" ? last : s.status === "DONE" ? "Done." : "Failed. " + (s.error || "");
  if (s.status !== "RUNNING") { runId = null; failed = s.status !== "DONE"; $("run").disabled = false; refresh(); }
}

function show(which, burns, tab) {
  source = which; onlyBurns = burns; picked = null; fleet = null; priority = tab === "showPriority"; shown = null;
  $("plan").innerHTML = '<p class="why">Pick a pass.</p>';
  ["showPriority", "showLatest", "showBurns", "showFleets", "showReplay"].forEach(id => $(id).classList.toggle("on", id === tab));
  if (which !== "object") { $("q").value = ""; $("found").innerHTML = ""; }
  $("about").textContent = which === "fleets" ? "Own fleet: passes between two of its own satellites." : "";
  loadEvents().catch(fail);
}

// --- check any satellite: find it by name or number, then list its close passes from now ---
const kind = o => o.operational ? "working satellite" : o.object_type === "PAYLOAD" ? "dead satellite" : o.object_type.toLowerCase().replace("_", " ");

$("q").oninput = () => {
  const text = $("q").value.trim(), turn = ++typed;
  if (text.length < 2) { $("found").innerHTML = ""; return; }
  setTimeout(async () => {
    if (turn !== typed) return;
    try {
      const found = await get("/objects/search?q=" + encodeURIComponent(text));
      if (turn !== typed) return;
      $("found").innerHTML = found.map(o => `<li data-id="${o.norad_id}" data-name="${esc(o.name)}">${esc(o.name)} <span>${o.norad_id}, ${kind(o)}</span></li>`).join("") || "<li>No object with that name or number.</li>";
      document.querySelectorAll("#found li[data-id]").forEach(li => li.onclick = () => check(li.dataset.id, li.dataset.name));
    } catch (e) { $("found").innerHTML = "<li>Start a run first.</li>"; }
  }, 250);
};

async function check(id, name) {
  typed++; checked = null;
  show("object", false, "");
  $("q").value = name; $("found").innerHTML = "";
  $("about").textContent = "Checking...";
  try {
    const r = await fetch("/objects/" + id + "/passes"), d = await r.json();
    if (source !== "object") return;
    if (!r.ok) { $("about").textContent = d.detail || "Could not check it."; return; }
    checked = d;
    const risky = d.passes.filter(e => e.risk_level !== "GREEN").length;
    $("about").textContent = `${d.passes.length} ${d.passes.length === 1 ? "pass" : "passes"} within ${d.threshold_km} km in ${d.hours} hours, ${risky ? risky + " dangerous" : "none dangerous"}. ${n(d.objects_screened)} objects checked in ${d.seconds} s.`;
    loadEvents();
  } catch (e) { $("about").textContent = "Cannot reach the system."; }
}
$("showPriority").onclick = () => show("latest", false, "showPriority");
$("showLatest").onclick = () => show("latest", false, "showLatest");
$("showBurns").onclick = () => show("latest", true, "showBurns");
$("showFleets").onclick = () => show("fleets", false, "showFleets");
$("showReplay").onclick = () => show("replay", false, "showReplay");

setInterval(() => poll().catch(fail), 2000);
setInterval(() => { if (!runId && !showOnly) refresh(); }, 20000);  // a recorded run does not change
refresh();
loadProof().catch(() => {});  // without the validation pack there is no proof section
