#!/usr/bin/env node
/**
 * Playwright script to extract per-slide text from the Cross-Risk-Overview SPA.
 *
 * The SPA has a sidebar with 5 programs, each with slides navigable via ArrowRight.
 * This script:
 *   1. Opens the local HTML file
 *   2. Clicks each program in the sidebar
 *   3. Iterates slides with ArrowRight
 *   4. Extracts visible text per slide (using the slide counter to deduplicate)
 *   5. Outputs JSON mapping program -> slide -> text
 */
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

// Slide definitions from the SPA source (variable names: ia, la, ra, oa, ca)
const PROGRAMS = [
  {
    id: "regulatory-compliance",
    sidebarName: "Regulatory Compliance",
    slideCount: 21,
    slides: [
      "Title", "Agenda", "Executive Summary", "Our Mission", "What We Screen",
      "Risk Types", "Current Challenges", "Known Gaps", "Current Portal",
      "Tools Overview", "Bridger Architecture", "Research Tools",
      "AI Case Operator", "Addressing the Gaps", "Feature Comparison",
      "Screening Process", "Requestor Workflow", "Manager Workflow",
      "Bulk Upload Workflow", "Key Metrics", "Roadmap",
    ],
  },
  {
    id: "anti-corruption",
    sidebarName: "Anti-Corruption",
    slideCount: 22,
    slides: [
      "Title", "Agenda", "Executive Summary", "Our Mission", "What We Do",
      "Third Party", "Third Party Intermediaries", "Risk Areas",
      "Business Problems", "The Old Experience", "Our Vision", "Then vs Now",
      "AC Procedure on TPIs", "As-Is Process", "Third-Party Due Diligence",
      "Tools Overview", "TPI Tracker", "TP Inventory", "Progress in Numbers",
      "User Experience Today", "Known Gaps", "Roadmap",
    ],
  },
  {
    id: "privacy",
    sidebarName: "Privacy",
    slideCount: 14,
    slides: [
      "Title", "Agenda", "Executive Summary", "Our Mission", "Tools Overview",
      "PIA/DPIA Automation", "Cookie Compliance", "Regulations Covered",
      "Data Mapping", "Data Subject Rights", "Consent Management",
      "Key Metrics", "Current State", "Roadmap 2026",
    ],
  },
  {
    id: "optimize",
    sidebarName: "Optimize",
    slideCount: 15,
    slides: [
      "Title", "Agenda", "What is Optimize", "Our Vision", "Third Parties",
      "Operating Areas", "KPIs", "TP Inventory", "Key Features", "Data Sources",
      "Architecture", "User Personas", "User Journey", "Current State",
      "Success Metrics",
    ],
  },
  {
    id: "audit-board",
    sidebarName: "AuditBoard",
    slideCount: 19,
    slides: [
      "Title", "Agenda", "What is AuditBoard", "McKinsey Background",
      "Business Problems", "Key Advantages", "Platform Overview",
      "Teams & Modules", "OpsAudit", "SOXHub", "CrossComply",
      "RiskOversight", "Instances", "Cells Requesting", "Governance",
      "Journey Roadmap", "TE Transition", "Cost Overview", "AI Roadmap",
    ],
  },
];

const HTML_PATH =
  "/Users/Rijul_Kalra/Downloads/Old Downloads/Cross-Risk-Overview.html";
const OUTPUT_PATH =
  "/Users/Rijul_Kalra/.coco/knowledge/product_evidence/_playwright_slides.json";

/**
 * Extract visible text from the current slide, filtering out off-screen elements.
 */
async function extractCurrentSlideText(page) {
  return page.evaluate(() => {
    const main = document.querySelector("main");
    if (!main) return { text: "", counter: "" };

    // Get the viewport dimensions
    const vw = window.innerWidth;
    const vh = window.innerHeight;

    // Find the slide counter (e.g. "3 / 21")
    let counter = "";
    const spans = main.querySelectorAll("span");
    for (const span of spans) {
      const t = span.textContent.trim();
      if (/^\d+\s*\/\s*\d+$/.test(t)) {
        counter = t;
        break;
      }
    }

    // Collect text from elements that are actually visible and within viewport
    const textParts = new Set(); // Use Set to deduplicate
    const allElements = main.querySelectorAll(
      "h1, h2, h3, h4, h5, h6, p, span, li, td, th, div, label, a, strong, em, b, i"
    );

    for (const el of allElements) {
      // Skip if this element has children that are also block elements
      // (to avoid double-counting parent + child)
      if (
        el.tagName === "DIV" &&
        el.querySelector("h1,h2,h3,h4,h5,h6,p,li,td,th")
      ) {
        continue;
      }

      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);

      // Must be visible
      if (
        style.display === "none" ||
        style.visibility === "hidden" ||
        parseFloat(style.opacity) < 0.1
      )
        continue;

      // Must be within viewport (slide content area)
      if (rect.width === 0 || rect.height === 0) continue;
      if (rect.right < 0 || rect.left > vw) continue;
      if (rect.bottom < 0 || rect.top > vh) continue;

      // Skip print-only and navigation elements
      if (el.closest("[data-print-hide]")) continue;
      if (el.closest("aside")) continue;
      if (el.closest("nav")) continue;

      // Get direct text content (not child elements' text)
      let text = "";
      for (const child of el.childNodes) {
        if (child.nodeType === Node.TEXT_NODE) {
          text += child.textContent;
        }
      }
      text = text.trim();
      if (text && text.length > 1) {
        textParts.add(text);
      }
    }

    return {
      text: [...textParts].join(" | "),
      counter,
    };
  });
}

