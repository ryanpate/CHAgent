# Landing Hero Chat Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the landing hero's static medallion with an interactive scripted Aria chat (three canned exchanges, chips, in-chat trial CTA) — pure front-end, no AI calls.

**Architecture:** Everything lives in `templates/core/landing.html`, matching the page's existing structure: markup swaps into `.lp-right`, CSS appends to the page's `<style>` block (`lp-demo-*` prefix, existing tokens), one vanilla-JS IIFE appends next to the existing `lpSetBilling` script. A Django test asserts the rendered content; JS behavior is browser-verified by the controller.

**Tech Stack:** Django template, vanilla JS, CSS (page-local `lp-*` design system).

**Spec:** `docs/superpowers/specs/2026-07-10-landing-hero-demo-design.md` — the dialogue strings in Task 1 are copied from it verbatim and must not be reworded.

## Global Constraints

- No free-text input in the demo; chips (`<button>`) only.
- `prefers-reduced-motion: reduce` → render all exchanges + finale instantly, no animation.
- Typing indicator 700ms; answers reveal in word/tag-token chunks completing within 2.5s.
- Message area: `aria-live="polite"`, `max-height: 340px; overflow-y: auto`; card `max-width: 420px`.
- The hero text column (H1, lede, CTAs, JSON-LD) must not change; only the medallion is replaced. The dove stays in the site header.
- Test command: `python3 -m pytest <path> -q` (python3, not python).
- Commit messages end with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_013HvrcrDi5Je8kWxCi55LbL`

---

### Task 1: Demo markup, CSS, JS, and content test

**Files:**
- Modify: `templates/core/landing.html` (three insertion points: `.lp-right` markup ~line 281, CSS before `</style>` ~line 255, JS inside the existing bottom `<script>` ~line 500)
- Test: `tests/test_landing_demo.py` (new)

**Interfaces:**
- Produces: element ids `lpDemo`, `lpDemoMsgs`, `lpDemoChips` (Task 2's browser checks reference them).

- [ ] **Step 1: Write the failing test**

Create `tests/test_landing_demo.py`:

```python
"""Landing hero chat demo: scripted content renders server-side."""
import pytest


@pytest.mark.django_db
def test_landing_renders_hero_demo(client):
    response = client.get('/')
    assert response.status_code == 200
    content = response.content.decode()

    # Demo container and honesty label
    assert 'id="lpDemo"' in content
    assert 'Sample data' in content

    # All three scripted questions ship in the page source
    assert "Who's on the team this Sunday?" in content
    assert 'Any follow-ups for me?' in content
    assert 'What key is Goodness of God in?' in content

    # The static medallion is gone
    assert 'lp-medallion' not in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_landing_demo.py -q`
Expected: FAIL — `id="lpDemo"` not found.

- [ ] **Step 3: Implement — markup**

In `templates/core/landing.html`, inside `<div class="lp-right">`, replace

```html
                <div class="lp-medallion"><img src="/static/aria-logo.png" alt="Aria dove logo" width="200" height="200"></div>
```

with:

```html
                <div class="lp-demo" id="lpDemo">
                    <div class="lp-demo-head">
                        <span class="lp-demo-dot" aria-hidden="true"></span>
                        <span class="lp-demo-name">Aria</span>
                        <span class="lp-demo-tag">Sample data</span>
                    </div>
                    <div class="lp-demo-msgs" id="lpDemoMsgs" aria-live="polite"></div>
                    <div class="lp-demo-chips" id="lpDemoChips"></div>
                </div>
