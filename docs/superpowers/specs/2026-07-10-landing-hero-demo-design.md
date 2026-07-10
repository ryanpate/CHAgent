# Landing-Page Hero Chat Demo — Design

**Date:** 2026-07-10
**Status:** Approved
**Goal:** Show Aria's core moment — asking a question and getting a real answer —
the second the landing page loads, without an account, a backend call, or AI
cost. Conversion-plan item #2 (after the card-free trial).

## Decisions (made with Ryan)

1. **Format:** interactive scripted chat replacing the static gold medallion in
   the hero's right column (`.lp-right` in `templates/core/landing.html`).
2. **Script:** three exchanges — Sunday team (auto-plays on load), volunteer
   care, song lookup. Blockouts cut (overlaps Sunday team).
3. **Implementation:** vanilla JS + CSS inline in `landing.html`, matching the
   page's existing architecture (`lp-*` style block, vanilla `lpSetBilling`
   script). No frameworks, no backend, no live AI.

## Behavior

- **Auto-play on load:** exchange 1 plays automatically — user bubble appears,
  a typing indicator (three pulsing dots) shows for 700ms, then Aria's answer
  reveals word-chunk by word-chunk so the full answer completes within 2.5s
  regardless of length. Start on DOMContentLoaded; no scroll-trigger needed
  (the hero is above the fold).
- **Chips:** after exchange 1 completes, two suggestion chips render:
  "Any follow-ups for me?" and "What key is Goodness of God in?". Clicking a
  chip plays that exchange (same user-bubble → typing → answer flow) and
  disables/removes that chip. Chips are real `<button>` elements.
- **Finale:** once all three exchanges have played, a gold CTA block renders
  inside the chat: text "Ask Aria about *your* team." with a button
  "Start your free trial" linking to `{% url 'onboarding_signup' %}`.
- **No free-text input.** Chips only — the demo must not imply a live AI
  endpoint (no backend exists for it; avoids abuse and confusion).
- **Reduced motion:** if `prefers-reduced-motion: reduce`, all three exchanges
  and the finale render instantly, fully expanded, no animation.
- **Message area:** `aria-live="polite"`, internal scroll if content exceeds
  the card (`max-height`, auto-scroll to bottom as messages append).
- **Honesty label:** card header shows a gold dot, the name "Aria", and a
  muted "Sample data" tag.

## Script (verbatim content)

Formatting note: answers may use simple line breaks and **bold** names
(rendered via `<strong>`); no markdown parser — the strings below are authored
as HTML in the JS config.

**Exchange 1 — auto-plays**
- User: `Who's on the team this Sunday?`
- Aria: `This Sunday at Morning Main you have:<br>
  <strong>Vocals:</strong> Sarah J., Marcus L., Elena R.<br>
  <strong>Band:</strong> Dave (drums), Priya (keys), Tom (bass), Grace (electric)<br>
  <strong>Tech:</strong> Kevin (FOH), Amber (lyrics)<br><br>
  Heads up — Tom is blocked out the following two Sundays, so you may want a
  backup bassist for the 19th.`

**Exchange 2 — chip: "Any follow-ups for me?"**
- User: `Any follow-ups for me?`
- Aria: `Two things this week:<br><br>
  1. When you talked with <strong>Sarah</strong> after service two weeks ago,
  she mentioned her mom's surgery was coming up. That was last Thursday —
  might be a good day to check in.<br><br>
  2. You still have an open follow-up to send <strong>Marcus</strong> the
  in-ear monitor recommendation you promised him.`

**Exchange 3 — chip: "What key is Goodness of God in?"**
- User: `What key is Goodness of God in?`
- Aria: `<strong>Goodness of God</strong> is in <strong>B</strong> in your
  Planning Center library (85 BPM).<br><br>
  You last played it three weeks ago, and it's been in rotation 8 times this
  year — your team knows this one well.`

**Finale block**
- Text: `Ask Aria about <em>your</em> team.`
- Button: `Start your free trial` → `{% url 'onboarding_signup' %}`
  (gold, `lp-btn lp-btn-gold lp-btn-md`).

## Markup & styling

- Replace `<div class="lp-medallion">…</div>` inside `.lp-right` with the demo
  card. The `.lp-right::before` divider line stays. The dove logo remains in
  the site header, and the `aria-logo.png` asset is untouched.
- New CSS appended to the page's existing `<style>` block, `lp-demo-*`
  prefixed, using existing tokens: card `background: var(--card)`,
  `border: 1px solid var(--border)`, radius ~16px; user bubbles inset
  (`var(--inset)`), right-aligned; Aria bubbles borderless left-aligned text;
  gold (`var(--gold)`) for the header dot, chip borders/hover, and typing
  dots. Card width fills the column (`max-width: 420px`), message area
  `max-height: 340px; overflow-y: auto`.
- Mobile: the existing `@media` collapse (hero grid → 1 column) places the
  demo below the CTA; it stays full-width with the same max-height. The
  `.lp-right::before` divider is already hidden/irrelevant in the collapsed
  layout — verify it doesn't render as a stray line on mobile.
- JS: one self-contained IIFE appended to the page's existing bottom
  `<script>` area; exchanges defined as a const array of
  `{question, answerHtml}`. No globals beyond what the IIFE closes over.

## Non-goals / out of scope

- No video recording (separate task, requires Ryan).
- No live-AI sandbox or backend endpoint.
- No demo on other pages (pricing, signup).
- No changes to headings, lede, CTAs, JSON-LD, or SEO copy in the hero text
  column (the medallion swap is the only hero change).

## Testing

- Django test (append to an existing landing/SEO test file or a small new
  one): GET `/` renders — assert presence of the demo container id, all three
  scripted question strings, the "Sample data" label, and absence of the
  `lp-medallion` markup.
- JS has no test infra in this repo: manual browser verification before ship —
  auto-play runs, chips play and disable, finale CTA appears and links to
  /signup/, reduced-motion path renders instantly (toggle via DevTools),
  mobile layout sane. Performed with the in-session Chrome tools.
