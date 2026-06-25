"""Build the committed v0.5 slop benchmark: the seed set plus hand-authored expansion rows.

Labels follow eval/RUBRIC.md (slop = low-quality writing, not authorship). All rows here are
original, hand-authored, and license-clean (committable + train-eligible). Large external corpora
(FinerWeb, FineWeb-Edu, Wikipedia AI-Cleanup) are fetched separately into the cache, never committed.

Run: python scripts/eval/build_benchmark.py  ->  writes eval/datasets/benchmark.jsonl
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from slopscore.eval.datasets import load_seed

# New rows beyond the seed. Each: (text, label, bucket, subgroup). label 1 = slop, 0 = clean.
NEW_ROWS: list[tuple[str, int, str, str]] = [
    # --- human_good / general (label 0): specific, factual, plain ---
    (
        "The dam holds back 29 billion cubic meters and took eight years to build, finishing in 1968.",
        0,
        "human_good",
        "general",
    ),
    (
        "Apple shipped the first iPhone in June 2007 at 499 dollars for the 4-gigabyte model.",
        0,
        "human_good",
        "general",
    ),
    (
        "The marathon route climbs 140 meters over the first 10 kilometers, then drops to the harbor.",
        0,
        "human_good",
        "general",
    ),
    (
        "She ran the bakery for 22 years and sold roughly 300 loaves a day from a single wood oven.",
        0,
        "human_good",
        "general",
    ),
    (
        "The 1923 earthquake destroyed most of the wooden city; rebuilding used reinforced concrete.",
        0,
        "human_good",
        "general",
    ),
    (
        "The patch fixed a memory leak that grew about 4 megabytes an hour under the old cache code.",
        0,
        "human_good",
        "general",
    ),
    (
        "Wheat prices fell 6 percent in August after India lifted its export ban on common varieties.",
        0,
        "human_good",
        "general",
    ),
    (
        "The orchestra has 88 players and tours for nine weeks each spring, mostly by overnight train.",
        0,
        "human_good",
        "general",
    ),
    (
        "He logged 1,140 dives over 30 years and mapped three wrecks off the Cornish coast.",
        0,
        "human_good",
        "general",
    ),
    (
        "The library added 12,000 titles in 2019 and now lends e-books to 40,000 county residents.",
        0,
        "human_good",
        "general",
    ),
    (
        "The bridge carries 60,000 vehicles a day and was repainted over four summers from 2015.",
        0,
        "human_good",
        "general",
    ),
    (
        "Rainfall hit 210 millimeters in two days, flooding the lower town and closing the rail line.",
        0,
        "human_good",
        "general",
    ),
    (
        "The vaccine trial enrolled 4,200 people across six clinics and ran for 14 months.",
        0,
        "human_good",
        "general",
    ),
    (
        "They restored the 1949 tractor over a winter, machining a new gear when no part could be found.",
        0,
        "human_good",
        "general",
    ),
    # --- raw_llm / general (label 1): dense tells ---
    (
        "In an ever-evolving digital landscape, this solution empowers organizations to unlock unprecedented value and drive meaningful transformation.",
        1,
        "raw_llm",
        "general",
    ),
    (
        "It is important to note that this approach represents a paradigm shift, fundamentally reshaping how we think about the future.",
        1,
        "raw_llm",
        "general",
    ),
    (
        "From bustling cities to serene countryside, the region offers a rich tapestry of experiences for every kind of traveler.",
        1,
        "raw_llm",
        "general",
    ),
    (
        "This groundbreaking initiative not only fosters innovation but also cultivates a culture of collaboration and shared purpose.",
        1,
        "raw_llm",
        "general",
    ),
    (
        "Navigating the complexities of modern life requires a holistic, multifaceted approach that embraces both challenge and opportunity.",
        1,
        "raw_llm",
        "general",
    ),
    (
        "Ultimately, the platform serves as a beacon of progress, illuminating the path toward a brighter and more inclusive tomorrow.",
        1,
        "raw_llm",
        "general",
    ),
    (
        "By leveraging cutting-edge technology, the team is poised to redefine the boundaries of what is truly possible.",
        1,
        "raw_llm",
        "general",
    ),
    (
        "This essay will delve into the multifaceted dimensions of the issue, shedding light on its profound and far-reaching implications.",
        1,
        "raw_llm",
        "general",
    ),
    (
        "With its unwavering commitment to excellence, the company continues to set new standards and inspire those around it.",
        1,
        "raw_llm",
        "general",
    ),
    (
        "The findings underscore the critical importance of fostering resilience in an increasingly interconnected and dynamic world.",
        1,
        "raw_llm",
        "general",
    ),
    (
        "As we move forward, it becomes increasingly clear that collaboration is the cornerstone of sustainable, long-term success.",
        1,
        "raw_llm",
        "general",
    ),
    (
        "This vibrant community thrives on creativity and passion, weaving together diverse voices into a harmonious whole.",
        1,
        "raw_llm",
        "general",
    ),
    # --- edited_llm / general (label 1): slop with grafted facts (hard positives) ---
    (
        "Founded in 2016 in Tallinn, the firm has 75 employees and stands as a testament to the transformative power of bold, visionary thinking.",
        1,
        "edited_llm",
        "general",
    ),
    (
        "The 4.5-kilometer tunnel, opened in 2022, is more than mere infrastructure; it embodies a community's enduring spirit of resilience and progress.",
        1,
        "edited_llm",
        "general",
    ),
    (
        "With 31 patents to its name, the lab leverages a holistic methodology, underscoring the profound significance of its pioneering work.",
        1,
        "edited_llm",
        "general",
    ),
    (
        "The 2020 census counted 84,000 residents, a vibrant tapestry of cultures that continues to shape the city's dynamic and evolving identity.",
        1,
        "edited_llm",
        "general",
    ),
    (
        "Processing 12 tons of beans a year, the cooperative is a shining example of how passion and purpose can drive truly meaningful change.",
        1,
        "edited_llm",
        "general",
    ),
    (
        "The album reached number three in 1998, yet its real legacy lies in how it redefined a genre and inspired a generation of artists.",
        1,
        "edited_llm",
        "general",
    ),
    (
        "Spanning 600 hectares, the reserve is not just a park but a living testament to the delicate, intricate balance of the natural world.",
        1,
        "edited_llm",
        "general",
    ),
    (
        "Serving 2,300 patients monthly, the clinic exemplifies a patient-first philosophy that fosters trust, healing, and lasting wellbeing.",
        1,
        "edited_llm",
        "general",
    ),
    # --- human_bad / general (label 1): marketing puffery ---
    (
        "Elevate your everyday with premium essentials thoughtfully designed to inspire confidence and spark joy in every moment.",
        1,
        "human_bad",
        "general",
    ),
    (
        "Our mission is simple: to empower dreamers and doers everywhere with tools that turn bold ideas into reality.",
        1,
        "human_bad",
        "general",
    ),
    (
        "Join a movement of forward-thinkers redefining the future, one breakthrough at a time, with passion and purpose.",
        1,
        "human_bad",
        "general",
    ),
    (
        "Say goodbye to limits and hello to possibility with a platform built to scale alongside your wildest ambitions.",
        1,
        "human_bad",
        "general",
    ),
    (
        "We blend artistry and innovation to craft unforgettable experiences that delight, inspire, and exceed every expectation.",
        1,
        "human_bad",
        "general",
    ),
    (
        "Trusted by industry leaders worldwide, our solutions deliver unmatched performance and value you can truly believe in.",
        1,
        "human_bad",
        "general",
    ),
    (
        "Unlock your team's full potential with intuitive, powerful tools designed for the way modern teams actually work.",
        1,
        "human_bad",
        "general",
    ),
    (
        "Experience next-level comfort and timeless style, crafted with care and built to move with you wherever life leads.",
        1,
        "human_bad",
        "general",
    ),
    # --- simple_english / human_good (label 0) ---
    (
        "The dog is brown. It likes to run in the park. Every morning my sister walks it before school.",
        0,
        "human_good",
        "simple_english",
    ),
    (
        "We cook rice for dinner. My mother adds beans and a little salt. We eat together at seven.",
        0,
        "human_good",
        "simple_english",
    ),
    (
        "The shop opens at eight. It sells bread, eggs, and milk. The old man there knows my name.",
        0,
        "human_good",
        "simple_english",
    ),
    (
        "It rained all day. The street had water on it. I wore boots and jumped over the big puddles.",
        0,
        "human_good",
        "simple_english",
    ),
    (
        "My uncle drives a bus. He starts work at five. He says the city is quiet early in the morning.",
        0,
        "human_good",
        "simple_english",
    ),
    (
        "The cat sleeps on the chair. In the day it sits by the window. At night it hunts in the yard.",
        0,
        "human_good",
        "simple_english",
    ),
    # --- non_native / human_good (label 0): clean content, ESL phrasing. The fairness test. ---
    (
        "I am working in this company since three years. My job is to test the software. Last month we found 42 bugs and fixed them before the release.",
        0,
        "human_good",
        "non_native",
    ),
    (
        "My village have one school and one clinic. The road to the town take two hours by bus. Many people there grow rice and keep some chickens.",
        0,
        "human_good",
        "non_native",
    ),
    (
        "Yesterday I go to the market and buy three kilos of tomato and one fish. The price was high because of the rain last week.",
        0,
        "human_good",
        "non_native",
    ),
    (
        "She is studying engineering in the second year. She want to build bridges in her country. The exam is in next month and she study every night.",
        0,
        "human_good",
        "non_native",
    ),
    (
        "Our team win the match by two goals. The weather was cold and the field was wet. After the game we eat together in a small restaurant.",
        0,
        "human_good",
        "non_native",
    ),
    (
        "I came to this city in 2019 for my master degree. First the winter was very hard for me. Now I have many friends and I like it here.",
        0,
        "human_good",
        "non_native",
    ),
    (
        "The factory where my father works make car parts. He is there since 15 years. They produce about 500 pieces in one day.",
        0,
        "human_good",
        "non_native",
    ),
    (
        "My grandmother cook very well. On Sunday she make a soup with seven vegetables. All the family come to her house to eat it.",
        0,
        "human_good",
        "non_native",
    ),
    (
        "Last summer we travel to the mountains by train. The journey was eight hours. We stay in a small house and walk every day to the lake.",
        0,
        "human_good",
        "non_native",
    ),
    (
        "In my country the school start in April. The children wear uniform. The classes are big, sometimes 50 students in one room.",
        0,
        "human_good",
        "non_native",
    ),
    (
        "I am learning to drive since two months. The teacher is patient. Yesterday I drive on the highway for the first time and I was nervous.",
        0,
        "human_good",
        "non_native",
    ),
    (
        "My brother repair phones in a small shop. He fix maybe ten phones in one day. He learn this work from a video on the internet.",
        0,
        "human_good",
        "non_native",
    ),
    # --- non_native (label 1): non-native slop, for balance ---
    (
        "This product is very best in the market and give you many benefits for your life and your family happiness forever.",
        1,
        "human_bad",
        "non_native",
    ),
    (
        "Our company is leader in innovation and always provide the most excellent service for make all customers very satisfied.",
        1,
        "human_bad",
        "non_native",
    ),
    # --- web_quality / clean reference (label 0) ---
    (
        "Tungsten has the highest melting point of any metal, 3,422 degrees Celsius, and is used in light-bulb filaments.",
        0,
        "web_quality",
        "general",
    ),
    (
        "The Treaty of Westphalia, signed in 1648, ended the Thirty Years' War and is often cited in histories of state sovereignty.",
        0,
        "web_quality",
        "general",
    ),
    (
        "Photosynthesis converts carbon dioxide and water into glucose and oxygen using light energy captured by chlorophyll.",
        0,
        "web_quality",
        "general",
    ),
    (
        "The standard railway gauge of 1,435 millimeters was adopted in Britain and spread with British-built railways.",
        0,
        "web_quality",
        "general",
    ),
    (
        "A leap year occurs every four years except for years divisible by 100 but not by 400, such as 1900.",
        0,
        "web_quality",
        "general",
    ),
    (
        "The Mariana Trench reaches about 10,935 meters at the Challenger Deep, the deepest known point in the ocean.",
        0,
        "web_quality",
        "general",
    ),
    # --- web_quality / boilerplate + spam (label 1) ---
    (
        "Click here now to claim your free trial! Limited time only. Subscribe today and save 50 percent on all plans, plus a bonus gift!",
        1,
        "web_quality",
        "general",
    ),
    (
        "Home | About | Services | Blog | Contact. Copyright 2026. All rights reserved. Terms of Service. Privacy Policy. Sitemap.",
        1,
        "web_quality",
        "general",
    ),
    (
        "Best cheap deals online!!! Buy now, pay later. Hot offers updated daily. Don't miss out, shop the sale before it ends tonight!",
        1,
        "web_quality",
        "general",
    ),
    (
        "Sign up for our newsletter to receive exclusive offers, expert tips, and the latest updates delivered straight to your inbox.",
        1,
        "web_quality",
        "general",
    ),
    (
        "Top 10 best products you must buy in 2026! Number 7 will shock you. Read on to discover our ultimate buyer's guide.",
        1,
        "web_quality",
        "general",
    ),
    (
        "This website uses cookies to enhance your experience. By continuing to browse, you accept our use of cookies. Accept all and continue.",
        1,
        "web_quality",
        "general",
    ),
]


def main() -> None:
    seed = [(r.text, r.label, r.bucket, r.subgroup) for r in load_seed()]
    rows = seed + NEW_ROWS
    seen: set[str] = set()
    out_rows = []
    for text, label, bucket, subgroup in rows:
        if text in seen:
            continue
        seen.add(text)
        out_rows.append({"text": text, "label": label, "bucket": bucket, "subgroup": subgroup})

    root = Path(__file__).resolve().parents[2]
    out = root / "eval" / "datasets" / "benchmark.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in out_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    n = len(out_rows)
    pos = sum(r["label"] for r in out_rows)
    print(f"wrote {n} rows ({pos} slop / {n - pos} clean) to {out}")
    print("buckets:", dict(Counter(r["bucket"] for r in out_rows)))
    print("subgroups:", dict(Counter(r["subgroup"] for r in out_rows)))
    print(
        "non_native labels:",
        dict(Counter(r["label"] for r in out_rows if r["subgroup"] == "non_native")),
    )


if __name__ == "__main__":
    main()
