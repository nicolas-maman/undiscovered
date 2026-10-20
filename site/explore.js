// The explorer: a map of the set, the pairs and why, search, and the checking job's record.
(function () {
  "use strict";
  var REPO = "nicolas-maman/undiscovered";
  var RAW = window.UNDISCOVERED_DATA || ("https://raw.githubusercontent.com/" + REPO + "/distill-2025/");
  var text = window.UndiscoveredText;
  var $ = function (id) { return document.getElementById(id); };
  var data = {};

  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") { e.textContent = attrs[k]; } else if (k === "class") { e.className = attrs[k]; } else { e.setAttribute(k, attrs[k]); }
    });
    (kids || []).forEach(function (c) { if (c !== null && c !== undefined) { e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); } });
    return e;
  }
  function n(x) { return (x || 0).toLocaleString("en"); }
  function oa(w, label) { return el("a", {href: "https://openalex.org/" + w, target: "_blank", rel: "noopener", text: label || w}); }
  // Where a result came from: its GitHub issue, or a maintainer's import, whose record is on the data branch.
  function issue(i) {
    if (typeof i === "number") { return el("a", {href: "https://github.com/" + REPO + "/issues/" + i, target: "_blank", rel: "noopener", text: "#" + i}); }
    var batch = String(i).replace(/^import-/, "").replace(/-\d+$/, "");
    return el("a", {href: "https://github.com/" + REPO + "/blob/distill-2025/imports/" + batch + ".json", target: "_blank",
                    rel: "noopener", title: String(i), text: "imported"});
  }

  // Each file is optional: a missing one (404) means that part has nothing yet.
  function get(path, as) {
    return fetch(RAW + path, {cache: "no-store"}).then(function (r) {
      if (r.status === 404) { return null; }
      if (!r.ok) { throw new Error(path + ": HTTP " + r.status); }
      return as === "text" ? r.text() : r.json();
    });
  }

  // ---- tabs --------------------------------------------------------------

  var shown = {};
  function show(tab) {
    document.querySelectorAll("#tabs a").forEach(function (a) { a.setAttribute("aria-selected", a.dataset.tab === tab ? "true" : "false"); });
    document.querySelectorAll("section[role=tabpanel]").forEach(function (s) { s.hidden = s.id !== "tab-" + tab; });
    if (tab === "map") { map.resize(); }
    if (!shown[tab] && render[tab]) { shown[tab] = true; render[tab](); }
  }
  function route() {
    var h = location.hash.replace(/^#/, "").split("&"), tab = h[0] || "map";
    if (!$("tab-" + tab)) { tab = "map"; }
    show(tab);
    var w = h.slice(1).map(function (x) { return x.split("="); }).filter(function (x) { return x[0] === "w"; })[0];
    if (w && tab === "map") { map.focus(w[1]); }
  }

  // ---- the map -----------------------------------------------------------

  var map = (function () {
    var canvas = $("map"), ctx = canvas.getContext("2d"), tip = $("tip");
    var pts = [], layout = "abstracts", view = {x: 0, y: 0, k: 1}, size = {w: 0, h: 0, dpr: 1};
    var hidden = new Set(), onlyField = "", selected = -1, hover = -1, anim = null, colors = [], families = {};
    var pairLines = [];

    function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }

    function resize() {
      var r = canvas.getBoundingClientRect();
      if (!r.width) { return; }
      size = {w: r.width, h: r.height, dpr: window.devicePixelRatio || 1};
      canvas.width = r.width * size.dpr; canvas.height = r.height * size.dpr;
      if (!view.fitted && pts.length) { fit(); }
      draw();
    }
    function fit() {
      var s = Math.min(size.w, size.h) / 1080;
      view = {k: s, x: (size.w - 1000 * s) / 2, y: (size.h - 1000 * s) / 2, fitted: true};
    }
    function sx(p) { return p.x * view.k + view.x; }
    function sy(p) { return p.y * view.k + view.y; }
    function visible(p) {
      return !hidden.has(p.domain) && (!onlyField || p.fieldName === onlyField) && (layout === "abstracts" || p.described);
    }

    function draw() {
      if (!size.w) { return; }
      ctx.setTransform(size.dpr, 0, 0, size.dpr, 0, 0);
      ctx.clearRect(0, 0, size.w, size.h);
      var r = Math.max(1.6, Math.min(4, 1.6 * Math.sqrt(view.k * 1.1)));
      ctx.globalAlpha = 1;
      if ($("show-pairs").checked) {
        ctx.lineWidth = 1.4;
        pairLines.forEach(function (l) {
          var a = pts[l[0]], b = pts[l[1]];
          if (!a || !b || !visible(a) || !visible(b)) { return; }
          ctx.strokeStyle = css("--accent"); ctx.globalAlpha = .7;
          ctx.beginPath(); ctx.moveTo(sx(a), sy(a)); ctx.lineTo(sx(b), sy(b)); ctx.stroke();
        });
        ctx.globalAlpha = 1;
      }
      if ($("show-twins").checked) {
        ctx.strokeStyle = css("--twin"); ctx.lineWidth = 1; ctx.globalAlpha = .55;
        Object.keys(families).forEach(function (f) {
          var m = families[f].filter(function (i) { return visible(pts[i]); });
          for (var i = 1; i < m.length; i++) {
            ctx.beginPath(); ctx.moveTo(sx(pts[m[0]]), sy(pts[m[0]])); ctx.lineTo(sx(pts[m[i]]), sy(pts[m[i]])); ctx.stroke();
          }
        });
        ctx.globalAlpha = 1;
      }
      for (var i = 0; i < pts.length; i++) {
        var p = pts[i];
        if (!visible(p)) { continue; }
        ctx.fillStyle = colors[p.domain];
        ctx.globalAlpha = .8;
        ctx.beginPath(); ctx.arc(sx(p), sy(p), r, 0, 6.2832); ctx.fill();
      }
      ctx.globalAlpha = 1;
      if ($("show-twins").checked) {
        ctx.strokeStyle = css("--twin"); ctx.lineWidth = 1.6;
        pts.forEach(function (p) {
          if (p.family && visible(p)) { ctx.beginPath(); ctx.arc(sx(p), sy(p), r + 3, 0, 6.2832); ctx.stroke(); }
        });
      }
      [hover, selected].forEach(function (i, k) {
        if (i < 0) { return; }
        var p = pts[i];
        ctx.strokeStyle = css("--fg"); ctx.lineWidth = k ? 2.4 : 1.4;
        ctx.beginPath(); ctx.arc(sx(p), sy(p), r + (k ? 6 : 4), 0, 6.2832); ctx.stroke();
      });
    }

    function nearest(mx, my) {
      var best = -1, bd = 64;
      for (var i = 0; i < pts.length; i++) {
        var p = pts[i];
        if (!visible(p)) { continue; }
        var dx = sx(p) - mx, dy = sy(p) - my, d = dx * dx + dy * dy;
        if (d < bd) { bd = d; best = i; }
      }
      return best;
    }

    function setLayout(name) {
      if (name === layout) { return; }
      var from = pts.map(function (p) { return [p.x, p.y]; });
      layout = name;
      var to = pts.map(function (p) { var q = name === "descriptions" && p.plain ? p.plain : p.abs; return [q[0], q[1]]; });
      var t0 = performance.now();
      if (anim) { cancelAnimationFrame(anim); }
      (function step(now) {
        var t = Math.min(1, (now - t0) / 700), e = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
        pts.forEach(function (p, i) { p.x = from[i][0] + (to[i][0] - from[i][0]) * e; p.y = from[i][1] + (to[i][1] - from[i][1]) * e; });
        draw();
        if (t < 1) { anim = requestAnimationFrame(step); }
      }(t0));
      $("by-abstracts").setAttribute("aria-pressed", name === "abstracts");
      $("by-descriptions").setAttribute("aria-pressed", name === "descriptions");
    }

    function init(m, twins) {
      colors = m.domains.map(function (_d, i) { return css("--d" + (i % 4)); });
      pts = m.papers.map(function (row, i) {
        var abs = m.layouts.abstracts[i], plain = m.layouts.descriptions[i];
        return {work: row[0], field: row[1], fieldName: m.fields[row[1]], domain: row[2], title: row[3], year: row[4],
                family: row[5], abs: abs, plain: plain, described: !!plain, x: abs[0], y: abs[1]};
      });
      families = {};
      pts.forEach(function (p, i) { if (p.family) { (families[p.family] = families[p.family] || []).push(i); } });
      var at = {};
      pts.forEach(function (p, i) { at[p.work] = i; });
      pairLines = ((twins && twins.twins) || []).filter(function (t) { return t.trust === "two models agree"; })
        .map(function (t) { return [at[t.a.work], at[t.b.work], t.trust]; })
        .filter(function (l) { return l[0] !== undefined && l[1] !== undefined; });
      $("by-descriptions").disabled = !m.described;
      $("by-descriptions").title = m.described ? "" : "Appears once enough papers have descriptions";
      var legend = $("legend");
      m.domains.forEach(function (d, i) {
        var b = el("button", {type: "button", "aria-pressed": "true"}, [el("i", {style: "background:" + colors[i]}), d || "unknown"]);
        b.addEventListener("click", function () {
          if (hidden.has(i)) { hidden.delete(i); } else { hidden.add(i); }
          b.setAttribute("aria-pressed", hidden.has(i) ? "false" : "true"); draw();
        });
        legend.appendChild(b);
      });
      var counts = {};
      pts.forEach(function (p) { counts[p.fieldName] = (counts[p.fieldName] || 0) + 1; });
      Object.keys(counts).sort().forEach(function (f) {
        if (f) { $("field").appendChild(el("option", {value: f, text: f + " (" + n(counts[f]) + ")"})); }
      });
      view.fitted = false;
      resize();
      return at;
    }

    var drag = null;
    canvas.addEventListener("pointerdown", function (e) {
      drag = {x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false};
      canvas.setPointerCapture(e.pointerId); canvas.classList.add("drag");
    });
    canvas.addEventListener("pointermove", function (e) {
      var r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
      if (drag) {
        var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
        if (Math.abs(dx) + Math.abs(dy) > 3) { drag.moved = true; }
        view.x = drag.vx + dx; view.y = drag.vy + dy; draw(); return;
      }
      var i = nearest(mx, my);
      if (i !== hover) { hover = i; draw(); }
      if (i >= 0) {
        var p = pts[i];
        tip.hidden = false; tip.textContent = "";
        tip.appendChild(el("div", {text: p.title || p.work}));
        tip.appendChild(el("div", {class: "note", text: (p.fieldName || "") + (p.year ? ", " + p.year : "") + (p.family ? ", known twin" : "")}));
        tip.style.left = Math.min(mx + 14, size.w - 310) + "px"; tip.style.top = Math.min(my + 14, size.h - 70) + "px";
      } else { tip.hidden = true; }
    });
    canvas.addEventListener("pointerup", function (e) {
      canvas.classList.remove("drag");
      var moved = drag && drag.moved;
      drag = null;
      if (!moved && hover >= 0) { select(hover); }
    });
    canvas.addEventListener("pointerleave", function () { hover = -1; tip.hidden = true; draw(); });
    canvas.addEventListener("wheel", function (e) {
      e.preventDefault();
      var r = canvas.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
      var f = Math.exp(-e.deltaY * 0.0015), k = Math.max(0.2, Math.min(40, view.k * f));
      view.x = mx - (mx - view.x) * (k / view.k); view.y = my - (my - view.y) * (k / view.k); view.k = k; draw();
    }, {passive: false});
    window.addEventListener("resize", resize);
    $("by-abstracts").addEventListener("click", function () { setLayout("abstracts"); });
    $("by-descriptions").addEventListener("click", function () { setLayout("descriptions"); });
    $("field").addEventListener("change", function () { onlyField = $("field").value; draw(); });
    $("show-twins").addEventListener("change", draw);
    $("show-pairs").addEventListener("change", draw);

    function select(i) {
      selected = i; draw();
      paperPanel(pts[i]);
      history.replaceState(null, "", "#map&w=" + pts[i].work);
    }
    function focus(w) {
      var i = pts.findIndex(function (p) { return p.work === w; });
      if (i < 0) { return; }
      var p = pts[i];
      view.k = Math.max(view.k, 3);
      view.x = size.w / 2 - p.x * view.k; view.y = size.h / 2 - p.y * view.k;
      select(i);
    }
    return {init: init, resize: resize, draw: draw, focus: focus};
  }());

  // ---- one paper ---------------------------------------------------------

  function descriptionsOf(w) { return (data.byWork && data.byWork[w]) || null; }

  function paperPanel(p) {
    var box = $("paper");
    box.textContent = "";
    box.appendChild(el("h3", {}, [oa(p.work, p.title || p.work)]));
    box.appendChild(el("div", {class: "kv", text: [p.fieldName, p.year].filter(Boolean).join(", ")}));
    if (p.family) {
      box.appendChild(el("div", {class: "kv"}, ["Known twin: family " + p.family.replace(/_/g, " ") + " of the ",
        el("a", {href: "https://arxiv.org/abs/2609.07595", target: "_blank", rel: "noopener", text: "benchmark"})]));
    }
    var abs = el("details", {}, [el("summary", {class: "kv", text: "Abstract, from OpenAlex"})]);
    abs.addEventListener("toggle", function () {
      if (!abs.open || abs.dataset.loaded) { return; }
      abs.dataset.loaded = "1";
      fetch("https://api.openalex.org/works/" + p.work + "?select=abstract_inverted_index").then(function (r) { return r.json(); })
        .then(function (w) { abs.appendChild(el("p", {class: "note", text: window.UndiscoveredCore.abstractText(w.abstract_inverted_index) || "No abstract."})); })
        .catch(function () { abs.appendChild(el("p", {class: "note", text: "OpenAlex could not be reached just now."})); });
    });
    box.appendChild(abs);
    var d = descriptionsOf(p.work);
    if (d && d.descriptions.length) {
      box.appendChild(el("h3", {text: "Described as"}));
      d.descriptions.forEach(function (x) {
        box.appendChild(el("div", {class: "d"}, [el("div", {}, [el("b", {text: "problem"}), x.problem]),
          el("div", {}, [el("b", {text: "approach"}), x.approach]), el("div", {class: "m", text: x.model.id + ", by " + x.author})]));
      });
    } else {
      box.appendChild(el("p", {class: "note", text: "Not described yet."}));
    }
    var near = data.neighbours && data.neighbours[p.work];
    if (near && near.length) {
      box.appendChild(el("h3", {text: "Most like it, in other fields"}));
      near.forEach(function (x) {
        var q = data.paper[x[0]];
        var b = el("button", {type: "button", class: "nb"}, [(q && q.title) || x[0], " ",
          el("span", {text: (q ? q.fieldName + ", " : "") + "similarity " + x[1].toFixed(2)})]);
        b.addEventListener("click", function () { map.focus(x[0]); });
        box.appendChild(b);
      });
    }
  }

  // ---- pairs ---------------------------------------------------------------

  function side(s) {
    return el("div", {}, [
      el("div", {class: "kv", text: [s.field || s.domain, s.year].filter(Boolean).join(", ")}),
      el("div", {}, [oa(s.work, s.title || s.topic_name || s.work)]),
      el("div", {}, s.descriptions.map(function (d) {
        return el("div", {class: "d"}, [el("div", {}, [el("b", {text: "problem"}), d.problem]),
          el("div", {}, [el("b", {text: "approach"}), d.approach]), el("div", {class: "m", text: d.model})]);
      }))]);
  }

  function pairCard(t, i) {
    var cites = {neither: ["cite neither", "good"], "a cites b": ["already cited", "bad"], "b cites a": ["already cited", "bad"],
                 both: ["already cited", "bad"]}[t.cites] || null;
    return el("div", {class: "pair"}, [
      el("div", {class: "head"}, [el("span", {text: "#" + (i + 1)}),
        el("span", {title: "similarity times field distance", text: "score " + (t.score === undefined ? t.similarity : t.score).toFixed(2) +
          (t.field_distance === undefined ? "" : " (alike " + t.similarity.toFixed(2) + ", fields apart " + t.field_distance.toFixed(2) + ")")}),
        el("span", {class: "chip " + (t.trust === "two models agree" ? "good" : t.trust === "known case" ? "" : "warn"), text: t.trust}),
        cites ? el("span", {class: "chip " + cites[1], text: cites[0]}) : null,
        el("a", {href: "#map&w=" + t.a.work, text: "on the map"})]),
      el("div", {class: "sides"}, [side(t.a), side(t.b)]),
      t.why && t.why.length ? el("div", {class: "why"}, ["Alike in: "].concat(t.why.map(function (w, k) {
        return el("span", {}, [k ? ", " : "", el("mark", {text: w[0]})]); }))) : null]);
  }

  var render = {};
  render.pairs = function () {
    var box = $("pairs"), t = data.twins;
    box.textContent = "";
    var all = (t && t.twins) || [], known = (t && t.known_cases) || [];
    box.appendChild(el("p", {class: "note", text: "Pairs of papers from different fields whose plain descriptions are most " +
      "alike. \"Two models agree\" pairs join papers two different models describe alike; \"one model so far\" pairs are " +
      "leads from one model, to be checked by a second. Each is a lead for a reader to judge, not a finding."}));
    if (!all.length && !known.length) {
      box.appendChild(el("p", {}, ["No pairs yet: they appear as soon as papers have descriptions. ",
        el("a", {href: "describe.html", text: "Describe a unit"}), " to make the first ones."]));
      return;
    }
    function group(title, list, note) {
      if (!list.length) { return; }
      box.appendChild(el("h3", {text: title + " (" + list.length + ")"}));
      if (note) { box.appendChild(el("p", {class: "note", text: note})); }
      var holder = el("div"), more = el("button", {type: "button", class: "button"}), shownN = 0;
      function page() {
        list.slice(shownN, shownN + 10).forEach(function (x, i) { holder.appendChild(pairCard(x, shownN + i)); });
        shownN = Math.min(list.length, shownN + 10);
        more.hidden = shownN >= list.length;
        more.textContent = "Show " + Math.min(10, list.length - shownN) + " more of " + (list.length - shownN);
      }
      more.addEventListener("click", page);
      box.appendChild(holder); box.appendChild(more);
      page();
    }
    group("Two models agree", all.filter(function (x) { return x.trust === "two models agree"; }),
          "Ranked by how alike the two papers' descriptions are, times how far apart their fields are.");
    group("One model so far", all.filter(function (x) { return x.trust === "one model so far"; }),
          "Leads from papers only one model has described so far, or whose models do not yet agree.");
    group("Known cases recovered", known, "Pairs of benchmark papers known to do the same computation in different " +
          "fields. Finding them is a check that the descriptions work, not a discovery.");
  };

  // ---- search --------------------------------------------------------------

  var searchIn = "descriptions", indexes = {};
  function searchIndex() {
    if (indexes[searchIn]) { return indexes[searchIn]; }
    var docs = [];
    if (searchIn === "descriptions") {
      Object.keys(data.byWork || {}).forEach(function (w) {
        var d = data.byWork[w];
        docs.push({id: w, text: d.descriptions.map(function (x) { return x.problem + " " + x.approach; }).join(" "), d: d});
      });
    } else {
      Object.keys(data.paper || {}).forEach(function (w) { docs.push({id: w, text: data.paper[w].title || ""}); });
    }
    indexes[searchIn] = new text.Index(docs);
    return indexes[searchIn];
  }
  function search() {
    var q = $("q").value.trim(), box = $("results");
    if (!q) { return; }
    box.textContent = "";
    if (searchIn === "descriptions" && !Object.keys(data.byWork || {}).length) {
      box.appendChild(el("p", {class: "note", text: "No paper has a plain description yet, so search the titles for now."}));
      return;
    }
    var hits = searchIndex().search(q, 30);
    if (!hits.length) { box.appendChild(el("p", {class: "note", text: "Nothing matches those words."})); return; }
    hits.forEach(function (h) {
      var p = data.paper[h.doc.id] || {}, d = h.doc.d;
      box.appendChild(el("div", {class: "result"}, [
        el("div", {class: "kv", text: [p.fieldName, p.year, "match " + h.score.toFixed(2)].filter(Boolean).join(", ")}),
        el("div", {}, [oa(h.doc.id, p.title || h.doc.id), " ", el("a", {href: "#map&w=" + h.doc.id, class: "note", text: "on the map"})]),
        d ? el("div", {class: "d"}, [el("div", {}, [el("b", {text: "problem"}), d.descriptions[0].problem]),
                                     el("div", {}, [el("b", {text: "approach"}), d.descriptions[0].approach])]) : null,
        el("div", {class: "why", text: "shared words: " + h.shared.map(function (s) { return s[0]; }).join(", ")})]));
    });
  }
  var timer;
  $("q").addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(search, 250); });
  ["descriptions", "titles"].forEach(function (k) {
    $("in-" + k).addEventListener("click", function () {
      searchIn = k;
      $("in-descriptions").setAttribute("aria-pressed", k === "descriptions");
      $("in-titles").setAttribute("aria-pressed", k === "titles");
      search();
    });
  });

  // ---- units, models, log ------------------------------------------------------

  function stat(label, value) { return el("div", {class: "stat"}, [el("b", {text: value}), label]); }

  render.units = function () {
    var box = $("units"), units = (data.index && data.index.units) || [];
    box.textContent = "";
    var by = {open: 0, check: 0, done: 0};
    units.forEach(function (u) { by[u.status] = (by[u.status] || 0) + 1; });
    box.appendChild(el("div", {class: "stats"}, [stat("units", n(units.length)), stat("waiting for a model", n(by.open)),
      stat("waiting for a second model", n(by.check)), stat("complete", n(by.done))]));
    var filter = el("select", {}, ["all", "open", "check", "done"].map(function (s) { return el("option", {value: s, text: s}); }));
    var tbody = el("tbody");
    function fill() {
      tbody.textContent = "";
      units.filter(function (u) { return filter.value === "all" || u.status === filter.value; }).slice(0, 500).forEach(function (u) {
        var fields = {};
        u.works.forEach(function (w) { var p = data.paper[w]; if (p) { fields[p.fieldName] = 1; } });
        tbody.appendChild(el("tr", {}, [el("td", {class: "id", text: u.unit}), el("td", {text: u.status}),
          el("td", {class: "num", text: String(u.works.length)}),
          el("td", {text: Object.keys(fields).length + " fields"}),
          el("td", {text: (u.models || []).join(", ") || ""}),
          el("td", {}, (u.results || []).map(function (r, k) {
            return el("span", {}, [k ? "; " : "", issue(r.issue), " " + r.author +
              (r.relevance === null || r.relevance === undefined ? "" : ", " + Math.round(r.relevance * 100) + "% on target")]); }))]));
      });
    }
    filter.addEventListener("change", fill);
    box.appendChild(el("div", {class: "controls"}, [el("label", {}, ["Status ", filter])]));
    box.appendChild(el("div", {class: "scroll"}, [el("table", {}, [el("thead", {}, [el("tr", {}, ["Unit", "Status", "Papers", "Spread", "Models", "Results"]
      .map(function (h, i) { return el("th", {class: i === 2 ? "num" : "", text: h}); }))]), tbody])]));
    box.appendChild(el("p", {class: "note", text: "\"On target\": the share of a result's descriptions that find their own " +
      "paper's abstract among the most like them in the unit. The checking job needs at least half."}));
    fill();
  };

  function hist(counts, cls) {
    var max = Math.max.apply(null, counts.concat([1]));
    return el("span", {class: "hist " + (cls || ""), title: "0 to 1, in twentieths"},
      counts.map(function (c) { return el("span", {style: "height:" + Math.max(1, Math.round(28 * c / max)) + "px"}); }));
  }

  render.models = function () {
    var box = $("models"), m = data.models, p = data.progress;
    box.textContent = "";
    box.appendChild(el("div", {class: "stats"}, [stat("descriptions", n(p && p.descriptions)), stat("papers described",
      n(p && p.papers_described) + " of " + n(p && p.papers)), stat("volunteers", n(p && (p.contributors || []).length)),
      stat("papers two models agree on", n(m && m.reliable_papers))]));
    if (!m || !m.models || !m.models.length) {
      box.appendChild(el("p", {class: "note", text: (m && m.note) || "No model has described anything yet."}));
    } else {
      box.appendChild(el("p", {class: "note", text: "Agreement: how alike two different models' descriptions of the same " +
        "paper are. Chance: how alike descriptions of two different papers are. A model worth its descriptions agrees with " +
        "others well above chance; the histograms show the spread from 0 to 1."}));
      box.appendChild(el("div", {class: "scroll"}, [el("table", {}, [
        el("thead", {}, [el("tr", {}, ["Model", "Endpoint", "Papers", "Agreement", "", "Chance", ""].map(function (h, i) {
          return el("th", {class: i === 2 || i === 3 || i === 5 ? "num" : "", text: h}); }))]),
        el("tbody", {}, m.models.map(function (x) {
          return el("tr", {}, [el("td", {text: x.id}), el("td", {text: x.provider}), el("td", {class: "num", text: n(x.papers)}),
            el("td", {class: "num", text: x.agreement === null ? "not yet" : x.agreement.toFixed(2)}),
            el("td", {}, [x.agreement_histogram ? hist(x.agreement_histogram) : null]),
            el("td", {class: "num", text: x.chance === null ? "" : x.chance.toFixed(2)}),
            el("td", {}, [x.chance_histogram ? hist(x.chance_histogram, "chance") : null])]);
        }))])]));
    }
    if (p && p.contributors && p.contributors.length) {
      box.appendChild(el("h3", {text: "Volunteers"}));
      box.appendChild(el("div", {class: "scroll"}, [el("table", {}, [
        el("thead", {}, [el("tr", {}, [el("th", {text: "Volunteer"}), el("th", {class: "num", text: "Units"}),
                                       el("th", {class: "num", text: "Descriptions"})])]),
        el("tbody", {}, p.contributors.map(function (c) {
          return el("tr", {}, [el("td", {}, [el("a", {href: "https://github.com/" + encodeURIComponent(c.login), text: c.login})]),
            el("td", {class: "num", text: n(c.units)}), el("td", {class: "num", text: n(c.descriptions)})]);
        }))])]));
    }
  };

  render.log = function () {
    var box = $("log"), r = data.rejected;
    box.textContent = "";
    box.appendChild(el("p", {class: "note", text: "Every result the checking job turned away, latest first, with its reason. " +
      "Accepted results are on the Units tab."}));
    if (!r || !r.latest || !r.latest.length) { box.appendChild(el("p", {text: "No result has been turned away yet."})); return; }
    box.appendChild(el("div", {class: "scroll"}, [el("table", {}, [
      el("thead", {}, [el("tr", {}, ["Issue", "When", "Who", "Unit", "Model", "Why"].map(function (h) { return el("th", {text: h}); }))]),
      el("tbody", {}, r.latest.map(function (x) {
        return el("tr", {}, [el("td", {}, [issue(x.issue)]), el("td", {text: (x.at || "").replace("T", " ").slice(0, 16)}),
          el("td", {text: x.author}), el("td", {text: x.unit || ""}),
          el("td", {text: x.model ? x.model.id + " (" + x.model.provider + ")" : ""}), el("td", {text: x.reason})]);
      }))])]));
  };

  // ---- loading -------------------------------------------------------------------

  window.addEventListener("hashchange", route);
  Promise.all([get("combined/map.json"), get("combined/twins.json"), get("units/index.json"), get("progress.json"),
               get("combined/models.json"), get("rejected/index.json"), get("combined/neighbours.json"),
               get("combined/descriptions.jsonl", "text")])
    .then(function (all) {
      data = {map: all[0], twins: all[1], index: all[2], progress: all[3], models: all[4], rejected: all[5],
              neighbours: all[6], byWork: {}, paper: {}};
      (all[7] || "").split("\n").forEach(function (line) { if (line.trim()) { var d = JSON.parse(line); data.byWork[d.work] = d; } });
      if (data.map) {
        data.map.papers.forEach(function (row) {
          data.paper[row[0]] = {title: row[3], year: row[4], fieldName: data.map.fields[row[1]], family: row[5]};
        });
        map.init(data.map, data.twins);
        $("map-note").textContent = n(data.map.papers.length) + " papers, placed by how alike their abstracts are" +
          (data.map.described ? "; " + n(data.map.described) + " also by their plain descriptions." : ". Once papers are " +
          "described, they can also be placed by what they do, and the papers that do the same thing in different fields " +
          "move together.") + " Rings mark the benchmark's known twins; lines join papers of one family. Click a paper.";
      } else {
        $("map-note").textContent = "The map is not built yet.";
      }
      var twins = (data.twins && data.twins.twins) || [];
      $("n-pairs").textContent = twins.length ? "(" + twins.length + ")" : "";
      $("n-units").textContent = data.index ? "(" + n(data.index.units.length) + ")" : "";
      $("n-models").textContent = data.models && data.models.models && data.models.models.length ? "(" + data.models.models.length + ")" : "";
      $("n-log").textContent = data.rejected && data.rejected.rejected ? "(" + n(data.rejected.rejected) + ")" : "";
      route();
    })
    .catch(function (e) {
      $("map-note").textContent = "The data could not be loaded just now (" + e.message + ").";
      route();
    });
}());
