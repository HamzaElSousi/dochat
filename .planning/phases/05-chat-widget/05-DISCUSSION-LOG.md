# Phase 5: Chat Widget - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-09
**Phase:** 5-Chat Widget
**Areas discussed:** Panel visual design, Follow-up chip source, Session storage strategy, Script delivery + DocChatConfig

---

## Panel Visual Design

### Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed corner panel | 380×560px desktop, full-screen mobile ≤480px, anchored bottom-right | ✓ |
| Slide-in side drawer | Panel slides from right edge, overlays page content | |
| Floating bubble | Grows as messages accumulate, no fixed height | |

**User's choice:** Fixed corner panel (recommended)
**Notes:** Standard chatbot pattern — immediately familiar to visitors.

---

### Header bar

| Option | Description | Selected |
|--------|-------------|----------|
| Logo + title + close | Configurable logo, title text, × close button | ✓ |
| Title + close only | No logo in header | |
| Minimal — close only | Just the × button, max content space | |

**User's choice:** Logo + title + close (recommended)

---

### Message style

| Option | Description | Selected |
|--------|-------------|----------|
| Bubbles — left/right aligned | Visitor right (colored), bot left (neutral) | ✓ |
| Full-width rows | Each message spans full width with "You:" / "DocChat:" label | |
| You decide | Leave to Claude | |

**User's choice:** Bubbles — left/right aligned (recommended)

---

## Follow-up Chip Source

### Where chips come from

| Option | Description | Selected |
|--------|-------------|----------|
| Backend generates them | LLM generates chips; `chips` field added to POST /chat response | ✓ |
| Frontend static suggestions | Hardcoded generic chips; no backend change | |
| Skip chips for now | Defer to v2 | |

**User's choice:** Backend generates them (recommended)
**Notes:** Requires updating `app/services/query.py` and `app/routes/chat.py` as part of Phase 5.

---

### Generation strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Same LLM call, structured prompt | LLM outputs JSON block in same call; parser extracts chips | ✓ |
| Separate LLM call | Second lightweight call; doubles latency | |
| You decide | Leave to Claude | |

**User's choice:** Same LLM call, structured prompt (recommended)

---

### Chip click behavior + parse failure

| Option | Description | Selected |
|--------|-------------|----------|
| Click auto-sends + silent fail | Click → fill + send; parse fail → chips = [] | ✓ |
| Click populates input only | Visitor must press Send manually; parse fail → silent | |
| You decide | Leave to Claude | |

**User's choice:** Click auto-sends + silent fail (recommended)

---

## Session Storage Strategy

### session_id storage

| Option | Description | Selected |
|--------|-------------|----------|
| sessionStorage | Per-tab, clears on close. Fresh session each visit. | ✓ |
| localStorage | Persists across reloads; risk of stale session | |
| In-memory only | Lost on any navigation | |

**User's choice:** sessionStorage (recommended)

---

### History persistence across navigation

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory only for history | History cleared on page load; session_id retained in sessionStorage | |
| Persist history in sessionStorage | Serialize messages; restore on reload | |
| You decide | Leave to Claude | ✓ |

**User's choice:** You decide (deferred to Claude)

---

## Script Delivery + DocChatConfig

### widget.js delivery

| Option | Description | Selected |
|--------|-------------|----------|
| Flask static route | Served at /dochat/widget.js via Flask route + .htaccess rule | |
| Static file in public_html | Apache serves directly, no Flask overhead | |
| You decide | Leave to Claude | ✓ |

**User's choice:** You decide (deferred to Claude)

---

### DocChatConfig scope

| Option | Description | Selected |
|--------|-------------|----------|
| Core 6 properties | primaryColor, logo, title, apiUrl, borderRadius, fontFamily | |
| Extend with text/bg colors | + headerBg, botBubbleColor, userBubbleColor, textColor | ✓ |
| You decide | Leave to Claude | |

**User's choice:** Extended 10-property theme object
**Notes:** User opted for full color control — headerBg, botBubbleColor, userBubbleColor, textColor on top of the core 6.

---

## Claude's Discretion

- `widget.js` delivery location (Flask static vs `public_html/dochat/`)
- In-memory vs sessionStorage for message history across same-tab navigation
- FAB icon design (standard chat bubble SVG)
- Empty state / welcome message
- Input placeholder text
- Typing indicator animation style
- Error state UX (network error / 500)
- `sessionStorage` key name for `session_id`

## Deferred Ideas

- **Streaming responses (SSE)** — v2 feature; CGI SSE behavior untested on SiteGround
- **Lead capture form in widget** — Phase 6 scope (LEADS-01 through LEADS-04)
- **Source citations below answer** — v2 (QUAL-01); `sources` field already in API
- **Answer rating (thumbs up/down)** — v2 (WIDGET-UX-02)
- **Multi-language support** — v2 (WIDGET-UX-03)
