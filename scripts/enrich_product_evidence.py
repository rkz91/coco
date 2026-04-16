#!/usr/bin/env python3
"""Enrich product evidence JSONs with per-slide content extracted via Playwright.

Reads _playwright_slides.json, maps slides to products using keyword matching,
and adds new sources to the existing product evidence files.
"""

import json
import re
from pathlib import Path

EVIDENCE_DIR = Path.home() / ".coco" / "knowledge" / "product_evidence"
SLIDES_PATH = EVIDENCE_DIR / "_playwright_slides.json"

# ──────────────────────────────────────────────────────────────────────
# Product-to-slide mapping rules
# Each product specifies:
#   - program: which SPA program section to look in
#   - keywords: terms that indicate a slide is relevant
#   - slide_titles: specific slide titles (from the SPA) that are relevant
#   - exclude_keywords: terms that indicate a slide is NOT relevant despite matching
# ──────────────────────────────────────────────────────────────────────

PRODUCT_MAP = {
    "onetrust-tpi-tpdd": {
        "program": "anti-corruption",
        "display_name": "OneTrust TPI-TPDD",
        "keywords": [
            "one trust", "onetrust", "tpdd", "due diligence",
            "risk ranking", "enhanced dd", "dow jones", "screening",
            "tpi lifecycle", "onboarding", "certification",
        ],
        "slide_titles": [
            "Executive Summary", "What We Do", "Third-Party Due Diligence",
            "AC Procedure on TPIs", "As-Is Process", "Our Vision",
            "Then vs Now", "Progress in Numbers", "User Experience Today",
            "Known Gaps", "Roadmap",
        ],
        "exclude_keywords": ["tpi tracker dashboard", "tp inventory"],
    },
    "tpi-central-data-repo": {
        "program": "anti-corruption",
        "display_name": "TPI Central Data Repo",
        "keywords": [
            "tpi-cdr", "tpi cdr", "central data", "data repository",
            "aravo", "magnit", "cms", "upstream", "pipeline",
            "integration", "snowflake", "kafka",
        ],
        "slide_titles": [
            "What We Do", "Tools Overview", "Then vs Now",
            "Third-Party Due Diligence", "Known Gaps", "Roadmap",
        ],
        "exclude_keywords": [],
    },
    "onetrust-privacy-rights": {
        "program": "privacy",
        "display_name": "OneTrust Privacy Rights",
        "keywords": [
            "privacy rights", "dsr", "data subject",
            "access", "erasure", "portability", "rectification",
        ],
        "slide_titles": [
            "Executive Summary", "Our Mission", "Tools Overview",
            "Data Subject Rights", "Regulations Covered",
            "Key Metrics", "Current State", "Roadmap 2026",
        ],
        "exclude_keywords": [],
    },
    "onetrust-mobile-app-consent": {
        "program": "privacy",
        "display_name": "OneTrust Mobile App Consent",
        "keywords": [
            "mobile app consent", "mobile consent", "app consent",
        ],
        "slide_titles": [
            "Executive Summary", "Our Mission", "Tools Overview",
            "Consent Management",
            "Key Metrics", "Current State", "Roadmap 2026",
        ],
        "exclude_keywords": [],
    },
    "onetrust-consent-rate-opt": {
        "program": "privacy",
        "display_name": "OneTrust Consent Rate Optimization",
        "keywords": [
            "consent rate", "optimization", "consent rate optimization",
            "optimize consent",
        ],
        "slide_titles": [
            "Executive Summary", "Our Mission", "Tools Overview",
            "Consent Management",
            "Key Metrics", "Current State", "Roadmap 2026",
        ],
        "exclude_keywords": [],
    },
    "onetrust-universal-cookie": {
        "program": "privacy",
        "display_name": "OneTrust Universal Cookie & Preference",
        "keywords": [
            "universal cookie", "universal preference", "preference center",
            "preference management",
        ],
        "slide_titles": [
            "Executive Summary", "Our Mission", "Tools Overview",
            "Cookie Compliance", "Consent Management",
            "Key Metrics", "Current State", "Roadmap 2026",
        ],
        "exclude_keywords": [],
    },
    "onetrust-data-guidance": {
        "program": "privacy",
        "display_name": "OneTrust Data Guidance",
        "keywords": [
            "data guidance", "privacy guidance", "privacy insights",
        ],
        "slide_titles": [
            "Executive Summary", "Our Mission", "Tools Overview",
            "Regulations Covered",
            "Key Metrics", "Current State", "Roadmap 2026",
        ],
        "exclude_keywords": [],
    },
    "onetrust-pia-dpia": {
        "program": "privacy",
        "display_name": "OneTrust PIA/DPIA",
        "keywords": [
            "pia", "dpia", "privacy impact", "data protection impact",
            "assessment", "gdpr article 35",
        ],
        "slide_titles": [
            "Executive Summary", "Our Mission", "Tools Overview",
            "PIA/DPIA Automation", "Regulations Covered",
            "Key Metrics", "Current State", "Roadmap 2026",
        ],
        "exclude_keywords": [],
    },
    "ai-case-operator": {
        "program": "regulatory-compliance",
        "display_name": "AI Case Operator",
        "keywords": [
            "ai case operator", "ai-powered", "conversational intake",
            "automated triage", "tech monitor", "gpt-powered",
            "smart routing", "auto-closure",
        ],
        "slide_titles": [
            "Executive Summary", "AI Case Operator", "Addressing the Gaps",
            "Feature Comparison", "Screening Process", "Requestor Workflow",
            "Manager Workflow", "Bulk Upload Workflow", "Key Metrics", "Roadmap",
        ],
        "exclude_keywords": [],
    },
    "kharon": {
        "program": "regulatory-compliance",
        "display_name": "Kharon",
        "keywords": [
            "kharon", "enhanced due diligence", "risk intelligence",
            "sanctions analysis", "ownership tracing",
        ],
        "slide_titles": [
            "Executive Summary", "Our Mission", "What We Screen",
            "Tools Overview", "Research Tools", "Known Gaps", "Roadmap",
        ],
        "exclude_keywords": [],
    },
    "mlex": {
        "program": None,  # Not in the SPA
        "display_name": "MLex",
        "keywords": ["mlex"],
        "slide_titles": [],
        "exclude_keywords": [],
    },
    "transparint": {
        "program": "regulatory-compliance",
        "display_name": "TransparINT",
        "keywords": [
            "transparint", "due diligence research", "adverse media",
            "background checks",
        ],
        "slide_titles": [
            "Executive Summary", "Our Mission", "What We Screen",
            "Tools Overview", "Research Tools", "Known Gaps", "Roadmap",
        ],
        "exclude_keywords": [],
    },
    "navex": {
        "program": None,  # Not directly in the SPA sections
        "display_name": "Navex",
        "keywords": ["navex", "ethicspoint", "whistleblow", "hotline"],
        "slide_titles": [],
        "exclude_keywords": [],
    },
    "mycomplianceoffice": {
        "program": None,  # Not in the SPA
        "display_name": "MyComplianceOffice",
        "keywords": ["mycomplianceoffice", "mco"],
        "slide_titles": [],
        "exclude_keywords": [],
    },
    "auditboard-ab1": {
        "program": "audit-board",
        "display_name": "AuditBoard AB1",
        "keywords": [
            "auditboard", "opsaudit", "soxhub", "crosscomply",
            "riskoversight", "grc", "audit", "sox", "icfr",
            "ab1", "connected risk",
        ],
        "slide_titles": [
            "What is AuditBoard", "McKinsey Background", "Business Problems",
            "Key Advantages", "Platform Overview", "Teams & Modules",
            "OpsAudit", "SOXHub", "CrossComply", "RiskOversight",
            "Instances", "Cells Requesting", "Governance",
            "Journey Roadmap", "TE Transition", "Cost Overview", "AI Roadmap",
        ],
        "exclude_keywords": [],
    },
    "moodys-orbis": {
        "program": "regulatory-compliance",
        "display_name": "Moody's Orbis",
        "keywords": [
            "orbis", "moody", "bvd", "company information",
            "beneficial ownership", "corporate structure",
        ],
        "slide_titles": [
            "Executive Summary", "Our Mission", "What We Screen",
            "Tools Overview", "Research Tools", "Known Gaps", "Roadmap",
        ],
        "exclude_keywords": [],
    },
}


