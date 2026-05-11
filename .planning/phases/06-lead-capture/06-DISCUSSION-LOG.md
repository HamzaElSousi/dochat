# Phase 6: Lead Capture - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-10
**Phase:** 6-Lead Capture
**Areas discussed:** Form trigger conditions, Widget UX — form appearance, Email delivery method, Book-a-call URL config

---

## Form Trigger Conditions

| Option | Description | Selected |
|--------|-------------|----------|
| No relevant docs only | Only show form when similarity threshold isn't met — technical errors excluded | |
| All fallbacks | Show form for any `fallback: true` response — simpler, no type distinction | ✓ |
| You decide | Claude picks the most sensible option | |

**User's choice:** All fallbacks
**Notes:** Widget treats all `fallback: true` responses identically — no need to distinguish between similarity-gate miss, embedding failure, or LLM failure.

---

### Follow-up: Form placement

| Option | Description | Selected |
|--------|-------------|----------|
| Replace it | Form IS the response — cleaner UX, fallback text becomes form heading | ✓ |
| Below the message | Show fallback text first, then append form below | |
| You decide | Claude picks based on existing widget layout | |

**User's choice:** Replace it

---

### Follow-up: Re-showing form on subsequent fallbacks

| Option | Description | Selected |
|--------|-------------|----------|
| Show fallback text only | Don't re-prompt after first submission — track boolean in widget state | |
| Show the form again | Always show form on fallback regardless of prior submission | |
| You decide | Claude picks the most sensible option | ✓ |

**User's choice:** You decide (Claude discretion)
**Notes:** Claude chose "show fallback text only after first submission" — cleaner UX, simple `_leadSubmitted` boolean in widget state.

---

## Widget UX — Form Appearance

| Option | Description | Selected |
|--------|-------------|----------|
| Name + Email only | Matches existing leads table schema — question auto-captured | |
| Name + Email + Phone | Adds phone field — requires schema migration | ✓ |
| Email only | Lowest friction — loses name for personalization | |

**User's choice:** Name + Email + Phone
**Notes:** Requires adding `phone TEXT` column to the `leads` table via schema migration.

---

### Follow-up: Post-submission widget state

| Option | Description | Selected |
|--------|-------------|----------|
| Thank-you message + Book-a-call CTA button | Confirmation + prominent CTA — clean conversion flow | ✓ |
| Thank-you message only | Confirmation only — no CTA | |
| CTA button only | Skip thank-you — abrupt transition | |

**User's choice:** Thank-you message + Book-a-call CTA button

---

## Email Delivery Method

| Option | Description | Selected |
|--------|-------------|----------|
| Python smtplib via SiteGround SMTP | Standard SMTP — credentials in .env, reliable, testable | ✓ |
| subprocess sendmail | Unix sendmail binary — no credentials, harder to test | |
| Skip email for v1 | Admin checks leads view manually | |

**User's choice:** Python smtplib via SiteGround SMTP
**Notes:** Credentials via `.env`: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ADMIN_EMAIL. Email sent synchronously; failure is non-fatal (lead still saved).

---

### Follow-up: Email body content

| Option | Description | Selected |
|--------|-------------|----------|
| Name, email, phone, question, timestamp | Full lead details — admin can act immediately | ✓ |
| Just a link to admin leads page | Short email, admin must log in to see details | |
| You decide | Claude picks the most useful format | |

**User's choice:** Name, email, phone, question, timestamp

---

## Book-a-Call URL Config

| Option | Description | Selected |
|--------|-------------|----------|
| In the `<script>` embed tag | DocChatConfig property — zero backend change | |
| Admin UI setting | Stored in DB, fetched via API — more flexible | ✓ |
| Environment variable | .env on server — friction for site owner | |

**User's choice:** Admin UI setting

---

### Follow-up: Where in Admin UI

| Option | Description | Selected |
|--------|-------------|----------|
| New Settings tab in admin nav | Dedicated tab alongside Docs and Leads | ✓ |
| Top of the Leads page | Inline with leads management — no new tab | |

**User's choice:** New Settings tab in admin nav
**Notes:** `settings` table (key-value), `GET /dochat/admin/settings` and `POST /dochat/admin/settings` routes. Widget fetches via `GET /dochat/api/settings`.

---

## Claude's Discretion

- **Subsequent fallback behavior** — After lead form submission, subsequent `fallback: true` responses show only the FALLBACK_MESSAGE text (not the form again). Claude chose this to avoid re-prompting the visitor; implemented via `_leadSubmitted` boolean in widget JS state.

## Deferred Ideas

- CRM integration (HubSpot, Salesforce) — post-v1
- HTML/styled email templates — plain text for v1
- Admin reply-to-lead from within admin UI — post-v1
- Spam / CAPTCHA protection on the lead form — post-v1
- Lead conversion analytics — post-v1
