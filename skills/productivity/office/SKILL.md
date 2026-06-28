---
name: office
description: Build polished PowerPoint decks, Word documents and PDF reports that actually look right. A manager plans, cheap parallel workers draft each section, designed templates own the layout, and a vision gate checks every rendered page before you deliver. Use this for any "make me a deck/presentation/slides/report/document" request.
license: Proprietary
platforms: [linux, macos, windows]
version: 1.0.0
author: EnergyIR
metadata:
  hermes:
    tags: [PowerPoint, Presentations, Slides, Documents, Office, Reports]
---

# Office mode — decks that get reused, not used once

Old approach (do NOT use): writing slide coordinates by hand. You cannot see the
result, so text overflows and boxes overlap. **Instead you DESCRIBE the content;
designed templates own the layout, and a vision gate checks the rendered pages.**

## The pipeline (follow in order)

### 1. Plan (you, the manager)
Produce three things and keep them:
- **Outline** — the slide list: for each slide a `layout` and one line of intent.
- **Style guide** — `theme` (`light` or `dark`) and the tone (e.g. "crisp, executive").
- **Acceptance criteria** — one short, checkable line per slide (e.g. "title slide:
  big title, one subtitle, nothing else"; "bullets: at most 5 short bullets").

**Stop-the-line gate:** do not fan out until the outline + theme are sensible. A bad
plan parallelised is just fast garbage.

### 2. Draft the content (fan out to cheap workers)
For a deck with several distinct sections, draft them **in parallel** with
`delegate_task` (batch form, up to 6 workers). Each worker drafts ONE section's
**content only** — never layout. Give each worker its slice of the outline and ask
it to return JSON slide objects (see the spec below). Example call shape:

```
delegate_task(tasks=[
  {goal: "Draft the 'Results' slides as deck-spec JSON: a bullets slide (<=5 bullets) and a two_column slide. Return ONLY the JSON array of slide objects.", context: "<the outline + style for this section>", toolsets: ["web"]},
  {goal: "Draft the 'Risks' slides ...", context: "...", toolsets: ["web"]},
  ...
])
```

Workers cannot run code or build files — they only return content. Small decks
(1–3 sections) you can draft yourself without delegating.

### 3. Assemble the deck spec
Collect the workers' slide objects into ONE spec and write it to `deck.json`:

```json
{
  "title": "Quarterly Review",
  "theme": "light",
  "slides": [
    {"layout": "title",   "title": "Quarterly Review", "subtitle": "Q2 2026"},
    {"layout": "section", "title": "Results"},
    {"layout": "bullets", "title": "Highlights", "bullets": ["Revenue up 18%", "Churn down", "NPS 61"]},
    {"layout": "two_column", "title": "Wins vs Risks",
     "left_title": "Wins",  "left":  ["Launched X", "Signed Y"],
     "right_title": "Risks", "right": ["Hiring", "Latency"]},
    {"layout": "quote",   "quote": "Make it work, then make it good.", "attribution": "Team"},
    {"layout": "closing", "title": "Thank you", "subtitle": "Questions?"}
  ]
}
```

**Layouts:** `title` (title, subtitle) · `section` (title) · `bullets` (title,
bullets[]) · `two_column` (title, left_title, left[], right_title, right[]) ·
`quote` (quote, attribution) · `closing` (title, subtitle) · `table` (title,
headers[], rows[][]) · `chart` (title, chart_type: column|bar|line|pie,
categories[], series:{name:[numbers]}) · `image` (title, image_path, caption).
Keep bullets short
(<= 5 per slide, one line each) — the template autofits, but brevity reads better.

### 4. Build (you)
Call the **`build_presentation`** tool with your deck spec — NOT a terminal script
and NOT `import pptx` (a terminal Python lacks python-pptx and the office modules;
the tool runs in-process where they auto-install):

```
build_presentation(spec={...deck spec...}, out_path="/abs/path/out.pptx")
```

It returns `{"path": ..., "slides": N, "warnings": [...]}`. Fix any warnings.

### 5. Visual QA gate — render and LOOK (you)
Call the **`render_check`** tool on the built file, passing your acceptance criteria:

```
render_check(path="out.pptx", criteria="<your per-slide criteria, summarised>")
```

It renders every slide to an image and returns a per-page verdict
`{overall_pass, pages:[{page, pass, issues:[{type, where, fix}]}], ...}`. For each
failing page, apply the suggested fix **to the deck spec** (trim text, split a
crowded slide into two, switch layout, shorten a title), rebuild, and re-run
`render_check`. **Cap at 2 fix passes per slide**; if a page still fails, simplify
its content rather than looping. (The first `render_check` on a machine without
LibreOffice will set up the renderer once.)

### 6. Synthesise and deliver (you)
Read the deck end to end for one consistent voice and clean transitions, then hand
over `out.pptx`. Mention briefly that it was visually checked.

## Word documents and PDF reports

Same pipeline, different builder. For a report or document, draft the content as a
**doc spec** (ordered blocks) and build with `build_docx.py`:

```json
{
  "title": "Operations Report", "subtitle": "Q2 2026", "theme": "light",
  "blocks": [
    {"type": "heading", "text": "Summary", "level": 1},
    {"type": "paragraph", "text": "..."},
    {"type": "bullets", "items": ["...", "..."]},
    {"type": "table", "headers": ["Metric", "Value"], "rows": [["Revenue", "1.2M"]]},
    {"type": "image", "path": "/abs/fig1.png", "caption": "Figure 1", "width_in": 6.0},
    {"type": "paragraph", "text": "..."}
  ]
}
```

Block types: `heading` (text, level 1–2) · `paragraph` (text) · `bullets` (items[])
· `table` (headers[], rows[][]) · `image` (path, caption?, width_in?) · `pagebreak`.
Named styles, margins and spacing are fixed by the template — you only supply content.
**Illustrations:** create the image files first with the `image_generate` tool (or
matplotlib/PIL for a data chart), then reference them as `image` blocks. Prefer a
continuous flow over `pagebreak` blocks — let content paginate naturally.

Build with the **`build_document`** tool (in-process; do NOT run a terminal script or
`import docx` yourself):

```
build_document(spec={...doc spec...}, out_path="/abs/path/out.docx")
```

Then run the **same `render_check` gate** on the result (`out.docx` or `out.pdf`) and
fix any flagged pages exactly as for decks. For multi-section reports, fan out the
drafting to workers the same way.

## Why this works
You never guess pixels (templates own layout), the slow drafting is parallel and
cheap (Flash workers), and nothing ships until it has been *seen* (the vision gate).
Decks come out clean, fast, and for a few cents.