def slide_matches_product(slide_text: str, slide_title: str, product_config: dict) -> bool:
    """Check if a slide is relevant to a product based on keywords and title."""
    text_lower = slide_text.lower()

    # Check exclude keywords first
    for kw in product_config.get("exclude_keywords", []):
        if kw.lower() in text_lower:
            return False

    # Check slide title match
    if slide_title in product_config.get("slide_titles", []):
        return True

    # Check keyword match
    for kw in product_config.get("keywords", []):
        if kw.lower() in text_lower:
            return True

    return False


def make_source_name(program_name: str, slide_title: str) -> str:
    return f"Cross-Risk-Overview / {program_name} / {slide_title} (Playwright)"


def main():
    # Load extracted slides
    with open(SLIDES_PATH) as f:
        all_slides = json.load(f)

    # Process each product
    stats = {"enriched": 0, "skipped": 0, "new_sources": 0}

    for slug, config in PRODUCT_MAP.items():
        evidence_path = EVIDENCE_DIR / f"{slug}.json"
        if not evidence_path.exists():
            print(f"  SKIP {slug}: evidence file not found")
            stats["skipped"] += 1
            continue

        with open(evidence_path) as f:
            evidence = json.load(f)

        program_id = config["program"]
        if program_id is None:
            print(f"  SKIP {slug}: not in the SPA")
            stats["skipped"] += 1
            continue

        program_data = all_slides.get(program_id)
        if not program_data:
            print(f"  SKIP {slug}: program '{program_id}' not found in slides")
            stats["skipped"] += 1
            continue

        # Remove the old giant blob source and old Playwright sources (idempotent re-run)
        old_sources = evidence.get("sources", [])
        cleaned_sources = []
        removed_blob = False
        for src in old_sources:
            # Remove the 63K char blob that was the entire Privacy section
            if src.get("type") == "presentation" and "Cross-Risk-Overview / Privacy" == src.get("name", "") and len(src.get("content", "")) > 10000:
                removed_blob = True
                print(f"  {slug}: Removed 63K char blob source")
            # Remove old Playwright sources — they'll be re-added below
            elif "(Playwright)" in src.get("name", ""):
                pass
            else:
                cleaned_sources.append(src)

        # Existing non-Playwright source names (to avoid duplicating original BS4 sources)
        existing_names = {s["name"] for s in cleaned_sources}

        new_sources_added = 0
        program_name = program_data["name"]

        for slide in program_data["slides"]:
            slide_title = slide["title"]
            slide_text = slide["text"]

            # Skip very short slides (title slides, etc.)
            if slide["textLength"] < 100:
                continue

            if not slide_matches_product(slide_text, slide_title, config):
                continue

            source_name = make_source_name(program_name, slide_title)

            # Skip if already exists (from a prior run without Playwright tag)
            if source_name in existing_names:
                continue

            cleaned_sources.append({
                "type": "presentation",
                "name": source_name,
                "content": slide_text,
            })
            new_sources_added += 1

        if new_sources_added > 0 or removed_blob:
            evidence["sources"] = cleaned_sources
            evidence["source_count"] = len(cleaned_sources)

            # Re-classify tier based on new source count and content depth
            total_chars = sum(len(s.get("content", "")) for s in cleaned_sources)
            if total_chars > 5000 and len(cleaned_sources) >= 6:
                evidence["evidence_tier"] = "standard"
            elif total_chars > 2000 and len(cleaned_sources) >= 3:
                evidence["evidence_tier"] = "thin"
            else:
                evidence["evidence_tier"] = "stub"

            with open(evidence_path, "w") as f:
                json.dump(evidence, f, indent=2)

            print(f"  OK {slug}: +{new_sources_added} slide sources, {len(cleaned_sources)} total, tier={evidence['evidence_tier']}, {total_chars} chars")
            stats["enriched"] += 1
            stats["new_sources"] += new_sources_added
        else:
            print(f"  NOOP {slug}: no new slides matched")
            stats["skipped"] += 1

    print(f"\nDone: {stats['enriched']} products enriched, {stats['new_sources']} new sources added, {stats['skipped']} skipped")


if __name__ == "__main__":
    main()
