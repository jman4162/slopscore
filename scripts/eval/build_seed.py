"""Build the committed seed evaluation set (``eval/datasets/seed.jsonl``).

A small, hand-authored, license-clean seed corpus across the four buckets the spec calls for:
human-good, raw-LLM-style slop, edited/humanized slop, and human-bad (vague human marketing/SEO).
It is deliberately diverse to limit the leakage between the WP:AISIGNS-derived features and the
labels. The large public corpora (RAID/MAGE/Kobak) are fetched separately (scripts/eval/fetch_*),
never committed. Re-run: ``python scripts/eval/build_seed.py``.

label: 1 = slop patterns present, 0 = clean. subgroup is used for fairness slices.
"""

from __future__ import annotations

import json
from pathlib import Path

# --- label 0: clean human-good (specific, plain, varied topics) ------------------------------
HUMAN_GOOD = [
    "The factory opened in 1962 on a 14-acre site east of Cleveland and employed 1,200 people.",
    "Strauss fought the Navy for two years over the bridge design before work began in 1933.",
    "We drove to Bend in October; the pass iced over near the summit and the wipers froze twice.",
    "The cache bug was a race condition. I added a lock, ran the tests fifty times, and shipped it.",
    "Harian Metro was established in March 1991 as Malaysia's first Malay-language afternoon tabloid.",
    "The recipe needs 240 grams of flour, two eggs, and a 20-minute rest before the dough is rolled.",
    "Ellis did most of the math for the towers but received no public credit until the 1990s.",
    "The river drains 3,400 square kilometers and floods most years after the August monsoon.",
    "She sold about 200 records a week and graded the used vinyl by eye under a desk lamp.",
    "The 1977 schedule change raised output 12 percent over two years before the plant closed.",
    "Voter turnout fell to 41 percent in the off-year election, the lowest since the county began counting.",
    "The telescope's mirror is 8.1 meters across and was polished to within 25 nanometers of its shape.",
    "After the merger the firm cut 300 jobs in Leeds and moved accounting to a Manila office.",
    "The trail climbs 900 meters in four kilometers, then traverses scree below the north face.",
    "Copper prices rose 4 percent in March on a strike at the Escondida mine in Chile.",
    "He coached the team for nine seasons, won two titles, and retired after the 2008 final.",
]

# --- label 1: raw-LLM-style slop (puffery, -ing, parallelism, AI vocab) ----------------------
RAW_LLM = [
    "In today's fast-paced world, this platform stands as a testament to innovation, reflecting "
    "its broader significance across the evolving landscape.",
    "It is not just a tool, it is a revolution, fostering a vibrant, dynamic, and transformative "
    "ecosystem for everyone involved.",
    "The festival plays a pivotal role in the region, marking a significant shift and underscoring "
    "its enduring cultural importance.",
    "Experts argue that the initiative leverages a robust, holistic framework, highlighting its "
    "lasting impact on the community.",
    "This comprehensive guide will delve into the intricate tapestry of solutions, empowering "
    "readers to unlock their full potential.",
    "The museum serves as a cornerstone of local identity, contributing to the broader history "
    "and showcasing a rich cultural heritage.",
    "Ultimately, the technology has revolutionized industries, seamlessly weaving together "
    "creativity and progress in unprecedented ways.",
    "The company maintains an active social media presence and has been featured in numerous "
    "prominent media outlets, demonstrating its growing influence.",
    "At its core, the project embodies a multifaceted approach, navigating challenges while "
    "fostering meaningful and impactful change.",
    "Whether you are a beginner or an expert, this solution offers a seamless experience, "
    "elevating productivity and illuminating new possibilities.",
    "The town boasts a diverse array of attractions, nestled in the heart of a region renowned "
    "for its breathtaking natural beauty.",
    "Moreover, the framework underscores the crucial interplay between strategy and execution, "
    "reflecting a deeper commitment to excellence.",
    "Despite its success, the program faces several challenges; however, ongoing initiatives "
    "position it to continue to thrive in the years ahead.",
    "The artist's work is a vibrant tapestry of emotion and meaning, resonating deeply and "
    "leaving an indelible mark on contemporary culture.",
]

