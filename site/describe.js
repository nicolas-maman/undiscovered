// The browser client: choose a model, describe a unit, send the result.
// The rules (prompt, checks, result) are core.js's, the Python client's own.
(function () {
  "use strict";
  var core = window.UndiscoveredCore, text = window.UndiscoveredText;
  var REPO = "nicolas-maman/undiscovered";
  var RAW = "https://raw.githubusercontent.com/" + REPO + "/distill-2025/";
  var WEBLLM = "https://esm.run/@mlc-ai/web-llm@0.2.86";
  var WEBLLM_MODELS = [
    {id: "Qwen3-4B-q4f16_1-MLC", label: "Qwen3 4B: the best of these, about 3.4 GB of graphics memory"},
    {id: "Llama-3.2-3B-Instruct-q4f16_1-MLC", label: "Llama 3.2 3B: about 2.3 GB"},
    {id: "Qwen3-1.7B-q4f16_1-MLC", label: "Qwen3 1.7B: lighter, about 2 GB"}
  ];
  var PROVIDERS = {
    gemini: {label: "Google Gemini", kind: "google", base: "https://generativelanguage.googleapis.com/v1beta",
             keys: "https://aistudio.google.com/apikey",
             note: "Free key. Google uses what is sent on its free tier to improve its products; abstracts are public."},
    groq: {label: "Groq", kind: "openai-compatible", base: "https://api.groq.com/openai/v1",
           keys: "https://console.groq.com/keys", note: "Free key, about 1,000 requests a day per model: dozens of units."},
    openrouter: {label: "OpenRouter", kind: "openai-compatible", base: "https://openrouter.ai/api/v1",
                 keys: "https://openrouter.ai/keys",
                 note: "Models whose name ends in :free cost nothing, 50 requests a day: two units."},
    mistral: {label: "Mistral", kind: "openai-compatible", base: "https://api.mistral.ai/v1",
              keys: "https://console.mistral.ai", note: "Free mode, within its rate limits."},
    openai: {label: "OpenAI", kind: "openai-compatible", base: "https://api.openai.com/v1",
             keys: "https://platform.openai.com/api-keys", note: "Paid, billed to you by OpenAI."},
    anthropic: {label: "Anthropic", kind: "anthropic", base: "https://api.anthropic.com/v1",
                keys: "https://console.anthropic.com", note: "Paid, billed to you by Anthropic."}
  };
  var $ = function (id) { return document.getElementById(id); };
  var state = {engine: null, engineId: "", stop: false, running: false};

  // Storage may be off (private windows); everything works without it.
  function load(k, area) { try { return (area || localStorage).getItem("undiscovered." + k); } catch (e) { return null; } }
  function save(k, v, area) { try { (area || localStorage).setItem("undiscovered." + k, v); } catch (e) { /* none */ } }
  function forget(k) { try { localStorage.removeItem("undiscovered." + k); } catch (e) { /* none */ } }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") { e.textContent = attrs[k]; } else if (k === "class") { e.className = attrs[k]; } else { e.setAttribute(k, attrs[k]); }
    });
    (kids || []).forEach(function (c) { if (c) { e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); } });
    return e;
  }
  function status(id, msg, kind) { var s = $(id); s.textContent = msg; s.className = "status" + (kind ? " " + kind : ""); }

  // ---- step 1: the model -------------------------------------------------

  var hasGPU = !!navigator.gpu;
  if (!hasGPU) {
    $("choice-browser").classList.add("off");
    $("choice-browser").querySelector("input").disabled = true;
    $("gpu-note").textContent = "This browser has no WebGPU, so it cannot run a model itself. Recent Chrome, Edge " +
      "and Safari do; or use a key.";
  }
  WEBLLM_MODELS.forEach(function (m) { $("webllm-model").appendChild(el("option", {value: m.id, text: m.label})); });
  Object.keys(PROVIDERS).forEach(function (k) { $("provider").appendChild(el("option", {value: k, text: PROVIDERS[k].label})); });

  function kind() { var c = document.querySelector("input[name=kind]:checked"); return c ? c.value : ""; }

  function showProvider() {
    var p = PROVIDERS[$("provider").value];
    $("provider-note").textContent = "";
    $("provider-note").appendChild(document.createTextNode(p.note + " "));
    $("provider-note").appendChild(el("a", {href: p.keys, target: "_blank", rel: "noopener", text: "Get a key"}));
    $("key").value = load("key." + $("provider").value) || load("key." + $("provider").value, sessionStorage) || "";
    $("hosted-model").value = load("model." + $("provider").value) || "";
    $("remember").checked = !!load("key." + $("provider").value);
  }

  // The model as results name it, and how to ask it a question.
  function model() {
    var k = kind();
    if (k === "browser") { return {provider: "webllm", id: $("webllm-model").value}; }
    if (k === "hosted") {
      var p = PROVIDERS[$("provider").value];
      return {provider: p.kind, id: $("hosted-model").value.trim(), base: p.base, key: $("key").value.trim()};
    }
    if (k === "local") { return {provider: "openai-compatible", id: $("local-model").value.trim(), base: $("local-base").value.trim(), key: ""}; }
    return null;
  }
  function ready() { var m = model(); return !!(m && m.id && (m.provider === "webllm" || m.base)); }

  function refresh() {
    ["browser", "hosted", "local"].forEach(function (k) { $("panel-" + k).hidden = kind() !== k; });
    $("test").disabled = !ready() || state.running;
    $("start").disabled = !ready() || state.running;
    if (!state.running && !state.finished) { status("unit-status", ready() ? "Ready." : "Choose a model first."); }
    if (kind()) { save("kind", kind()); }
  }

  function remember() {
    var p = $("provider").value, m = model();
    if (kind() === "hosted") {
      save("model." + p, m.id);
      if ($("remember").checked) { save("key." + p, m.key); } else { forget("key." + p); save("key." + p, m.key, sessionStorage); }
    }
    if (kind() === "local") { save("local.base", $("local-base").value.trim()); save("local.model", $("local-model").value.trim()); }
    if (kind() === "browser") { save("webllm", $("webllm-model").value); }
  }

  async function webllm(m, onProgress) {
    if (state.engine && state.engineId === m.id) { return state.engine; }
    var lib = await import(WEBLLM);
    state.engine = await lib.CreateMLCEngine(m.id, {initProgressCallback: function (p) { onProgress(p.text || ""); }});
    state.engineId = m.id;
    return state.engine;
  }

  // One question, waiting and retrying when the service is busy or limits the pace, as the Python client does.
  async function ask(m, system, user, onWait) {
    if (m.provider === "webllm") {
      var engine = await webllm(m, onWait);
      var reply = await engine.chat.completions.create({
        messages: [{role: "system", content: system}, {role: "user", content: user}],
        temperature: 0, max_tokens: core.MAX_TOKENS, extra_body: {enable_thinking: false}});
      return reply.choices[0].message.content || "";
    }
    var req = core.request(m, system, user), delay = 2;
    for (var attempt = 0; attempt < 8; attempt++) {
      var wait = (state.interval || 0) * 1000 - (Date.now() - (state.last || 0));
      if (wait > 0) { await sleep(wait); }
      state.last = Date.now();
      var resp;
      try {
        resp = await fetch(req.url, {method: "POST", headers: Object.assign({"Content-Type": "application/json"}, req.headers),
                                     body: JSON.stringify(req.body)});
      } catch (e) {
        if (attempt === 7) { throw new Error("cannot reach the model at " + m.base + " (" + e.message + ")"); }
        await sleep(delay * 1000); delay = Math.min(delay * 2, 60); continue;
      }
      if (resp.ok) { return core.answerText(m.provider, await resp.json()); }
      var after = parseFloat(resp.headers.get("retry-after") || "") || 0;
      if (resp.status === 429) {
        state.interval = Math.min(30, Math.max(2, (state.interval || 0) * 2));
        if (onWait) { onWait("the service asks to slow down; waiting " + Math.round(after || delay) + " s"); }
        await sleep((after || delay) * 1000); delay = Math.min(delay * 2, 120); continue;
      }
      if ([500, 502, 503, 504, 529].indexOf(resp.status) >= 0 && attempt < 7) {
        await sleep((after || delay) * 1000); delay = Math.min(delay * 2, 60); continue;
      }
      throw new Error("the model answered " + resp.status + ": " + (await resp.text()).slice(0, 300));
    }
    throw new Error("the model kept saying it is busy or that we ask too often; if it has a daily limit, it may be reached");
  }

  async function listModels(m, datalistId, statusId) {
    status(statusId, "Asking for its models...");
    try {
      var url = m.base.replace(/\/+$/, "") + "/models", headers = {};
      if (m.provider === "google") { headers["x-goog-api-key"] = m.key; }
      else if (m.provider === "anthropic") {
        headers = {"x-api-key": m.key, "anthropic-version": "2023-06-01", "anthropic-dangerous-direct-browser-access": "true"};
      } else if (m.key) { headers.Authorization = "Bearer " + m.key; }
      var resp = await fetch(url, {headers: headers});
      if (!resp.ok) { throw new Error("it answered " + resp.status); }
      var data = await resp.json(), ids;
      if (m.provider === "google") {
        ids = (data.models || []).filter(function (x) { return (x.supportedGenerationMethods || []).indexOf("generateContent") >= 0; })
          .map(function (x) { return x.name.replace(/^models\//, ""); });
      } else { ids = (data.data || []).map(function (x) { return x.id; }); }
      var list = $(datalistId);
      list.textContent = "";
      ids.sort().forEach(function (id) { list.appendChild(el("option", {value: id})); });
      status(statusId, ids.length + " models; start typing in the Model box to pick one.", "ok");
    } catch (e) {
      status(statusId, "Could not list its models (" + e.message + "). Check the key or the address.", "bad");
    }
  }

  async function test() {
    var m = model();
    remember();
    $("test").disabled = true;
    status("test-status", m.provider === "webllm" ? "Loading the model; the first time, this is the download..." : "Asking...");
    var t = Date.now();
    try {
      var answer = await ask(m, core.SYSTEM, core.prompt("Describe the task this work carries out as an abstract computation.",
        "Forecasting seasonal outbreaks of influenza",
        "We forecast the timing of seasonal influenza peaks by combining a model of transmission with weekly " +
        "surveillance counts, updating the model's state as each week's data arrive.", []),
        function (msg) { status("test-status", msg); });
      var d = core.parse(answer);
      status("test-status", "It works (" + ((Date.now() - t) / 1000).toFixed(1) + " s): " + d.problem, "ok");
    } catch (e) {
      status("test-status", "Not yet: " + e.message, "bad");
    }
    $("test").disabled = false;
  }

  // ---- step 2: a unit ----------------------------------------------------

  function modelName(m) { return m.id + " (" + m.provider + ")"; }
  function done() { try { return JSON.parse(load("done") || "[]"); } catch (e) { return []; } }

  // A unit this model has not described, waiting for a second model first (as cli.pick_unit).
  function pick(index, m) {
    var mine = modelName(m), skip = done();
    var todo = index.units.filter(function (u) {
      return (u.status === "open" || u.status === "check") && (u.models || []).indexOf(mine) < 0 &&
             skip.indexOf(u.unit + " " + mine) < 0;
    });
    var waiting = todo.filter(function (u) { return u.status === "check"; });
    var pool = waiting.length ? waiting : todo;
    return pool.length ? pool[Math.floor(Math.random() * pool.length)] : null;
  }

  async function getJSON(url) {
    var r = await fetch(url, {cache: "no-store"});
    if (!r.ok) { throw new Error(url.split("/").pop() + ": " + r.status); }
    return r.json();
  }

  async function works(ids) {
    var data = await getJSON("https://api.openalex.org/works?filter=openalex:" + ids.join("|") + "&per_page=" + ids.length +
                             "&select=id,title,abstract_inverted_index");
    var out = {};
    (data.results || []).forEach(function (w) {
      out[w.id.split("/").pop()] = {title: (w.title || "").trim(), abstract: core.abstractText(w.abstract_inverted_index)};
    });
    return out;
  }

  function paperRow(w, info, paper) {
    var row = el("li", {class: "paper"});
    row.appendChild(el("div", {class: "head"}, [
      el("span", {class: "state", text: "waiting"}),
      el("span", {class: "t"}, [el("a", {href: "https://openalex.org/" + w, target: "_blank", rel: "noopener",
                                         text: (info && info.title) || w}), " ",
                                el("span", {class: "field", text: paper ? (paper.field || paper.domain || "") : ""})])]));
    return row;
  }

  function setState(row, label, cls) { var s = row.querySelector(".state"); s.textContent = label; s.className = "state " + (cls || ""); }

  async function run() {
    var m = model();
    remember();
    state.running = true; state.stop = false;
    refresh();
    $("stop").hidden = false;
    $("send").textContent = ""; $("resemble").textContent = ""; $("papers").textContent = "";
    $("progress").style.width = "0";
    try {
      status("unit-status", "Fetching the units...");
      var index = await getJSON(RAW + "units/index.json");
      var papers = await getJSON(RAW + "papers.json").catch(function () { return {}; });
      var unit = pick(index, m);
      if (!unit) { status("unit-status", "No unit is left for " + m.id + ". Thank you, or try another model.", "ok"); return; }
      var have = (unit.models || []).length;
      status("unit-status", unit.unit + ": " + unit.works.length + " papers" +
             (have ? ", already described by " + unit.models.join(", ") + "; yours completes it" : "") + ". Fetching abstracts...");
      var info = await works(unit.works), rows = {};
      unit.works.forEach(function (w) { rows[w] = paperRow(w, info[w], papers[w]); $("papers").appendChild(rows[w]); });
      if (m.provider === "webllm") { status("unit-status", "Loading the model; the first time, this is the download..."); }

      var out = [], failed = 0, taken = new Set(), t0 = Date.now();
      for (var i = 0; i < unit.works.length; i++) {
        var w = unit.works[i], row = rows[w];
        if (state.stop) { setState(row, "stopped"); continue; }
        if (!info[w] || !info[w].abstract) { setState(row, "no abstract"); continue; }
        setState(row, "describing", "busy");
        status("unit-status", unit.unit + ": paper " + (i + 1) + " of " + unit.works.length +
               (out.length ? ", about " + Math.round((Date.now() - t0) / out.length / 1000) + " s each" : ""));
        var attempts = [];
        try {
          var desc = await core.describe(function (s, u) {
            return ask(m, s, u, function (msg) { status("unit-status", unit.unit + ": " + msg); });
          }, unit.instructions, info[w], (unit.avoid || {})[w] || [], unit.max_avoided || 2, taken,
          function (a) { attempts.push(a); });
          taken.add(core.fingerprint(desc));
          out.push(Object.assign({work: w}, desc));
          setState(row, attempts.length > 1 ? "ok, 2nd try" : "ok", "ok");
          row.appendChild(el("div", {class: "desc"}, [el("p", {}, [el("b", {text: "Problem"}), desc.problem]),
                                                    el("p", {}, [el("b", {text: "Approach"}), desc.approach])]));
          var used = core.avoided(desc.problem + " " + desc.approach, (unit.avoid || {})[w] || []);
          row.appendChild(el("div", {class: "badges"}, [
            el("span", {class: "badge", text: (desc.problem + " " + desc.approach).split(/\s+/).length + " words"}),
            used.length ? el("span", {class: "badge warn", text: "uses " + used.join(", ")}) : null]));
        } catch (e) {
          if (e.name !== "Unusable") { throw e; }
          failed++;
          setState(row, "unusable", "bad");
          row.appendChild(el("div", {class: "desc"}, [el("p", {class: "note", text: "Left out: " + e.message + "."})]));
        }
        if (attempts.length) {
          row.appendChild(el("details", {class: "raw"}, [el("summary", {text: "The model's answer" + (attempts.length > 1 ? "s" : "")})]
            .concat(attempts.map(function (a) {
              return el("pre", {text: (a.ok ? "" : "Not usable (" + a.reason + "):\n") + a.answer});
            }))));
        }
        $("progress").style.width = Math.round(100 * (i + 1) / unit.works.length) + "%";
      }
      var result = core.result(unit, {provider: m.provider, id: m.id}, out, failed);
      resemble(unit, out, papers, info);
      if (out.length * 4 < unit.works.length * 3) {
        status("unit-status", unit.unit + ": " + out.length + " of " + unit.works.length + " papers described, fewer " +
               "than the three quarters a result needs, so there is nothing to send." +
               (state.stop ? " Start again to do a whole unit." : ""), "bad");
        return;
      }
      status("unit-status", unit.unit + ": " + out.length + " of " + unit.works.length + " papers described.", "ok");
      sendPanel(unit, m, result);
    } catch (e) {
      status("unit-status", (e.name === "Unusable" ? "This model is not up to the job: " : "Stopped: ") + e.message, "bad");
    } finally {
      state.running = false; state.finished = true; $("stop").hidden = true; refresh();
    }
  }

  // ---- step 3: send ------------------------------------------------------

  function sendPanel(unit, m, result) {
    var json = JSON.stringify(result, null, 1);
    var title = "distill result " + unit.unit;
    var base = "https://github.com/" + REPO + "/issues/new?template=work-result.yml&title=" + encodeURIComponent(title);
    var full = base + "&result=" + encodeURIComponent(json);
    var url = full.length < 6000 ? full : base;
    var box = $("send");
    box.textContent = "";
    var copied = el("span", {class: "status"});
    var copy = el("button", {type: "button", class: "primary", text: "1. Copy the result"});
    copy.addEventListener("click", function () {
      navigator.clipboard.writeText(json).then(function () { copied.textContent = "Copied."; copied.className = "status ok"; },
        function () { copied.textContent = "Copying is blocked here: use Download, then paste the file's text."; copied.className = "status bad"; });
    });
    var open = el("a", {class: "button primary", href: url, target: "_blank", rel: "noopener", text: "2. Open the GitHub form"});
    open.addEventListener("click", function () {
      var d = done(); d.push(unit.unit + " " + modelName(m)); save("done", JSON.stringify(d));
    });
    var dl = el("a", {class: "button", download: "undiscovered-" + unit.unit + ".json",
                      href: URL.createObjectURL(new Blob([json], {type: "application/json"})), text: "Download it"});
    box.appendChild(el("p", {}, [result.descriptions.length + " descriptions for " + unit.unit + ", made with " + m.id + "."]));
    box.appendChild(el("div", {class: "buttons"}, [copy, open, dl, copied]));
    box.appendChild(el("p", {class: "note", text: (url === full
      ? "The form opens with the result filled in. "
      : "Paste the result into the form's Result box (it is too long to fill in for you). ") +
      "Tick the CC0 box and press Submit. The checking job answers on the issue within a few minutes."}));
  }

  // ---- what the descriptions resemble ------------------------------------

  async function resemble(unit, out, papers, info) {
    var box = $("resemble");
    box.textContent = "";
    if (!out.length) { return; }
    box.appendChild(el("p", {class: "note", text: "Looking among the published descriptions..."}));
    var docs = [];
    try {
      var r = await fetch(RAW + "combined/descriptions.jsonl", {cache: "no-store"});
      if (r.ok) {
        (await r.text()).split("\n").forEach(function (line) {
          if (!line.trim()) { return; }
          var p = JSON.parse(line);
          if (unit.works.indexOf(p.work) >= 0) { return; }
          docs.push({id: p.work, field: p.field || p.domain || "", title: p.title || p.topic_name || p.work,
                     text: p.descriptions.map(function (d) { return d.problem + " " + d.approach; }).join(" ")});
        });
      }
    } catch (e) { /* the published index is optional here: this unit alone still says something */ }
    out.forEach(function (d) {
      var p = papers[d.work] || {};
      docs.push({id: d.work, field: p.field || p.domain || "", title: (info[d.work] || {}).title || d.work, mine: true,
                 text: d.problem + " " + d.approach});
    });
    var index = new text.Index(docs), found = [];
    out.forEach(function (d) {
      var p = papers[d.work] || {}, field = p.field || p.domain || "";
      index.search(d.problem + " " + d.approach, 3, function (doc) { return doc.id !== d.work && doc.field !== field; })
        .forEach(function (hit) { found.push({mine: d, title: (info[d.work] || {}).title, field: field, hit: hit}); });
    });
    found.sort(function (a, b) { return b.hit.score - a.hit.score; });
    var seen = new Set(), shown = 0;
    box.textContent = "";
    box.appendChild(el("p", {class: "note", text: "The closest papers from other fields to what your model wrote, in " +
      "this unit and among " + (docs.length - out.length) + " papers already described. Leads to look at, not " +
      "findings: a pair counts once two models describe both papers alike."}));
    found.forEach(function (f) {
      var key = [f.mine.work, f.hit.doc.id].sort().join(" ");
      if (seen.has(key) || shown >= 6) { return; }
      seen.add(key); shown++;
      box.appendChild(el("div", {class: "match"}, [
        el("div", {}, [el("a", {href: "https://openalex.org/" + f.mine.work, target: "_blank", rel: "noopener", text: f.title || f.mine.work}),
                       el("span", {class: "note", text: " (" + f.field + ")"})]),
        el("div", {}, ["and ", el("a", {href: "https://openalex.org/" + f.hit.doc.id, target: "_blank", rel: "noopener", text: f.hit.doc.title}),
                       el("span", {class: "note", text: " (" + f.hit.doc.field + (f.hit.doc.mine ? ", also in your unit" : "") + ")"})]),
        el("div", {class: "why", text: "similarity " + f.hit.score.toFixed(2) + "; shared words: " +
                                       f.hit.shared.map(function (s) { return s[0]; }).join(", ")})]));
    });
    if (!shown) { box.appendChild(el("p", {class: "note", text: "Nothing close yet; that changes as more papers are described."})); }
  }

  // ---- wiring --------------------------------------------------------------

  document.querySelectorAll("input[name=kind]").forEach(function (r) { r.addEventListener("change", refresh); });
  ["provider"].forEach(function (id) { $(id).addEventListener("change", function () { showProvider(); refresh(); }); });
  ["key", "hosted-model", "local-base", "local-model", "webllm-model"].forEach(function (id) { $(id).addEventListener("input", refresh); });
  $("list-hosted").addEventListener("click", function () { listModels(model(), "hosted-models", "test-status"); });
  $("list-local").addEventListener("click", function () { listModels(model(), "local-models", "test-status"); });
  $("test").addEventListener("click", test);
  $("start").addEventListener("click", run);
  $("stop").addEventListener("click", function () { state.stop = true; status("unit-status", "Stopping after this paper..."); });

  var lastKind = load("kind");
  if (lastKind && !(lastKind === "browser" && !hasGPU)) {
    var r = document.querySelector("input[name=kind][value=" + lastKind + "]");
    if (r) { r.checked = true; }
  }
  if (load("webllm")) { $("webllm-model").value = load("webllm"); }
  if (load("local.base")) { $("local-base").value = load("local.base"); }
  if (load("local.model")) { $("local-model").value = load("local.model"); }
  showProvider();
  refresh();
})();
