# Genre profile notes (v0.2)

Profiles reweight dimensions for a genre (`scoring/profiles.py`); the default is `blog`. v0.2
values are **hand-set**, not empirically tuned — full F1 tuning across labelled genre corpora is
deferred to the evaluation milestone. The intent of each profile:

- **blog** (default): up-weight formulaic openings, genericity, significance inflation, insight
  signaling.
- **essay**: up-weight redundancy, parallelism, and insight signaling (the essayist register is
  where pseudo-profundity tells concentrate); less tolerant of padding.
- **academic**: down-weight lexical markers, copula avoidance ("constitutes/represents" is normal),
  weasel attribution (formal hedging is expected), and insight signaling ("first principles / the
  crux" are legitimate here).
- **marketing**: down-weight lexical markers, genericity, significance inflation, copula avoidance,
  formatting — marketing naturally resembles slop, so only flag severe cases.
- **technical**: down-weight lexical markers, cadence, copula avoidance ("functions/serves as" is
  precise), parallelism, and insight signaling ("load-bearing / pressure-test" are apt in
  engineering writing).
- **social**: down-weight formatting tells (em dashes/curly quotes are common); up-weight insight
  signaling.

Per-category lexicon weights (`data/lexicons/markers.yaml`, `profile_weights`) already tolerate
genre-legitimate words (e.g. "robust"/"comprehensive" in technical writing), which is why v0.2
does not also ship per-rule allow-lists. Add one if a specific rule proves noisy in a genre.
