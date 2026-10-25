"use strict";
const $ = (id) => document.getElementById(id);
const colors = {
  U: "#f4f6fa",
  R: "#f65c69",
  F: "#4ec785",
  D: "#f4cf55",
  L: "#f2944b",
  B: "#568ef0",
};
const accents = ["#a7f06b", "#79b8ff", "#e5a0f0", "#ffc078"];
let config,
  source,
  busy = false,
  savedData = null,
  latestData = null,
  replayActive = false,
  replayFrame = 0;
const cards = new Map(),
  charts = [];
const fmt = (n, d = 2) => (n == null ? "N/A" : Number(n).toFixed(d));
const timer = (seconds) => {
  const cs = Math.floor(Math.max(0, seconds) * 100);
  return `${Math.floor(cs / 6000)}:${String(Math.floor(cs / 100) % 60).padStart(2, "0")}.${String(cs % 100).padStart(2, "0")}`;
};
function notice(text, error = false) {
  $("notice").textContent = text;
  $("notice").classList.toggle("error", error);
}
async function api(path, options = {}) {
  const response = await fetch(path, options);
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`Server returned HTTP ${response.status}`);
  }
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
function setBusy(value) {
  busy = value;
  for (const id of [
    "run",
    "newScramble",
    "testSet",
    "seed",
    "length",
    "puzzles",
    "repeats",
    "runMode",
    "replay",
    "savedRuns",
    "replayPuzzle",
    "execution",
    "requestCap",
    "liveConsent",
  ])
    $(id).disabled = value;
}
function drawCube(card, state) {
  if (!state) return;
  card.stickers.forEach((el, i) => {
    el.style.backgroundColor = colors[state[i]];
    el.title = `${"URFDLB"[Math.floor(i / 9)]}${(i % 9) + 1}: ${state[i]}`;
  });
  card.net.setAttribute("aria-label", `Cube state ${state}`);
  card.net.classList.remove("flash");
  requestAnimationFrame(() => card.net.classList.add("flash"));
}
function makeCards(state) {
  $("cards").replaceChildren();
  cards.clear();
  config.models.forEach((model, index) => {
    const el = document.createElement("article");
    el.className = "model-card";
    el.style.setProperty("--card-color", accents[index]);
    el.innerHTML =
      '<div class="card-top"><span class="model-dot"></span><span class="model-name"></span><span class="category"></span><span class="medal"></span></div><div class="card-body"><div class="cube-zone"><div class="cube-net" role="img"></div><span class="face-label">U / L F R B / D · FACELET NET</span></div><div class="metrics"><div class="timer">0:00.00</div><div class="move-count">0 turns · 0 attempts</div><div class="current-move">—</div><div class="status">READY</div><div class="latency footnote">— ms / turn</div></div></div><div class="history" aria-label="Move history"></div>';
    el.querySelector(".model-name").textContent = model.name;
    el.querySelector(".category").textContent = model.category;
    const net = el.querySelector(".cube-net"),
      stickers = [];
    const positions = [
      [0, 3],
      [3, 6],
      [3, 3],
      [6, 3],
      [3, 0],
      [3, 9],
    ];
    for (let face = 0; face < 6; face++)
      for (let i = 0; i < 9; i++) {
        const sticker = document.createElement("span");
        sticker.className = "sticker";
        sticker.style.gridRow = positions[face][0] + Math.floor(i / 3) + 1;
        sticker.style.gridColumn = positions[face][1] + (i % 3) + 1;
        net.append(sticker);
        stickers.push(sticker);
      }
    $("cards").append(el);
    const card = {
      el,
      net,
      stickers,
      active: false,
      started: 0,
      elapsed: 0,
      game: null,
    };
    cards.set(model.key, card);
    drawCube(card, state);
  });
}
function setStatus(card, text, kind = "") {
  const node = card.el.querySelector(".status");
  node.textContent = text;
  node.className = `status ${kind}`;
}
function showPuzzle(p) {
  $("scramble").textContent = p.scramble.join(" ");
  $("startState").textContent = p.start_state;
  $("optimum").textContent =
    p.exact_optimal == null ? "N/A" : `${p.exact_optimal} turns`;
  makeCards(p.start_state);
  $("progress").textContent =
    `Seed ${p.seed}${p.repeat != null ? " · repeat " + (p.repeat + 1) : ""}`;
}
function handle(kind, p) {
  if (kind === "puzzle") {
    showPuzzle(p);
    for (const game of p.completed_games || [])
      handle("game_end", { model: game.model, game });
    return;
  }
  if (kind === "ranking") {
    for (const [key, rank] of Object.entries(p.ranks)) {
      const card = cards.get(key);
      if (card)
        card.el.querySelector(".medal").textContent = [
          "🥇 1st",
          "🥈 2nd",
          "🥉 3rd",
          "4th",
        ][rank - 1];
    }
    return;
  }
  const card = cards.get(p.model);
  if (!card) return;
  if (kind === "game_start" || kind === "game_end") {
    let provenance = card.el.querySelector(".provenance");
    if (!provenance) {
      provenance = document.createElement("span");
      provenance.className = "provenance";
      card.el.querySelector(".model-name").append(provenance);
    }
    provenance.textContent = p.game.mock ? "SIMULATED" : "LIVE RECORDING";
  }
  if (kind === "game_start") {
    card.active = true;
    card.started = performance.now();
    card.elapsed = 0;
    card.game = p.game;
    setStatus(card, "STARTING");
    drawCube(card, p.game.start_state);
  }
  if (kind === "thinking") {
    card.active = true;
    card.started = performance.now() - p.elapsed_s * 1000;
    setStatus(
      card,
      config.models.find((m) => m.key === p.model).category === "LLM"
        ? "THINKING…"
        : "DECIDING…",
    );
  }
  if (kind === "move") {
    const r = p.record;
    drawCube(card, r.state_after);
    card.elapsed = r.elapsed_s;
    card.started = performance.now() - r.elapsed_s * 1000;
    card.el.querySelector(".current-move").textContent = r.valid
      ? r.move
      : "INVALID / FAILED";
    card.el.querySelector(".move-count").textContent =
      `${p.moves_used} turns · ${p.attempts_used} / ${card.game?.config?.max_moves || config.max_moves} attempts`;
    card.el.querySelector(".latency").textContent =
      `${fmt(r.latency_ms, 0)} ms · incl. retries ${fmt(r.latency_incl_retries_ms, 0)}`;
    const node = document.createElement("span");
    node.textContent = `${r.index}. ${r.valid ? r.move : "×"}`;
    node.classList.toggle("bad", !r.valid);
    node.title = r.response.error || `${fmt(r.latency_ms)} ms`;
    const history = card.el.querySelector(".history");
    history.append(node);
    history.scrollTop = history.scrollHeight;
  }
  if (kind === "game_end") {
    const g = p.game;
    let failureNote = card.el.querySelector(".failure-note");
    if (!failureNote) {
      failureNote = document.createElement("p");
      failureNote.className = "failure-note";
      card.el.append(failureNote);
    }
    const truncated = g.status !== "SOLVED" && g.records.some(r =>
      (r.response.calls || []).some(c => (c.raw_response?.choices || []).some(choice =>
        choice.finish_reason === "length" || choice.native_finish_reason === "max_tokens")));
    failureNote.textContent = truncated
      ? "The model hit its completion-token limit before returning a complete move. The failed call may still be billed."
      : g.error || "";
    failureNote.hidden = !failureNote.textContent;
    card.active = false;
    card.elapsed = g.total_time_s;
    card.game = g;
    drawCube(card, g.final_state);
    card.el.querySelector(".timer").textContent = timer(g.total_time_s);
    card.el.querySelector(".move-count").textContent =
      `${g.moves_used} turns · ${g.attempts_used} attempts`;
    card.el.querySelector(".latency").textContent =
      `${fmt(g.avg_latency_ms, 0)} ms avg · gap ${g.optimality_gap ?? "N/A"}`;
    setStatus(
      card,
      g.status === "SOLVED" ? "SOLVED ✓" : g.status.replaceAll("_", " "),
      g.status === "SOLVED" ? "solved" : "failed",
    );
    if (g.error) card.el.querySelector(".status").title = g.error;
  }
}
function tick() {
  if (!replayActive)
    for (const card of cards.values())
      if (card.active)
        card.el.querySelector(".timer").textContent = timer(
          (performance.now() - card.started) / 1000,
        );
  requestAnimationFrame(tick);
}
async function preview() {
  const p = await api(
    `/api/puzzle?seed=${encodeURIComponent($("seed").value)}&length=${encodeURIComponent($("length").value)}`,
  );
  showPuzzle(p);
}
function view(stats) {
  $("raceView").hidden = stats;
  $("statsView").hidden = !stats;
  $("viewStats").classList.toggle("active", stats);
  $("viewRace").classList.toggle("active", !stats);
}
async function refreshRuns() {
  const runs = await api("/api/runs");
  const previous = $("savedRuns").value;
  $("savedRuns").replaceChildren(new Option("Choose a recording…", ""));
  for (const run of runs)
    $("savedRuns").add(
      new Option(
        `${run.mock ? "[MOCK]" : "[LIVE]"} ${run.run_id} · ${run.games} games`,
        run.run_id,
      ),
    );
  if (runs.some((r) => r.run_id === previous)) $("savedRuns").value = previous;
}
async function selectRun(id) {
  savedData = await api(`/api/runs/${encodeURIComponent(id)}`);
  latestData = savedData;
  $("modeBadge").textContent = savedData.metadata.mock
    ? "SYNTHETIC RECORDING"
    : "LIVE RECORDING";
  $("export").disabled = false;
  await refreshBilling();
  const keys = [
    ...new Set(savedData.games.map((g) => `${g.puzzle_id}|${g.repeat}`)),
  ];
  $("replayPuzzle").replaceChildren();
  for (const key of keys)
    $("replayPuzzle").add(new Option(key.replace("|", " · repeat "), key));
  renderStats(savedData);
  notice(
    `${savedData.metadata.mock ? "SYNTHETIC MOCK" : "LIVE"} saved results loaded. Replay or open Statistical benchmarks.`,
  );
}
async function run() {
  if (!config.student_name.trim() || !config.roll_number.trim()) {
    notice(
      "Set STUDENT_NAME and ROLL_NUMBER in .env, then restart the server before recording.",
      true,
    );
    return;
  }
  const live = $("execution").value === "live";
  const request = {
    set: $("testSet").value,
    puzzles: Number($("puzzles").value),
    repeats: Number($("repeats").value),
    mode: $("runMode").value,
    seed: Number($("seed").value),
    length: Number($("length").value),
    execution: live ? "live" : "simulated",
    live_approved: false,
    request_cap: live ? Number($("requestCap").value) : null,
  };
  if (live) {
    if (
      !$("liveConsent").checked ||
      !Number.isInteger(request.request_cap) ||
      request.request_cap < 1
    ) {
      notice(
        "Enter a whole-number API request cap (for example 4, not a dollar amount), then approve paid requests for this run.",
        true,
      );
      return;
    }
    const approved = await approveLive(request);
    $("liveConsent").checked = false;
    if (!approved) return;
    request.live_approved = true;
  }
  $("modeBadge").textContent = live ? "LIVE EXPERIMENT" : "SYNTHETIC MOCK";
  stopReplay();
  view(false);
  setBusy(true);
  notice(
    !live
      ? "SYNTHETIC MOCK RACE — programmed behaviors, not measurements of the named models."
      : "Live benchmark running. Calls may spend OpenRouter credits.",
  );
  try {
    const { run_id } = await api("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    source = new EventSource(`/api/runs/${run_id}/events`);
    for (const kind of [
      "puzzle",
      "game_start",
      "thinking",
      "move",
      "game_end",
      "ranking",
    ])
      source.addEventListener(kind, (e) => handle(kind, JSON.parse(e.data)));
    source.addEventListener("benchmark_done", async () => {
      source.close();
      setBusy(false);
      try {
        await refreshBilling();
        await refreshRuns();
        $("savedRuns").value = run_id;
        await selectRun(run_id);
        notice(
          "Benchmark complete. Final rankings are shown; open Statistical benchmarks for the report.",
        );
      } catch (e) {
        notice(e.message, true);
      }
    });
    source.addEventListener("run_error", (e) => {
      source.close();
      setBusy(false);
      notice(JSON.parse(e.data).message, true);
      refreshRuns().catch(() => {});
    });
    source.onerror = () =>
      notice(
        "Live connection interrupted; reconnecting automatically. Completed games are saved.",
      );
  } catch (e) {
    setBusy(false);
    notice(e.message, true);
  }
}
function rank(games) {
  return games.filter(g => g.status !== "NOT_RUN" && !g.diagnostic).sort((a, b) => {
    const solved = (g) => g.status === "SOLVED";
    if (solved(a) !== solved(b)) return solved(a) ? -1 : 1;
    const correct = (g) =>
      [...g.final_state].filter((x, i) => x === "URFDLB"[Math.floor(i / 9)])
        .length;
    return (
      (solved(a) ? a.moves_used - b.moves_used : correct(b) - correct(a)) ||
      a.total_time_s - b.total_time_s ||
      a.model.localeCompare(b.model)
    );
  });
}
function stopReplay() {
  replayActive = false;
  cancelAnimationFrame(replayFrame);
  for (const card of cards.values()) card.active = false;
  $("stopReplay").disabled = true;
  if (!source || source.readyState === EventSource.CLOSED) setBusy(false);
}
function replay() {
  if (!savedData) return notice("Select a saved run first.", true);
  stopReplay();
  const [pid, rep] = $("replayPuzzle").value.split("|");
  const games = savedData.games.filter(
    (g) => g.puzzle_id === pid && g.repeat === Number(rep),
  );
  if (!games.length) return;
  view(false);
  setBusy(true);
  replayActive = true;
  $("stopReplay").disabled = false;
  const first = games[0];
  showPuzzle(first);
  const timeline = [];
  let offset = 0;
  for (const g of games) {
    const base = savedData.metadata.mode === "sequential" ? offset : 0;
    timeline.push({
      t: base,
      kind: "game_start",
      data: { model: g.model, game: g },
    });
    for (const r of g.records)
      timeline.push({
        t: base + r.elapsed_s,
        kind: "move",
        data: {
          model: g.model,
          record: r,
          moves_used: g.records.filter((x) => x.index <= r.index && x.valid)
            .length,
          attempts_used: g.records.filter(
            (x) =>
              x.index <= r.index &&
              (x.valid || g.config.invalid_consumes_attempt),
          ).length,
        },
      });
    timeline.push({
      t: base + g.total_time_s,
      kind: "game_end",
      data: { model: g.model, game: g },
    });
    if (savedData.metadata.mode === "sequential") offset += g.total_time_s;
  }
  timeline.sort((a, b) => a.t - b.t);
  let cursor = 0,
    virtual = 0,
    last = performance.now();
  notice(
    `${savedData.metadata.mock ? "SYNTHETIC MOCK" : "LIVE"} recording replay · original timings scaled by speed control.`,
  );
  function frame(now) {
    if (!replayActive) return;
    virtual += ((now - last) / 1000) * Number($("speed").value);
    last = now;
    while (cursor < timeline.length && timeline[cursor].t <= virtual) {
      const e = timeline[cursor++];
      handle(e.kind, e.data);
      if (e.kind === "game_start") {
        const card = cards.get(e.data.model);
        card.replayStart = e.t;
        setStatus(card, "REPLAYING…");
      }
    }
    for (const card of cards.values())
      if (card.active)
        card.el.querySelector(".timer").textContent = timer(
          virtual - card.replayStart,
        );
    $("progress").textContent =
      `REPLAY · ${timer(virtual)} · ${$("speed").value}×`;
    if (cursor >= timeline.length) {
      const ranks = Object.fromEntries(
        rank(games).map((g, i) => [g.model, i + 1]),
      );
      handle("ranking", { ranks });
      stopReplay();
      notice("Replay complete.");
      return;
    }
    replayFrame = requestAnimationFrame(frame);
  }
  replayFrame = requestAnimationFrame(frame);
}
function chart(id, type, labels, data, title) {
  if (!window.Chart) return;
  charts.push(
    new Chart($(id), {
      type,
      data: {
        labels,
        datasets: [
          {
            label: title,
            data,
            backgroundColor: accents.map((c) => c + "bb"),
            borderColor: accents,
            borderWidth: 1,
            borderRadius: type === "bar" ? 5 : 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            grid: { color: "#273044" },
            ticks: { color: "#a5b0c2" },
            title: {
              display: type === "bubble",
              text: "Mean turn latency (ms)",
              color: "#a5b0c2",
            },
          },
          y: {
            beginAtZero: true,
            max: id === "successChart" ? 100 : undefined,
            grid: { color: "#273044" },
            ticks: { color: "#a5b0c2" },
            title: {
              display: type === "bubble",
              text: "Mean proven gap (HTM)",
              color: "#a5b0c2",
            },
          },
        },
      },
    }),
  );
}
function renderStats(data) {
  charts.splice(0).forEach((c) => c.destroy());
  const rows = data.summary;
  $("sampleLabel").textContent =
    `${data.games.length} attempts · ${data.metadata.mode} · ${data.metadata.mock ? "SYNTHETIC MOCK" : "LIVE API"}`;
  $("summaryRows").replaceChildren();
  $("winners").replaceChildren();
  $("distributions").replaceChildren();
  const labels = rows.map((r) => r.name);
  for (const r of rows) {
    const tr = document.createElement("tr");
    const values = [
      r.name,
      `${fmt(r.avg_latency_ms)} / ${fmt(r.median_latency_ms)} / ${fmt(r.p95_latency_ms)}`,
      fmt(r.avg_latency_incl_retries_ms),
      `${fmt(r.avg_solve_time_s)} / ${fmt(r.total_time_s)}`,
      r.total_moves,
      r.attempts
        ? `${fmt(r.success_rate, 1)}% (${r.solved}/${r.attempts})`
        : "N/A (not attempted)",
      fmt(r.avg_solved_moves),
      `${fmt(r.gap_mean)} / ${fmt(r.gap_median)}`,
      `${r.unsolved} / ${r.unavailable} / ${r.not_run || 0}`,
      `${r.invalid_count} / ${r.retry_count}`,
      `${r.tokens ?? "N/A"} / ${r.cost == null ? "N/A" : fmt(r.cost, 6)}`,
    ];
    for (const value of values) {
      const td = document.createElement("td");
      td.textContent = value;
      tr.append(td);
    }
    $("summaryRows").append(tr);
    const block = document.createElement("article"),
      h = document.createElement("h3"),
      p = document.createElement("p");
    h.textContent = r.name;
    p.textContent = `Gap distribution (HTM: count): ${JSON.stringify(r.gap_distribution)}. Solve rate by scramble length (%): ${JSON.stringify(r.solve_rate_by_length)}. Raw individual call mean: ${fmt(r.avg_raw_call_ms)} ms. Scheduled ${r.scheduled || r.attempts}; not run ${r.not_run || 0}; smoke diagnostics ${r.smoke_tests || 0}. Requests ${r.requests_used || 0}; known billed USD ${r.known_cost == null ? "unknown" : fmt(r.known_cost, 6)}; unknown-cost requests ${r.unknown_cost_requests || 0}; reasoning tokens ${r.reasoning_tokens ?? "unknown"}.`;
    block.append(h, p);
    $("distributions").append(block);
  }
  for (const [label, key, descending] of [
    ["Fastest observed", "avg_latency_ms", false],
    ["Highest solve rate", "success_rate", true],
    ["Smallest proven gap", "gap_mean", false],
  ]) {
    const eligible = rows.filter(
      (r) => r[key] != null && r.attempts > 0 && r.unavailable < r.attempts,
    );
    if (!eligible.length) continue;
    const best = eligible.reduce((a, b) =>
      (descending ? b[key] > a[key] : b[key] < a[key]) ? b : a,
    );
    if (key === "success_rate" && best.success_rate === 0) continue;
    const tied = eligible.filter((r) => r[key] === best[key]);
    const el = document.createElement("span");
    el.className = "winner";
    el.textContent = `★ ${label}: ${tied.map((r) => r.name).join(" & ")}`;
    $("winners").append(el);
  }
  chart(
    "latencyChart",
    "bar",
    labels,
    rows.map((r) => r.avg_latency_ms),
    "Mean turn ms",
  );
  chart(
    "successChart",
    "bar",
    labels,
    rows.map((r) => r.success_rate),
    "Solve %",
  );
  chart(
    "gapChart",
    "bar",
    labels,
    rows.map((r) => r.gap_mean),
    "Gap HTM",
  );
  // Chart.js bubble datasets cannot contain null points. Failed/unproven games
  // stay in the table and bar charts, but have no defined quality coordinate.
  const scatterRows = rows.filter(
    (r) => r.gap_mean != null && r.avg_latency_ms != null,
  );
  chart(
    "scatterChart",
    "bubble",
    scatterRows.map((r) => r.name),
    scatterRows.map((r) => ({
      x: r.avg_latency_ms,
      y: r.gap_mean,
      r: Math.max(3, r.success_rate / 5),
    })),
    "Latency / gap",
  );
  $("answers").replaceChildren();
  for (const answer of data.answers || []) {
    const li = document.createElement("li");
    li.textContent = answer;
    $("answers").append(li);
  }
  if (!window.Chart)
    notice(
      "Chart CDN unavailable. The statistics table and report remain available.",
      true,
    );
}
async function init() {
  try {
    config = await api("/api/config");
    $("identity").textContent =
      `Student: ${config.student_name || "NOT CONFIGURED"} | Roll No: ${config.roll_number || "NOT CONFIGURED"}`;
    $("execution").value = "simulated";
    if (config.mock)
      $("execution").querySelector('option[value="live"]').disabled = true;
    updateExecution();
    notice(
      !config.student_name || !config.roll_number
        ? "Set student name and roll number in .env before recording."
        : config.mock
          ? "Mock mode: programmed behaviors for UI testing; no API credits used."
          : "Ready. Simulation is free. Live runs require a request cap and approval.",
    );
    await preview();
    await refreshRuns();
    await refreshBilling();
    tick();
  } catch (e) {
    notice(e.message, true);
  }
}
$("run").onclick = run;
$("viewRace").onclick = () => view(false);
$("viewStats").onclick = () => {
  view(true);
  if (latestData) renderStats(latestData);
  else notice("Complete a benchmark or select a saved run to see statistics.");
};
$("newScramble").onclick = () => {
  const seed = crypto.getRandomValues(new Uint32Array(1))[0];
  $("seed").value = seed;
  preview().catch((e) => notice(e.message, true));
};
for (const id of ["seed", "length"])
  $(id).onchange = () => preview().catch((e) => notice(e.message, true));
$("testSet").onchange = () => {
  const value = $("testSet").value;
  $("puzzles").value = {
    race: 1,
    smoke: 1,
    warmup: 2,
    primary: 5,
    extension: 5,
  }[value];
  $("puzzles").min = value === "primary" ? 5 : 1;
  $("repeats").value = 1;
  $("length").disabled = !["race", "smoke"].includes(value);
  updateExecution();
  notice(
    value === "race"
      ? "Single puzzle race selected."
      : "Seed is the reproducible offset for the fixed benchmark seed list; the next puzzle is streamed when ready.",
  );
};
$("savedRuns").onchange = () => {
  if ($("savedRuns").value)
    selectRun($("savedRuns").value).catch((e) => notice(e.message, true));
};
$("replay").onclick = replay;
$("stopReplay").onclick = stopReplay;
function updateExecution() {
  const live = $("execution").value === "live";
  $("liveControls").hidden = !live;
  $("run").textContent = live ? "Review live run" : "Run simulation";
  $("modeBadge").textContent = live
    ? "LIVE · APPROVAL REQUIRED"
    : "SIMULATION · FREE";
  const cap =
    $("testSet").value === "smoke"
      ? 4
      : Number($("puzzles").value) *
        Number($("repeats").value) *
        4 *
        30 *
        (1 + config.max_retries);
  $("recommendedCap").textContent =
    `Recommended cap: ${cap} requests. Claude: ${config.claude_reasoning_effort} effort / ${config.claude_max_tokens} output tokens.`;
}
async function refreshBilling() {
  const b = await api("/api/billing");
  $("billing").textContent =
    `Suite: ${b.requests_used} / ${b.request_limit} live requests · known billed USD ${b.known_cost == null ? "unknown" : b.known_cost.toFixed(6)} · ${b.unknown_cost_requests} requests with unknown cost`;
  const run = savedData?.metadata?.billing;
  if (run)
    $("billing").textContent +=
      ` | Selected run: ${run.requests_used} / ${run.request_limit} requests · known USD ${run.known_cost == null ? "unknown" : run.known_cost.toFixed(6)} · ${run.unknown_cost_requests} unknown-cost requests`;
}
function approveLive(request) {
  $("approvalDescription").textContent =
    `${request.set}: ${request.puzzles} puzzle(s), ${request.repeats} repeat(s), four assigned models. Hard cap: ${request.request_cap} requests. ${$("recommendedCap").textContent}`;
  return new Promise((resolve) => {
    const dialog = $("approvalDialog");
    const finish = (approved) => {
      dialog.close();
      resolve(approved);
    };
    $("approvePaid").onclick = () => finish(true);
    $("cancelPaid").onclick = () => finish(false);
    dialog.oncancel = (event) => {
      event.preventDefault();
      finish(false);
    };
    dialog.showModal();
  });
}
$("execution").onchange = () => {
  $("liveConsent").checked = false;
  updateExecution();
};
for (const id of ["puzzles", "repeats"]) $(id).onchange = updateExecution;
$("export").onclick = () => {
  if (!savedData) return;
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(savedData, null, 2)], {
      type: "application/json",
    }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `${savedData.metadata.run_id}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
init();
