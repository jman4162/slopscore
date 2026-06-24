# Genre profile notes (v0.2)

Profiles reweight dimensions for a genre (`scoring/profiles.py`); the default is `blog`. v0.2
values are **hand-set**, not empirically tuned — full F1 tuning across labelled genre corpora is
deferred to the evaluation milestone. The intent of each profile:

- **blog** (default): up-weight formulaic openings, genericity, significance inflation.
- **essay**: up-weight redundancy and parallelism; less tolerant of padding.
- **academic**: down-weight lexical markers, copula avoidance ("constitutes/represents" is normal),
  and weasel attribution (formal hedging is expected).
- **marketing**: down-weight lexical markers, genericity, significance inflation, copula avoidance,
  formatting — marketing naturally resembles slop, so only flag severe cases.
- **technical**: down-weight lexical markers, cadence, copula avoidance ("functions/serves as" is
  precise), parallelism.
- **social**: down-weight formatting tells (em dashes/curly quotes are common).

Per-category lexicon weights (`data/lexicons/markers.yaml`, `profile_weights`) already tolerate
genre-legitimate words (e.g. "robust"/"comprehensive" in technical writing), which is why v0.2
does not also ship per-rule allow-lists. Add one if a specific rule proves noisy in a genre.