```

- [ ] **Step 4: Implement — CSS**

Immediately before the page's `</style>` (after the existing responsive `@media` block), add:

```css
    /* Hero chat demo */
    .lp-demo { width: 100%; max-width: 420px; background: var(--card); border: 1px solid var(--border);
        border-radius: 16px; overflow: hidden; box-shadow: 0 18px 50px rgba(0,0,0,.35); }
    .lp-demo-head { display: flex; align-items: center; gap: 9px; padding: 14px 18px;
        border-bottom: 1px solid var(--inset); }
    .lp-demo-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--gold);
        box-shadow: 0 0 8px rgba(201,162,39,.8); }
    .lp-demo-name { font-weight: 700; font-size: 14px; color: var(--t1); }
    .lp-demo-tag { margin-left: auto; font-size: 11px; color: var(--t3); border: 1px solid var(--inset);
        border-radius: 999px; padding: 2px 9px; }
    .lp-demo-msgs { padding: 16px 18px; max-height: 340px; overflow-y: auto;
        display: flex; flex-direction: column; gap: 12px; }
    .lp-demo-user { align-self: flex-end; background: var(--inset); color: var(--t1);
        border-radius: 12px 12px 3px 12px; padding: 9px 13px; font-size: 14px; max-width: 85%; }
    .lp-demo-aria { align-self: flex-start; color: var(--t2); font-size: 14px; line-height: 1.55;
        max-width: 95%; }
    .lp-demo-aria strong { color: var(--t1); font-weight: 600; }
    .lp-demo-typing { align-self: flex-start; display: inline-flex; gap: 5px; padding: 6px 2px; }
    .lp-demo-typing i { width: 6px; height: 6px; border-radius: 50%; background: var(--gold);
        opacity: .35; animation: lpDemoPulse 1s infinite; }
    .lp-demo-typing i:nth-child(2) { animation-delay: .18s; }
    .lp-demo-typing i:nth-child(3) { animation-delay: .36s; }
    @keyframes lpDemoPulse { 0%,100% { opacity: .25; } 50% { opacity: 1; } }
    .lp-demo-chips { display: flex; flex-wrap: wrap; gap: 8px; padding: 0 18px 16px; }
    .lp-demo-chips:empty { padding: 0; }
    .lp-demo-chip { border: 1px solid rgba(201,162,39,.45); color: var(--gold); background: transparent;
        border-radius: 999px; padding: 7px 14px; font-size: 13px; cursor: pointer; font-family: inherit;
        transition: background .15s ease, color .15s ease; }
    .lp-demo-chip:hover { background: rgba(201,162,39,.15); }
    .lp-demo-finale { align-self: stretch; text-align: center; border-top: 1px solid var(--inset);
        margin-top: 4px; padding-top: 14px; }
    .lp-demo-finale p { color: var(--t1); font-size: 15px; margin-bottom: 10px; }
    .lp-demo-finale em { color: var(--gold); font-style: italic; }
    @media (prefers-reduced-motion: reduce) {
        .lp-demo-typing i { animation: none; opacity: .7; }
    }
