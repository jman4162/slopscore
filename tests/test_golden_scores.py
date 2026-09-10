"""Score bands for the adversarial-review probes. Bands, not exact floats: the scorer may be
re-calibrated, but these inputs must stay on the right side of the label boundaries."""

from __future__ import annotations

from slopscore import scan_text

ABSTRACT_HUMAN = (
    "I kept putting off the decision because every option looked worse than the last one. My "
    "sister thought I should take the job, and my father thought I should not, and neither of "
    "them would say why. I walked around the block twice before I called back. The manager was "
    "kind about it, kinder than I expected, and told me to think it over for another week. I "
    "did not need the week. I needed someone to tell me that quitting was allowed. Nobody did, "
    "so I stayed, and it turned out fine, mostly. The work got easier once I stopped pretending "
    "to like it. That is the whole story, and I still do not know whether it was the right call."
)

NON_NATIVE = (
    "I am working in this company since three years. My manager is very kind person and he "
    "help me a lot when I started. In the beginning I did not understand many things because "
    "the system was very different from my last job. Now I am responsible for the night shift "
    "and I train the new workers. We are eight people in my team. Sometimes the work is hard "
    "because we must finish all orders before morning. But I like it because the salary is "
    "good and my colleagues are friendly. Next year I want to apply for the supervisor "
    "position. My wife say I should study more English first, so I take evening class two "
    "times per week."
)

TECHNICAL_DOCS = (
    "The parser serves as a thin wrapper around the tokenizer. It provides a stable API and "
    "offers a compatibility shim. Set the API key in the environment. The test harness runs in "
    "CI. Navigate to Settings. Logging, monitoring, and alerting are configured separately. "
    "The scheduler represents a queue of pending jobs. "
) * 2

PARAPHRASED_SLOP = (
    "In our fast-moving business environment, it is essential to use strong, modern tools. No "
    "matter whether you are new or experienced, this thorough guide will examine the detailed "
    "web of solutions. In the end, technology has changed industries. Also, it is a big change. "
    "Let us look at the details. Fundamentally, innovation shows transformative potential. "
    "Besides, it helps everyone. This product is more than software. The platform is proof of "
    "modern engineering and matters in shaping the future. Specialists say that it shows a "
    "wider movement toward smooth, complete design. It is not only a tool, it is a revolution, "
    "building a lively, energetic, and transformative ecosystem. Showing a big change, the "
    "solution is a cornerstone, showing its lasting importance and adding to the wider field "
    "of innovation across the industry."
)


def test_overt_slop_is_severe(slop_text: str) -> None:
    assert scan_text(slop_text).score.slop_score >= 90


def test_concrete_human_prose_is_low(clean_text: str) -> None:
    assert scan_text(clean_text).score.slop_score < 15


def test_abstract_human_prose_is_low() -> None:
    report = scan_text(ABSTRACT_HUMAN)
    assert report.score.slop_score < 25
    assert report.findings == []


def test_non_native_plain_english_is_low() -> None:
    report = scan_text(NON_NATIVE)
    assert report.score.slop_score < 25
    assert report.findings == []


def test_technical_documentation_is_low_under_the_default_profile() -> None:
    # Under blog/conservative this scored 93.9 before v0.10 ("provides a", "offers a", "key",
    # "harness", a gerund list read as a tricolon).
    assert scan_text(TECHNICAL_DOCS).score.slop_score < 25


def test_paraphrased_slop_is_still_flagged() -> None:
    assert scan_text(PARAPHRASED_SLOP).score.slop_score >= 50


def test_short_text_abstains_and_caps_the_label() -> None:
    report = scan_text("Let's delve into this transformative, robust, holistic tapestry.")
    assert report.score.abstained
    assert report.score.label.value in ("low", "mild")


# --- long-form metadiscourse (v0.14) ----------------------------------------------------------
#
# The bands the benchmark cannot express: its rows are 13-40 words, and the defect these guard
# is a run of meta sentences buried in a long, otherwise concrete document. Measured against
# 0.13.0, the run below scored nothing at all and the document read 9.6/low.

_FACTS = (
    "The Dimson Marsh Staunton dataset covers 35 markets from 1900 through 2024. Japan peaked "
    "at 38915 on the Nikkei in December 1989 and took 34 years to recover. Russia nationalized "
    "the Saint Petersburg exchange in 1917 and China closed Shanghai in 1949. Pastor and "
    "Stambaugh published their variance result in the Journal of Finance in 2012. The 1970s "
    "produced 7.4 percent annual inflation in the United States. "
)

LONGFORM_BURIED_RUN = (
    _FACTS
    * 12
    + "\n\nA stock market going to zero is a true but loose claim. Precision matters here "
    "because the counter-argument will not survive sloppy phrasing. The defensible version "
    "is the one that separates the cases.\n\n" + _FACTS * 12
)

LONGFORM_SIGNPOSTED_CLEAN = (
    "In this section we describe the sampling frame. We drew 2,400 households from the 2019 "
    "register. As noted above, the response rate was 61 percent in Ontario and 48 percent in "
    "Quebec. In other words, roughly three in five contacted households returned the form. "
) * 8


def test_long_form_buried_run_is_caught() -> None:
    report = scan_text(LONGFORM_BURIED_RUN)
    assert len(LONGFORM_BURIED_RUN.split()) > 1000
    # Length-invariant: the same run reads the same at 120 words and at 2,000.
    assert report.dimensions.metadiscourse >= 0.5
    assert any(e.rule_id == "META_RUN_OF_META_SENTENCES" for e in report.findings)


def test_long_form_legitimate_signposting_stays_low() -> None:
    # Signposting over concrete facts is how careful and ESL writers work. Every marker here
    # sits in a sentence carrying a number, which is what the evidence gate turns on.
    report = scan_text(LONGFORM_SIGNPOSTED_CLEAN)
    assert report.dimensions.metadiscourse == 0.0
    assert report.score.slop_score < 25