# --- label 1: edited / humanized slop (slop patterns + some concrete details) ----------------
EDITED_LLM = [
    "Founded in 2014, the startup stands as a testament to innovation, and its 40-person team "
    "in Austin continues to foster a dynamic and transformative culture.",
    "The 1.2-kilometer promenade, opened in 2019, plays a pivotal role in the city, reflecting a "
    "broader movement toward walkable, vibrant public space.",
    "Dr. Mensah's lab leverages a robust methodology and, with 18 published papers, underscores "
    "the enduring significance of its work on coral resilience.",
    "The 320-page report, released in March, highlights the intricate interplay of policy and "
    "markets, contributing to the broader conversation on housing.",
    "Now serving 5,000 daily riders, the line serves as a cornerstone of regional transit, "
    "showcasing the area's commitment to sustainable growth.",
    "The cafe, which roasts 200 kilograms a week, embodies a holistic philosophy, fostering a "
    "rich tapestry of community and craft on Glebe Point Road.",
    "Released in 2021 to strong reviews, the album is more than just a record; it is a bold, "
    "genre-blending statement that marks a turning point for the band.",
    "With a 12-megawatt capacity, the plant not only powers 9,000 homes but also exemplifies a "
    "transformative shift toward a cleaner, more resilient grid.",
]

# --- label 1: human-bad (vague human marketing / SEO; no AI generation) ----------------------
HUMAN_BAD = [
    "Our team is passionate about delivering best-in-class solutions that exceed expectations "
    "and drive real results for businesses of all sizes.",
    "We pride ourselves on world-class service and a customer-first mindset that sets us apart "
    "from the competition in every way that matters.",
    "Unlock the power of next-generation tools designed to take your workflow to the next level "
    "and beyond, today and into the future.",
    "Our cutting-edge platform empowers you to achieve more, faster, with seamless integrations "
    "and unparalleled flexibility at your fingertips.",
    "Discover a smarter way to work with our innovative suite of products, trusted by thousands "
    "of happy customers around the globe.",
    "We are committed to excellence and dedicated to helping you succeed every step of the way, "
    "no matter how big or small your goals.",
    "Experience the difference that true quality makes, with premium materials and timeless "
    "design crafted to last a lifetime.",
    "Transform your business with our game-changing approach that redefines what's possible and "
    "delivers value you can count on.",
]

# --- label 0: fairness subgroup — plain / simple English (clean, must NOT be flagged) --------
SIMPLE_ENGLISH = [
    "The man walks to the shop. He buys bread and milk. He pays with coins and goes home.",
    "My city is near the sea. In summer many people come. They swim and eat fish by the water.",
    "She studies at night. She wants to be a nurse. The school is far, so she takes two buses.",
    "The farm has cows and a dog. We wake up early. We give the cows water and clean the barn.",
    "I like to read books. My favorite book is about a boat. The boat sails to a small island.",
    "He fixed the bike. The chain was loose. Now the bike works well and he rides it to work.",
    "We planted beans in May. The rain came late. In July we picked the beans and made soup.",
    "The bus was late today. I waited in the cold. When it came, I found a seat near the door.",
]


def _rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for t in HUMAN_GOOD:
        rows.append({"text": t, "label": 0, "bucket": "human_good", "subgroup": "general"})
    for t in RAW_LLM:
        rows.append({"text": t, "label": 1, "bucket": "raw_llm", "subgroup": "general"})
    for t in EDITED_LLM:
        rows.append({"text": t, "label": 1, "bucket": "edited_llm", "subgroup": "general"})
    for t in HUMAN_BAD:
        rows.append({"text": t, "label": 1, "bucket": "human_bad", "subgroup": "general"})
    for t in SIMPLE_ENGLISH:
        rows.append({"text": t, "label": 0, "bucket": "human_good", "subgroup": "simple_english"})
    return rows


def main() -> None:
    out = Path(__file__).resolve().parents[2] / "eval" / "datasets" / "seed.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in _rows():
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(_rows())} rows to {out}")


if __name__ == "__main__":
    main()
