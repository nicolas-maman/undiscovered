# Known twins: the first test of the descriptions

Written on 11 October 2026, before any paper has been described. It fixes
how the first result of the describing work will be measured, so that the
result cannot be shaped by what the descriptions turn out to say.

## The question

Do plain descriptions written by volunteers' AI models bring together
papers from different fields that solve the same problem better than the
papers' own titles and abstracts do?

That is the premise of the describing work. Kulikowski (2026) found that
rewriting papers as the computation they perform, without their field's
vocabulary, raised the average precision of retrieving such twins from
0.22 to 0.51, on 109 papers, from full texts, with one family of models.
This test asks the same question from abstracts only, with whatever models
volunteers bring.

## The papers

The curated benchmark of that study: 109 papers in 18 method families, each
family one computation re-derived in several fields under different names,
with hard distractors (same field or vocabulary, different computation).
Link list `datasets/mode_a_seed_families.csv` of
<https://github.com/ErykKul/same-problem-different-field> at commit
912badb32eff3c07926ab36f8b050a6d630e5a42, released under CC BY 4.0
(archived at <https://doi.org/10.48804/W3B9WC>).

Each paper is looked up in OpenAlex by its arXiv identifier, PubMed Central
identifier or DOI, and kept when OpenAlex has an abstract that passes the
usable rule of the first test. On 11 October 2026 that kept 87 of the 109.
The papers kept, and their families, are fixed when the units are made and
published with them.

## How the papers are described

They go into describing units like any other papers, mixed with papers of
the 2025 set, with their distinctive words computed in the same way, so a
volunteer cannot tell them apart. Each unit holding them needs results from
five volunteers instead of two, so each paper is described by several
models. A family's method name is usually among a paper's distinctive words,
so the descriptions cannot match on names, while the abstracts can: the
comparison favours the abstracts.

## The measure

- **Pool:** the benchmark papers kept, members and distractors.
- **Queries:** every member with at least one member of its family from
  another field in the pool.
- **For one query:** rank every other paper in the pool by cosine
  similarity, and compute the average precision of the members of its
  family from other fields (its twins).
- **Score:** the mean over queries (MAP).
- **Abstracts:** TF-IDF of title and abstract (English stop words removed,
  sublinear term frequency, words in at least two papers).
- **Descriptions:** the same, on each paper's problem and approach; a
  paper's vector is the mean of the vectors of its descriptions, from all
  models that described it.

The result is computed once every kept paper has descriptions from at least
three different models.

## What would count

- **Main hypothesis:** descriptions score a higher MAP than abstracts,
  with the 95% interval of the difference above zero. The interval comes
  from 2,000 bootstrap draws of families (all of a family's papers in or
  out together), seed 2026.
- **Reported alongside:** precision at 1 for both; the same comparison on
  the members whose paper does not name its method
  (`method_named = no`), where a name cannot help; and, for each model
  that described at least 30 of the papers, its MAP against the abstracts'
  on the same papers.
- **Published whatever it shows**, on the site and in this folder, with the
  code that computed it.

## What it does not show

The models may have read these papers, which were all published before
them. The test measures whether descriptions carry the computation in a
form that matches across fields, not whether they foresee anything; that is
the forward test's job. The benchmark is small, 18 families, so the
interval will be wide, and a result either way is a first indication, not a
settled answer.

## Credit

Kulikowski, E. (2026). Same Problem, Different Field: Cross-Domain Solution
Import via Domain-Stripped Computational Fingerprints. arXiv:2609.07595.
Benchmark data under CC BY 4.0.