```

- [ ] **Step 5: Implement — JS**

Inside the page's existing bottom `<script>` block (after the `lpSetBilling` function and its initial call), append:

```javascript
// ---- Hero chat demo (scripted; no backend, no AI calls) ----
(function () {
    var msgs = document.getElementById('lpDemoMsgs');
    var chipsEl = document.getElementById('lpDemoChips');
    if (!msgs || !chipsEl) return;

    var EXCHANGES = [
        {
            q: "Who's on the team this Sunday?",
            a: "This Sunday at Morning Main you have:<br><strong>Vocals:</strong> Sarah J., Marcus L., Elena R.<br><strong>Band:</strong> Dave (drums), Priya (keys), Tom (bass), Grace (electric)<br><strong>Tech:</strong> Kevin (FOH), Amber (lyrics)<br><br>Heads up — Tom is blocked out the following two Sundays, so you may want a backup bassist for the 19th."
        },
        {
            q: "Any follow-ups for me?",
            a: "Two things this week:<br><br>1. When you talked with <strong>Sarah</strong> after service two weeks ago, she mentioned her mom's surgery was coming up. That was last Thursday — might be a good day to check in.<br><br>2. You still have an open follow-up to send <strong>Marcus</strong> the in-ear monitor recommendation you promised him."
        },
        {
            q: "What key is Goodness of God in?",
            a: "<strong>Goodness of God</strong> is in <strong>B</strong> in your Planning Center library (85 BPM).<br><br>You last played it three weeks ago, and it's been in rotation 8 times this year — your team knows this one well."
        }
    ];
    var SIGNUP_URL = "{% url 'onboarding_signup' %}";
    var REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var TYPING_MS = 700;
    var REVEAL_MS = 2500;
    var TICK_MS = 35;
    var pending = [1, 2];  // exchange indexes not yet played (0 auto-plays)

    function make(tag, cls, html) {
        var node = document.createElement(tag);
        node.className = cls;
        if (html) node.innerHTML = html;
        return node;
    }

    function scrollBottom() { msgs.scrollTop = msgs.scrollHeight; }

    function renderChips() {
        chipsEl.innerHTML = '';
        pending.forEach(function (idx) {
            var chip = make('button', 'lp-demo-chip', EXCHANGES[idx].q);
            chip.type = 'button';
            chip.addEventListener('click', function () {
                pending = pending.filter(function (p) { return p !== idx; });
                chipsEl.innerHTML = '';
                play(idx);
            });
            chipsEl.appendChild(chip);
        });
    }

    function renderFinale() {
        var finale = make('div', 'lp-demo-finale',
            '<p>Ask Aria about <em>your</em> team.</p>' +
            '<a class="lp-btn lp-btn-gold lp-btn-md" href="' + SIGNUP_URL + '">Start your free trial</a>');
        msgs.appendChild(finale);
        scrollBottom();
    }

    function afterExchange() {
        if (pending.length === 0) {
            chipsEl.innerHTML = '';
            renderFinale();
        } else {
            renderChips();
        }
    }

    function revealAnswer(answerHtml, done) {
        var bubble = make('div', 'lp-demo-aria', '');
        msgs.appendChild(bubble);
        var tokens = answerHtml.split(/(<[^>]+>|\s+)/).filter(function (t) { return t !== ''; });
        var perTick = Math.max(1, Math.ceil(tokens.length / (REVEAL_MS / TICK_MS)));
        var shown = 0;
        var timer = setInterval(function () {
            shown = Math.min(tokens.length, shown + perTick);
            bubble.innerHTML = tokens.slice(0, shown).join('');
            scrollBottom();
            if (shown >= tokens.length) {
                clearInterval(timer);
                done();
            }
        }, TICK_MS);
    }

    function play(idx) {
        var ex = EXCHANGES[idx];
        msgs.appendChild(make('div', 'lp-demo-user', ex.q));
        scrollBottom();
        if (REDUCED) {
            msgs.appendChild(make('div', 'lp-demo-aria', ex.a));
            scrollBottom();
            afterExchange();
            return;
        }
        var typing = make('div', 'lp-demo-typing', '<i></i><i></i><i></i>');
        msgs.appendChild(typing);
        scrollBottom();
        setTimeout(function () {
            typing.remove();
            revealAnswer(ex.a, afterExchange);
        }, TYPING_MS);
    }

    if (REDUCED) {
        // Render everything instantly, fully expanded.
        pending = [];
        for (var i = 0; i < EXCHANGES.length; i++) play(i);
    } else {
        play(0);
    }
})();
```

Note: the question strings use double-quoted JS strings (they contain apostrophes). The `{% url %}` tag renders server-side because this script is inline in the Django template.

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_landing_demo.py tests/test_seo.py -q`
Expected: all pass (test_seo covers other landing content that must not have broken).

- [ ] **Step 7: Commit**

```bash
git add templates/core/landing.html tests/test_landing_demo.py
git commit -m "feat: interactive scripted Aria chat demo in landing hero"
```

---

### Task 2: Browser verification (controller-executed)

**Files:** none expected (fixes, if any, go to `templates/core/landing.html`).

This task is performed by the controller in-session with the Chrome tools against a local dev server (`DEBUG=True ALLOWED_HOSTS=localhost,127.0.0.1 python3 manage.py runserver`), not dispatched to a subagent.

- [ ] **Step 1:** Load `http://127.0.0.1:8000/` — exchange 1 auto-plays (user bubble → pulsing dots → answer types out ≤ ~3s), two chips render after it.
- [ ] **Step 2:** Click each chip — its exchange plays, chip disappears; after the third exchange the finale renders with "Ask Aria about *your* team." and a gold "Start your free trial" button whose href is `/signup/`.
- [ ] **Step 3:** DevTools → emulate `prefers-reduced-motion: reduce`, reload — all three exchanges + finale render instantly.
- [ ] **Step 4:** Narrow viewport to ~390px — demo sits below the hero CTA, no horizontal scroll, no stray divider line from `.lp-right::before`.
- [ ] **Step 5:** Console has no errors from the demo script.
- [ ] **Step 6:** Any defect found → fix in `templates/core/landing.html`, re-run `python3 -m pytest tests/test_landing_demo.py -q`, re-verify in browser, commit the fix.

---

### Task 3: Ship

- [ ] **Step 1:** Full suite: `python3 -m pytest tests/ -q` — green (889+ expected: 888 + 1 new).
- [ ] **Step 2:** After user confirms shipping: merge to `main`, push (deploys to aria.church via Railway).
- [ ] **Step 3:** Post-deploy smoke: load https://aria.church/ in incognito, confirm the demo auto-plays and chips work in production.
