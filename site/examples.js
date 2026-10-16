// Known cases of one computation worked out in several fields, from the
// benchmark of Kulikowski (2026), CC BY 4.0. They are papers of the known-twins
// test (research/KNOWN-TWINS.md); titles, years and venues are OpenAlex's.
(function () {
  "use strict";
  var FAMILIES = [
    {
      problem: "Each event makes the next one more likely, nearby and soon.",
      detail: "Aftershocks follow an earthquake; crimes cluster after a crime. One model describes both.",
      names: "self-exciting point process; epidemic-type aftershock sequence model",
      papers: [
        {field: "Seismology", work: "W2625813022", year: 2017, by: "Nandan et al.",
         venue: "Journal of Geophysical Research: Solid Earth",
         title: "Objective estimation of spatially variable parameters of epidemic type aftershock sequence model: Application to California"},
        {field: "Criminology", work: "W2123906784", year: 2011, by: "Mohler et al.",
         venue: "Journal of the American Statistical Association",
         title: "Self-Exciting Point Process Modeling of Crime"}
      ]
    },
    {
      problem: "Estimate what you cannot see from noisy measurements, updating as each one arrives.",
      detail: "The state of a power grid, the course of a flu season, an ice sheet, a spacecraft's orientation.",
      names: "extended, unscented and ensemble Kalman filters",
      papers: [
        {field: "Power engineering", work: "W3112152739", year: 2020, by: "Bhusal and Gautam", venue: "arXiv",
         title: "Power System Dynamic State Estimation Using Extended and Unscented Kalman Filters"},
        {field: "Epidemiology", work: "W2143469080", year: 2012, by: "Shaman and Karspeck",
         venue: "Proceedings of the National Academy of Sciences",
         title: "Forecasting seasonal outbreaks of influenza"},
        {field: "Glaciology", work: "W7147738061", year: 2026, by: "Kyanjo et al.", venue: "arXiv",
         title: "The Ice Sheet State and Parameter Estimator (ICESEE) Library (v1.0.0): Ensemble Kalman Filtering for Ice Sheet Models"},
        {field: "Spacecraft navigation", work: "W3013783567", year: 2020, by: "Chang", venue: "arXiv",
         title: "SE(3) based Extended Kalman Filter for Spacecraft Attitude Estimation"}
      ]
    },
    {
      problem: "Something matters if things that matter point to it.",
      detail: "Ranking web pages, football teams, and the amino acids that carry a signal through a protein.",
      names: "PageRank; eigenvector centrality",
      papers: [
        {field: "Web search", work: "W2952548632", year: 2014, by: "Avrachenkov et al.", venue: "TU/e Research Portal",
         title: "Personalized PageRank with Node-dependent Restart"},
        {field: "Sports", work: "W1522660207", year: 2015, by: "Lazova and Basnarkov", venue: "arXiv",
         title: "PageRank Approach to Ranking National Football Teams"},
        {field: "Protein biochemistry", work: "W2621651488", year: 2017, by: "Negre et al.", venue: "arXiv",
         title: "Eigenvector Centrality Distribution for Characterization of Protein Allosteric Pathways"}
      ]
    },
    {
      problem: "Infer which parts interact from how they vary together.",
      detail: "Amino acids in contact inside a protein; neurons wired together in the brain.",
      names: "Potts model; maximum entropy model",
      papers: [
        {field: "Structural biology", work: "W2137566700", year: 2013, by: "Ekeberg et al.", venue: "Physical Review E",
         title: "Improved contact prediction in proteins: Using pseudolikelihoods to infer Potts models"},
        {field: "Neuroscience", work: "W2069214547", year: 2013, by: "Granot-Atedgi et al.",
         venue: "PLoS Computational Biology",
         title: "Stimulus-dependent Maximum Entropy Models of Neural Population Codes"}
      ]
    }
  ];

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text) { e.textContent = text; }
    return e;
  }

  function card(f) {
    var c = el("article", "example");
    c.appendChild(el("h3", "", f.problem));
    c.appendChild(el("p", "detail", f.detail));
    var list = el("ul", "papers");
    f.papers.forEach(function (p) {
      var li = el("li");
      li.appendChild(el("span", "field", p.field));
      var a = el("a", "title", p.title);
      a.href = "https://openalex.org/" + p.work;
      li.appendChild(a);
      li.appendChild(el("span", "cite", p.by + ", " + p.year + ", " + p.venue));
      list.appendChild(li);
    });
    c.appendChild(list);
    c.appendChild(el("p", "names", "Called: " + f.names));
    return c;
  }

  // Fills every element with data-examples="all" or data-examples="<count>".
  document.querySelectorAll("[data-examples]").forEach(function (box) {
    var want = box.getAttribute("data-examples");
    var shown = want === "all" ? FAMILIES : FAMILIES.slice(0, parseInt(want, 10));
    shown.forEach(function (f) { box.appendChild(card(f)); });
  });
})();
