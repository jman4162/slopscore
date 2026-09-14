# Genre profile notes (v0.2)

Profiles reweight dimensions for a genre (`scoring/profiles.py`); the default is `blog`. v0.2
values are **hand-set**, not empirically tuned — full F1 tuning across labelled genre corpora is
deferred to the evaluation milestone. The intent of each profile:

- **blog** (default): up-weight formulaic openings, genericity, significance inflation, insight
  signaling, and metadiscourse.
- **essay**: up-weight redundancy, parallelism, insight signaling (the essayist register is
  where pseudo-profundity tells concentrate), and metadiscourse; less tolerant of padding.
- **academic**: down-weight lexical markers, copula avoidance ("constitutes/represents" is normal),
  weasel attribution (formal hedging is expected), and insight signaling ("first principles / the
  crux" are legitimate here). Metadiscourse is halved: IMRaD signposting ("In this section we
  describe...", "As noted above") is a genre requirement, not a tell.
- **marketing**: down-weight lexical markers, genericity, significance inflation, copula avoidance,
  formatting — marketing naturally resembles slop, so only flag severe cases. Metadiscourse is
  0.8: "In this guide we will show you", "TL;DR:" and "Key takeaways:" are the genre's native
  register.
- **technical**: down-weight lexical markers, cadence, copula avoidance ("functions/serves as" is
  precise), parallelism, and insight signaling ("load-bearing / pressure-test" are apt in
  engineering writing). Metadiscourse is halved: reference docs cross-reference by design.
- **social**: down-weight formatting tells (em dashes/curly quotes are common) and metadiscourse
  ("TL;DR" and "to be clear," are native register in a thread); up-weight insight signaling.

Per-category lexicon weights (`data/lexicons/markers.yaml`, `profile_weights`) already tolerate
genre-legitimate words (e.g. "robust"/"comprehensive" in technical writing), which is why v0.2
does not also ship per-rule allow-lists. Add one if a specific rule proves noisy in a genre.