async function extractSlides() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
  });
  const page = await context.newPage();

  console.log("Opening HTML file...");
  await page.goto(`file://${HTML_PATH}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  const allSlides = {};

  for (const program of PROGRAMS) {
    console.log(
      `\n=== Program: ${program.sidebarName} (${program.id}) — ${program.slideCount} slides ===`
    );

    // Click sidebar item
    const sidebarButton = page
      .locator(`aside button`, { hasText: program.sidebarName })
      .first();
    const buttonCount = await sidebarButton.count();

    if (buttonCount === 0) {
      // Try clicking a link or div with the text
      const alt = page
        .locator(`aside >> text="${program.sidebarName}"`)
        .first();
      const altCount = await alt.count();
      console.log(`  Sidebar button not found, trying text link (${altCount} found)`);
      if (altCount > 0) {
        await alt.click();
      } else {
        console.log(`  SKIP: Cannot find entry for ${program.sidebarName}`);
        continue;
      }
    } else {
      await sidebarButton.click();
    }

    await page.waitForTimeout(1500);

    // Focus main area for keyboard events
    await page.locator("main").first().click({ position: { x: 500, y: 500 } });
    await page.waitForTimeout(500);

    const programSlides = [];
    let lastCounter = "";
    let stuckCount = 0;

    for (let slideIdx = 0; slideIdx < program.slideCount; slideIdx++) {
      const { text, counter } = await extractCurrentSlideText(page);

      // Check if we're actually advancing
      if (counter === lastCounter && slideIdx > 0) {
        stuckCount++;
        if (stuckCount > 2) {
          console.log(`  STUCK at slide ${slideIdx}, counter=${counter}. Breaking.`);
          break;
        }
        // Try clicking main area again and pressing ArrowRight
        await page.locator("main").first().click({ position: { x: 500, y: 500 } });
        await page.waitForTimeout(200);
        await page.keyboard.press("ArrowRight");
        await page.waitForTimeout(500);
        const retry = await extractCurrentSlideText(page);
        if (retry.counter !== lastCounter) {
          // Recovered
          stuckCount = 0;
          programSlides.push({
            index: slideIdx,
            title: program.slides[slideIdx] || `Slide ${slideIdx}`,
            counter: retry.counter,
            text: retry.text,
            textLength: retry.text.length,
          });
          lastCounter = retry.counter;
          console.log(
            `  [${retry.counter}] ${program.slides[slideIdx] || "?"} — ${retry.text.length} chars (recovered)`
          );
          if (slideIdx < program.slideCount - 1) {
            await page.keyboard.press("ArrowRight");
            await page.waitForTimeout(400);
          }
          continue;
        }
      } else {
        stuckCount = 0;
      }

      lastCounter = counter;
      programSlides.push({
        index: slideIdx,
        title: program.slides[slideIdx] || `Slide ${slideIdx}`,
        counter,
        text,
        textLength: text.length,
      });

      console.log(
        `  [${counter}] ${program.slides[slideIdx] || "?"} — ${text.length} chars`
      );

      // Navigate to next slide
      if (slideIdx < program.slideCount - 1) {
        await page.keyboard.press("ArrowRight");
        await page.waitForTimeout(400);
      }
    }

    allSlides[program.id] = {
      name: program.sidebarName,
      slideCount: program.slideCount,
      slides: programSlides,
    };
  }

  // Write output
  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(allSlides, null, 2));
  console.log(`\nWrote extracted slides to ${OUTPUT_PATH}`);

  // Print summary
  for (const [progId, data] of Object.entries(allSlides)) {
    const totalChars = data.slides.reduce((sum, s) => sum + s.textLength, 0);
    const nonEmpty = data.slides.filter((s) => s.textLength > 10).length;
    const uniqueTexts = new Set(data.slides.map((s) => s.text)).size;
    console.log(
      `  ${progId}: ${nonEmpty}/${data.slideCount} non-empty, ${uniqueTexts} unique, ${totalChars} total chars`
    );
  }

  await browser.close();
}

extractSlides().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
