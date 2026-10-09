# Data dictionary

What every file and field in the project means. All data the project
publishes is CC0, derived from [OpenAlex](https://openalex.org), which is
also CC0. "Topic" always means an OpenAlex topic (4,516 of them, each in one
of four domains), and a work counts under its *primary* topic only.

## The tables of pairs (for any language)

`pairs_2011.csv` and `pairs_2017.csv`, attached to the
[backtest release](https://github.com/nicolas-maman/undiscovered/releases),
are the first test's data, one row per pair of topics from different domains
that had at most one link up to the freeze year. The 2011 table is the one the
models were fitted on; the 2017 table is the one they were judged on. Made by
`python -m undiscovered_research.export`; the scores in the 2017 table
reproduce the published average precisions exactly.

**Who the pair is**

| column | meaning |
|---|---|
| `topic_a`, `topic_b` | OpenAlex topic IDs, for example `T10014` (see `https://openalex.org/T10014`) |
| `name_a`, `name_b`, `field_a`, `field_b`, `domain_a`, `domain_b` | OpenAlex's name, field and domain for each |

**Links.** A link from A to B is a work whose primary topic is A that cites
at least one of B's *reference papers*: the 100 papers of B, published up to
the freeze year, most cited up to the end of that year.

| column | meaning |
|---|---|
| `prior_link_count` | links in both directions in every year up to the freeze (0 or 1, by the eligibility rule) |
| `links_a_to_b`, `links_b_to_a` | links in each direction in the six years after the freeze |
| `links_after` | their sum |
| `connected` | 1 if `links_after` is at least 3: the label the models predict |
| `strict_links_after` | (2017 only) the same count, keeping only articles and reviews that OpenAlex does not also file under the other topic's subfield |
| `connected_strict` | (2017 only) 1 if `strict_links_after` is at least 3 |

**Features**, all computed from data up to the freeze year. For a pair, `hi`
and `lo` are the larger and smaller of the two topics' values. The train
window is the eight years up to the freeze (2004 to 2011, or 2010 to 2017);
the recent window is its last three.

| column | meaning |
|---|---|
| `log_size_hi`, `log_size_lo` | natural log of 1 plus the topic's works in the train window |
| `growth_hi`, `growth_lo` | natural log of (works in the last four years of the train window + 1) / (works in its first four + 1) |
| `log_usable_hi`, `log_usable_lo` | natural log of the number of usable abstracts among 40 sampled (English, at least 40 words; 5 to 40) |
| `dp_health_physical`, `dp_health_social`, `dp_life_physical`, `dp_life_social`, `dp_physical_social` | 1 if the pair's two domains are these; Health and Life Sciences is the reference, with all five at 0 |
| `log_deg_hi`, `log_deg_lo` | natural log of 1 plus the number of other topics citing the topic's reference papers in the train window |
| `log_recent_deg_hi`, `log_recent_deg_lo` | the same, in the recent window |
| `log_common` | natural log of 1 plus the number of topics citing both topics' reference papers in the train window |
| `log_recent_common` | the same, in the recent window |
| `jaccard` | topics citing both, divided by topics citing either (train window) |
| `adamic_adar` | for each topic citing both, 1 / ln(1 + the number of sampled topics it cites), summed |
| `cocite_cosine` | cosine between the two topics' vectors of citing works per citing topic (train window; a topic's citations of itself left out) |
| `log_two_hop` | natural log of 1 plus the number of third sampled topics Z with A citing Z and Z citing B, plus the reverse |
| `prior_links` | the same as `prior_link_count`, as the models see it |
| `centroid_cos` | cosine between the two topics' average TF-IDF vectors of usable abstracts |
| `top_pairs_cos` | mean of the five highest cosines between single abstracts of the two topics, using at most 20 per topic |

**Scores** (2017 only): `score_popularity`, `score_network`,
`score_semantic`, `score_combined` are each model's predicted probability
that the pair connects, from the models fitted on the 2011 table.

## Topic records (the first test)

`research/data/topics/<freeze>/<topic>.json`, one per sampled topic and
freeze year, made by `python -m undiscovered_research.collect`.

| field | meaning |
|---|---|
| `format` | record layout version (2) |
| `sample` | fingerprint of the topic sample the record belongs to |
| `topic`, `cutoff` | the topic and the freeze year |
| `retrieved` | date the record was fetched from OpenAlex |
| `train_window`, `recent_window`, `test_window` | first and last year of each window |
| `size` | the topic's works in the train window |
| `works_by_year` | the topic's works per year in the train window |
| `instrument` | the reference papers (work IDs) |
| `abstracts` | 40 randomly sampled works from the train window: `id`, `year`, and `text` (title and abstract) |
| `cited_by_train`, `cited_by_recent` | for every topic whose works cite the reference papers in that window, how many works |
| `cited_by_before`, `cited_by_test` | the same for every year before the train window and for the test window, for the sampled topics only |

## Map records (the distributed map)

`records/<topic>.json` on the
[`map-2025` branch](https://github.com/nicolas-maman/undiscovered/tree/map-2025),
made by volunteers' clients and checked by the intake job; the format is
`schemas/map-record.schema.json`. The same fields as a topic record, at the
end of 2025, with four differences: `freeze` instead of `cutoff`;
`cited_by_before` covers every citing topic; there is no test window yet;
and `usable_abstracts` (a count, 0 to 40) replaces `abstracts`.

## The published report

`data/backtest.json`, read by the results page:

| field | meaning |
|---|---|
| `commit` | the commit whose code produced the numbers |
| `report.config` | settings, and the Python and package versions used |
| `report.pairs` | how many pairs at each freeze, and how many connected |
| `report.models.<name>` | each model's average precision with its 95% interval, ROC-AUC, precision at 100 and 1,000, and fitted coefficients |
| `report.hypotheses` | H1 to H3 as in the plan, each with the difference, its 95% interval, and the outcome |
| `report.strict` | the check against misfiled papers |
| `report.decision` | `continue` or `stop`, by the plan's rule |
| `report.by_domain_pair`, `report.directions`, `report.feature_shift`, `report.top_predictions` | descriptive tables |
| `robustness` | each check listed in the plan, or why it was not run |
