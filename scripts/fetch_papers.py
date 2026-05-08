#!/usr/bin/env python3
"""
Fetch latest anorexia nervosa research papers from PubMed E-utilities API.
Targets eating disorder, psychiatry, nutrition, neuroscience, and sports medicine journals.
Search keywords sourced from anorexia_nervosa_research_toolkit.md.
"""

import json
import sys
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError
from urllib.parse import quote_plus

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

JOURNALS = [
    "International Journal of Eating Disorders",
    "Journal of Eating Disorders",
    "European Eating Disorders Review",
    "Eating Disorders",
    "Eating Behaviors",
    "Body Image",
    "Eating and Weight Disorders",
    "American Journal of Psychiatry",
    "JAMA Psychiatry",
    "The Lancet Psychiatry",
    "Psychological Medicine",
    "Biological Psychiatry",
    "Molecular Psychiatry",
    "Translational Psychiatry",
    "British Journal of Psychiatry",
    "Behaviour Research and Therapy",
    "Clinical Psychology Review",
    "Journal of Child Psychology and Psychiatry",
    "Journal of the American Academy of Child and Adolescent Psychiatry",
    "European Child and Adolescent Psychiatry",
    "Clinical Nutrition",
    "American Journal of Clinical Nutrition",
    "Nutrition in Clinical Practice",
    "Journal of Clinical Endocrinology and Metabolism",
    "Psychosomatic Medicine",
    "British Journal of Sports Medicine",
    "Sports Medicine",
    "Medicine and Science in Sports and Exercise",
    "Psychology of Sport and Exercise",
    "Appetite",
    "Nutritional Neuroscience",
    "Psychoneuroendocrinology",
    "NeuroImage: Clinical",
    "Social Science and Medicine",
    "Journal of Adolescent Health",
    "Pediatrics",
    "JAMA Pediatrics",
    "General Hospital Psychiatry",
    "BMC Psychiatry",
    "Frontiers in Psychiatry",
    "PLOS ONE",
    "Scientific Reports",
]

CORE_TERMS = (
    '("Anorexia Nervosa"[Mesh] '
    'OR "anorexia nervosa"[tiab] '
    'OR "atypical anorexia nervosa"[tiab] '
    'OR "restrictive eating disorder*"[tiab] '
    'OR "severe and enduring anorexia nervosa"[tiab] '
    'OR "SE-AN"[tiab])'
)

EXCLUSION = (
    "NOT (cachexia[tiab] OR cancer[tiab] OR neoplasm*[tiab] OR "
    '"appetite loss"[tiab] OR "loss of appetite"[tiab])'
)

HEADERS = {"User-Agent": "AnorexiaNervosaDailyBot/1.0 (research aggregator)"}


def build_query(days: int = 7, max_journals: int = 15) -> str:
    journal_part = " OR ".join(
        [f'"{j}"[Journal]' for j in JOURNALS[:max_journals]]
    )
    lookback = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y/%m/%d"
    )
    date_part = f'"{lookback}"[Date - Publication] : "3000"[Date - Publication]'
    return f"({journal_part}) AND {CORE_TERMS} AND {date_part} AND {EXCLUSION}"


def build_broad_query(days: int = 7) -> str:
    lookback = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y/%m/%d"
    )
    date_part = f'"{lookback}"[Date - Publication] : "3000"[Date - Publication]'
    return f"{CORE_TERMS} AND {date_part} AND {EXCLUSION}"


def search_papers(query: str, retmax: int = 50) -> list[str]:
    params = (
        f"?db=pubmed&term={quote_plus(query)}"
        f"&retmax={retmax}&sort=date&retmode=json"
    )
    url = PUBMED_SEARCH + params
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"[ERROR] PubMed search failed: {e}", file=sys.stderr)
        return []


