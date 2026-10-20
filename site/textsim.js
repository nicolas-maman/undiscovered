// Text similarity in the browser: TF-IDF on content words, as the pipeline's
// combine step uses it (English stop words left out, sublinear term frequency,
// unit-length vectors). Used to show a volunteer what their descriptions
// resemble, and by the explorer's search. Needs core.js for the word rules.
(function (root) {
  "use strict";
  var core = root.UndiscoveredCore;

  function terms(text) {
    var counts = new Map();
    (text.toLowerCase().match(/[\p{L}\p{Nl}\p{No}]+/gu) || []).forEach(function (w) {
      if (w.length > 1 && !core.STOP.has(w)) { counts.set(w, (counts.get(w) || 0) + 1); }
    });
    return counts;
  }

  // An index of documents ({id, text, ...}) that can rank them by likeness to any text.
  function Index(docs) {
    var df = new Map(), bags = docs.map(function (d) { return terms(d.text); });
    bags.forEach(function (bag) { bag.forEach(function (_n, w) { df.set(w, (df.get(w) || 0) + 1); }); });
    var n = docs.length;
    this.docs = docs;
    this.idf = function (w) { return Math.log((1 + n) / (1 + (df.get(w) || 0))) + 1; };
    this.vectors = bags.map(this.vector.bind(this, null));
  }

  Index.prototype.vector = function (text, bag) {
    var self = this, v = new Map(), norm = 0;
    (bag || terms(text)).forEach(function (count, w) {
      var x = (1 + Math.log(count)) * self.idf(w);
      v.set(w, x);
      norm += x * x;
    });
    norm = Math.sqrt(norm) || 1;
    v.forEach(function (x, w) { v.set(w, x / norm); });
    return v;
  };

  function dot(a, b) {
    var small = a.size < b.size ? a : b, big = small === a ? b : a, s = 0;
    small.forEach(function (x, w) { var y = big.get(w); if (y) { s += x * y; } });
    return s;
  }

  // The documents most like `text`, best first, as {doc, score, shared: [[word, weight]...]}.
  Index.prototype.search = function (text, k, keep) {
    var q = this.vector(text), out = [];
    for (var i = 0; i < this.docs.length; i++) {
      if (keep && !keep(this.docs[i])) { continue; }
      var s = dot(q, this.vectors[i]);
      if (s > 0) { out.push({doc: this.docs[i], score: s, v: this.vectors[i]}); }
    }
    out.sort(function (a, b) { return b.score - a.score; });
    return out.slice(0, k).map(function (r) {
      var shared = [];
      q.forEach(function (x, w) { var y = r.v.get(w); if (y) { shared.push([w, x * y]); } });
      shared.sort(function (a, b) { return b[1] - a[1]; });
      return {doc: r.doc, score: r.score, shared: shared.slice(0, 6)};
    });
  };

  root.UndiscoveredText = {terms: terms, Index: Index};
}(typeof self !== "undefined" ? self : this));
