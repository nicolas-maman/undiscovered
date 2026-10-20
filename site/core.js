// The describing work's rules, in JavaScript, for the browser client.
//
// A copy of clients/python/undiscovered/distill.py and models.py: the same
// prompt, the same parsing and the same checks, so a result made in the
// browser passes the checking job exactly as one made by the Python client.
// pipeline/tests/test_core_js.py runs both on the same cases in CI.
(function (root, factory) {
  "use strict";
  if (typeof module === "object" && module.exports) { module.exports = factory(); }
  else { root.UndiscoveredCore = factory(); }
}(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var PROMPT = 1;
  var MAX_WORDS = 60;
  var SAME_SHAPE = 0.8;
  var MAX_TOKENS = 2048;
  var CLIENT = {name: "undiscovered-web", version: "0.1.0"};

  var SYSTEM = "You help researchers in one field recognise work from another. You describe what a " +
               "piece of research does in plain words that any scientist would understand.";
  var FORMAT = 'Answer with one JSON object and nothing else, in this form:\n' +
               '{"problem": "...", "approach": "..."}\n' +
               "Each value is one or two sentences of plain English, at most " + MAX_WORDS + " words.";

  // Python's [^\W\d_]+: letters, and numbers that are not decimal digits.
  var WORD = /[\p{L}\p{Nl}\p{No}]+/gu;
  var THINKING = /<think>[\s\S]*?<\/think>/gi;
  // scikit-learn's English stop words, as clients/python/undiscovered/stopwords.py copies them.
  var STOP = new Set([
    "a", "about", "above", "across", "after", "afterwards", "again", "against", "all", "almost", "alone",
    "along", "already", "also", "although", "always", "am", "among", "amongst", "amoungst", "amount", "an",
    "and", "another", "any", "anyhow", "anyone", "anything", "anyway", "anywhere", "are", "around", "as",
    "at", "back", "be", "became", "because", "become", "becomes", "becoming", "been", "before", "beforehand",
    "behind", "being", "below", "beside", "besides", "between", "beyond", "bill", "both", "bottom", "but",
    "by", "call", "can", "cannot", "cant", "co", "con", "could", "couldnt", "cry", "de", "describe", "detail",
    "do", "done", "down", "due", "during", "each", "eg", "eight", "either", "eleven", "else", "elsewhere",
    "empty", "enough", "etc", "even", "ever", "every", "everyone", "everything", "everywhere", "except",
    "few", "fifteen", "fifty", "fill", "find", "fire", "first", "five", "for", "former", "formerly", "forty",
    "found", "four", "from", "front", "full", "further", "get", "give", "go", "had", "has", "hasnt", "have",
    "he", "hence", "her", "here", "hereafter", "hereby", "herein", "hereupon", "hers", "herself", "him",
    "himself", "his", "how", "however", "hundred", "i", "ie", "if", "in", "inc", "indeed", "interest", "into",
    "is", "it", "its", "itself", "keep", "last", "latter", "latterly", "least", "less", "ltd", "made", "many",
    "may", "me", "meanwhile", "might", "mill", "mine", "more", "moreover", "most", "mostly", "move", "much",
    "must", "my", "myself", "name", "namely", "neither", "never", "nevertheless", "next", "nine", "no",
    "nobody", "none", "noone", "nor", "not", "nothing", "now", "nowhere", "of", "off", "often", "on", "once",
    "one", "only", "onto", "or", "other", "others", "otherwise", "our", "ours", "ourselves", "out", "over",
    "own", "part", "per", "perhaps", "please", "put", "rather", "re", "same", "see", "seem", "seemed",
    "seeming", "seems", "serious", "several", "she", "should", "show", "side", "since", "sincere", "six",
    "sixty", "so", "some", "somehow", "someone", "something", "sometime", "sometimes", "somewhere", "still",
    "such", "system", "take", "ten", "than", "that", "the", "their", "them", "themselves", "then", "thence",
    "there", "thereafter", "thereby", "therefore", "therein", "thereupon", "these", "they", "thick", "thin",
    "third", "this", "those", "though", "three", "through", "throughout", "thru", "thus", "to", "together",
    "too", "top", "toward", "towards", "twelve", "twenty", "two", "un", "under", "until", "up", "upon", "us",
    "very", "via", "was", "we", "well", "were", "what", "whatever", "when", "whence", "whenever", "where",
    "whereafter", "whereas", "whereby", "wherein", "whereupon", "wherever", "whether", "which", "while",
    "whither", "who", "whoever", "whole", "whom", "whose", "why", "will", "with", "within", "without",
    "would", "yet", "you", "your", "yours", "yourself", "yourselves"
  ]);

  function Unusable(message) {
    var e = new Error(message);
    e.name = "Unusable";
    return e;
  }

  function words(text) { return text.trim() ? text.trim().split(/\s+/) : []; }
  function squash(text) { return words(text).join(" "); }

  function abstractText(inverted) {
    if (!inverted) { return ""; }
    var slots = {};
    Object.keys(inverted).forEach(function (w) { inverted[w].forEach(function (p) { slots[p] = w; }); });
    return Object.keys(slots).map(Number).sort(function (a, b) { return a - b; })
      .map(function (p) { return slots[p]; }).join(" ");
  }

  function prompt(instructions, title, abstract, avoid) {
    var parts = [instructions, "Title: " + title, "Abstract: " + abstract];
    if (avoid && avoid.length) {
      parts.push("Do not use these words, which are specific to this paper: " + avoid.join(", ") + ".");
    }
    parts.push(FORMAT);
    return parts.join("\n\n");
  }

  function stem(word) { return word.length > 3 && word.slice(-1) === "s" ? word.slice(0, -1) : word; }

  function avoided(text, avoid) {
    var seen = {};
    (text.toLowerCase().match(WORD) || []).forEach(function (w) { seen[stem(w)] = true; });
    return (avoid || []).filter(function (a) { return seen[stem(a.toLowerCase())]; });
  }

  function parse(answer) {
    var text = String(answer).replace(THINKING, "");
    var start = text.indexOf("{"), end = text.lastIndexOf("}");
    if (start < 0 || end < start) { throw Unusable("the answer was not a JSON object"); }
    var obj;
    try { obj = JSON.parse(text.slice(start, end + 1)); }
    catch (e) { throw Unusable("the answer was not valid JSON"); }
    var out = {};
    ["problem", "approach"].forEach(function (part) {
      var v = obj && typeof obj === "object" && !Array.isArray(obj) ? obj[part] : undefined;
      if (typeof v !== "string" || words(v).length < 4) { throw Unusable('"' + part + '" was missing or too short'); }
      out[part] = squash(v);
    });
    return out;
  }

  function fingerprint(desc) {
    return ((desc.problem + " " + desc.approach).toLowerCase().match(WORD) || []).join(" ");
  }

  function content(text) {
    var counts = new Map();
    (text.toLowerCase().match(WORD) || []).forEach(function (w) {
      if (!STOP.has(w)) { counts.set(w, (counts.get(w) || 0) + 1); }
    });
    return counts;
  }

  // Cosine between the content-word counts of two texts (as distill.likeness).
  function likeness(a, b) {
    var ca = content(a), cb = content(b), dot = 0, na = 0, nb = 0;
    ca.forEach(function (n, w) { dot += n * (cb.get(w) || 0); na += n * n; });
    if (!dot) { return 0; }
    cb.forEach(function (n) { nb += n * n; });
    return dot / Math.sqrt(na * nb);
  }

  function check(desc, avoid, maxAvoided, taken) {
    var mine = fingerprint(desc);
    var near = taken && Array.from(taken).some(function (other) { return likeness(mine, other) > SAME_SHAPE; });
    if (near) { throw Unusable("it said almost the same as the description of another paper in this unit"); }
    ["problem", "approach"].forEach(function (part) {
      if (words(desc[part]).length > MAX_WORDS) { throw Unusable('"' + part + '" was longer than ' + MAX_WORDS + " words"); }
    });
    var used = avoided(desc.problem + " " + desc.approach, avoid);
    if (used.length > maxAvoided) { throw Unusable("it used words specific to the paper: " + used.join(", ")); }
  }

  // The HTTP request for one question, by kind of endpoint (as models.py builds it).
  function request(model, system, user) {
    var base = model.base.replace(/\/+$/, "");
    if (model.provider === "anthropic") {
      return {url: base + "/messages",
              headers: {"x-api-key": model.key, "anthropic-version": "2023-06-01",
                        "anthropic-dangerous-direct-browser-access": "true"},
              body: {model: model.id, max_tokens: MAX_TOKENS, temperature: 0, system: system,
                     messages: [{role: "user", content: user}]}};
    }
    if (model.provider === "google") {
      return {url: base + "/models/" + encodeURIComponent(model.id) + ":generateContent",
              headers: {"x-goog-api-key": model.key},
              body: {systemInstruction: {parts: [{text: system}]},
                     contents: [{role: "user", parts: [{text: user}]}],
                     generationConfig: {temperature: 0, maxOutputTokens: MAX_TOKENS}}};
    }
    return {url: base + "/chat/completions",
            headers: model.key ? {"Authorization": "Bearer " + model.key} : {},
            body: {model: model.id, temperature: 0, max_tokens: MAX_TOKENS,
                   messages: [{role: "system", content: system}, {role: "user", content: user}]}};
  }

  function answerText(provider, data) {
    try {
      if (provider === "anthropic") {
        return data.content.filter(function (b) { return b.type === "text"; }).map(function (b) { return b.text; }).join("");
      }
      if (provider === "google") { return data.candidates[0].content.parts.map(function (p) { return p.text || ""; }).join(""); }
      return data.choices[0].message.content || "";
    } catch (e) {
      throw new Error(provider + " answered in an unexpected shape");
    }
  }

  // One work's description, checked; `ask(system, user)` returns the model's answer.
  // Two attempts, the second told why the first could not be used, as the Python client does.
  async function describe(ask, instructions, work, avoid, maxAvoided, taken, onAttempt) {
    var question = prompt(instructions, work.title, work.abstract, avoid);
    var reason = "";
    for (var attempt = 1; attempt <= 2; attempt++) {
      var user = reason ? question + "\n\nYour previous answer could not be used: " + reason + ". Try again." : question;
      var answer = await ask(SYSTEM, user);
      try {
        var desc = parse(answer);
        check(desc, avoid, maxAvoided, taken);
        if (onAttempt) { onAttempt({attempt: attempt, answer: answer, ok: true}); }
        return desc;
      } catch (e) {
        if (e.name !== "Unusable") { throw e; }
        reason = e.message;
        if (onAttempt) { onAttempt({attempt: attempt, answer: answer, ok: false, reason: reason}); }
      }
    }
    throw Unusable(reason);
  }

  // A unit's result as the checking job expects it, or Unusable when the model
  // failed on more than a quarter of the papers.
  function result(unit, model, descriptions, failed) {
    if (failed * 4 > unit.works.length) {
      throw Unusable("the model's answers failed the checks for " + failed + " of " + unit.works.length +
                     " papers; a larger model may do better");
    }
    return {unit: unit.unit, protocol: unit.protocol, client: CLIENT,
            model: {provider: model.provider, id: model.id}, prompt: PROMPT, descriptions: descriptions};
  }

  return {PROMPT: PROMPT, MAX_WORDS: MAX_WORDS, SAME_SHAPE: SAME_SHAPE, STOP: STOP, likeness: likeness, MAX_TOKENS: MAX_TOKENS, CLIENT: CLIENT, SYSTEM: SYSTEM, FORMAT: FORMAT,
          abstractText: abstractText, prompt: prompt, avoided: avoided, parse: parse, fingerprint: fingerprint,
          check: check, request: request, answerText: answerText, describe: describe, result: result};
}));