def fetch_details(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    ids = ",".join(pmids)
    params = f"?db=pubmed&id={ids}&retmode=xml"
    url = PUBMED_FETCH + params
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=60) as resp:
            xml_data = resp.read().decode()
    except Exception as e:
        print(f"[ERROR] PubMed fetch failed: {e}", file=sys.stderr)
        return []

    papers = []
    try:
        root = ET.fromstring(xml_data)
        for article in root.findall(".//PubmedArticle"):
            medline = article.find(".//MedlineCitation")
            art = medline.find(".//Article") if medline else None
            if art is None:
                continue

            title_el = art.find(".//ArticleTitle")
            title = (
                (title_el.text or "").strip()
                if title_el is not None and title_el.text
                else ""
            )

            abstract_parts = []
            for abs_el in art.findall(".//Abstract/AbstractText"):
                label = abs_el.get("Label", "")
                text = "".join(abs_el.itertext()).strip()
                if label and text:
                    abstract_parts.append(f"{label}: {text}")
                elif text:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts)[:3000]

            journal_el = art.find(".//Journal/Title")
            journal = (
                (journal_el.text or "").strip()
                if journal_el is not None and journal_el.text
                else ""
            )

            pub_date = art.find(".//PubDate")
            date_str = ""
            if pub_date is not None:
                year = pub_date.findtext("Year", "")
                month = pub_date.findtext("Month", "")
                day = pub_date.findtext("Day", "")
                parts = [p for p in [year, month, day] if p]
                date_str = " ".join(parts)

            pmid_el = medline.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""
            link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            doi = ""
            for aid in article.findall(".//PubmedData/ArticleIdList/ArticleId"):
                if aid.get("IdType") == "doi":
                    doi = aid.text or ""
                    break

            keywords = []
            for kw in medline.findall(".//KeywordList/Keyword"):
                if kw.text:
                    keywords.append(kw.text.strip())

            authors = []
            for author in art.findall(".//AuthorList/Author")[:6]:
                ln = author.findtext("LastName", "")
                ini = author.findtext("Initials", "")
                if ln:
                    authors.append(f"{ln} {ini}")
            if len(art.findall(".//AuthorList/Author")) > 6:
                authors.append("et al.")

            papers.append(
                {
                    "pmid": pmid,
                    "doi": doi,
                    "title": title,
                    "journal": journal,
                    "date": date_str,
                    "abstract": abstract,
                    "url": link,
                    "keywords": keywords,
                    "authors": authors,
                }
            )
    except ET.ParseError as e:
        print(f"[ERROR] XML parse failed: {e}", file=sys.stderr)

    return papers


def load_existing_pmids(output_path: str) -> set[str]:
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {p.get("pmid", "") for p in data.get("papers", [])}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return set()


def main():
    parser = argparse.ArgumentParser(
        description="Fetch anorexia nervosa papers from PubMed"
    )
    parser.add_argument("--days", type=int, default=7, help="Lookback days")
    parser.add_argument(
        "--max-papers", type=int, default=40, help="Max papers to fetch"
    )
    parser.add_argument("--output", default="-", help="Output file (- for stdout)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--skip-existing",
        default="",
        help="Path to existing JSON to skip already-fetched PMIDs",
    )
    args = parser.parse_args()

    existing_pmids = set()
    if args.skip_existing:
        existing_pmids = load_existing_pmids(args.skip_existing)
        if existing_pmids:
            print(
                f"[INFO] Skipping {len(existing_pmids)} existing PMIDs",
                file=sys.stderr,
            )

    query = build_query(days=args.days)
    print(
        f"[INFO] Searching PubMed for AN papers from last {args.days} days (journal-filtered)...",
        file=sys.stderr,
    )
    pmids = search_papers(query, retmax=args.max_papers)

    if len(pmids) < 10:
        print(
            "[INFO] Few results from journal filter, trying broad search...",
            file=sys.stderr,
        )
        broad_query = build_broad_query(days=args.days)
        broad_pmids = search_papers(broad_query, retmax=args.max_papers)
        new_pmids = [p for p in broad_pmids if p not in set(pmids)]
        pmids.extend(new_pmids)
        pmids = pmids[: args.max_papers]

    if existing_pmids:
        pmids = [p for p in pmids if p not in existing_pmids]

    print(f"[INFO] Found {len(pmids)} new papers", file=sys.stderr)

    if not pmids:
        print("NO_NEW_CONTENT", file=sys.stderr)
        if args.json:
            tz_taipei = timezone(timedelta(hours=8))
            output_data = {
                "date": datetime.now(tz_taipei).strftime("%Y-%m-%d"),
                "count": 0,
                "papers": [],
            }
            out_str = json.dumps(output_data, ensure_ascii=False, indent=2)
            if args.output == "-":
                print(out_str)
            else:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(out_str)
        return

    papers = fetch_details(pmids)
    print(f"[INFO] Fetched details for {len(papers)} papers", file=sys.stderr)

    tz_taipei = timezone(timedelta(hours=8))
    output_data = {
        "date": datetime.now(tz_taipei).strftime("%Y-%m-%d"),
        "count": len(papers),
        "papers": papers,
    }

    out_str = json.dumps(output_data, ensure_ascii=False, indent=2)

    if args.output == "-":
        print(out_str)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out_str)
        print(f"[INFO] Saved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
