# Developer Token Setup Guide

> Required reading before you can use `google-ads-mcp` against any Google Ads account.

This guide walks through obtaining a Google Ads API developer token — the credential that authorizes your MCP server to make API calls. Each user runs their own copy of `google-ads-mcp` with their own developer token; there is no shared-token model.

## Who needs a developer token?

Every user of `google-ads-mcp`. Google requires API callers to identify themselves with a developer token issued through an approval process. This is separate from the OAuth2 credentials (covered in [issue #3](https://github.com/matheusslg/google-ads-mcp/issues/3) once that work lands).

## Prerequisites

- A **Google Ads manager account** (also called MCC — My Client Center). Not a regular advertiser account. Not a test account.
  - Free to create. From `https://ads.google.com/` → Tools → Account Access → Create manager account.
- A monitored email inbox — Google emails approval / rejection / follow-up requests here.
- A primary website URL for your business or project.
- An idea of what you'll use the token for, expressed in 1–2 paragraphs.

## Access tiers

Google offers four access tiers for the Ads API:

| Tier | Production access? | Test account access? | Daily op limit | Approval time |
|---|---|---|---|---|
| **Test Account** | No | Yes | 15,000 | Granted on token creation |
| **Explorer** | Limited | Yes | 2,880 production / 15,000 test | Sometimes granted automatically |
| **Basic** | Yes | Yes | 15,000 | ~3 business days |
| **Standard** | Yes (unlimited) | Yes | Unlimited | ~10 business days |

**For most users of `google-ads-mcp`, Basic Access is the right target.** Test Account works for development against synthetic data; Basic unlocks your real Google Ads account.

## Applying for Basic Access

### Step 1: Sign in to your manager account

Navigate to https://ads.google.com/aw/apicenter from your Google Ads manager account.

### Step 2: Verify the API Contact Email

In the API Center, click your manager account → confirm the **API Contact Email** is a real, monitored inbox. Google sends approval emails here. Update if needed.

### Step 3: Click "Apply for Basic Access"

In the API Center, click the dropdown next to your access level → **Apply for Basic Access** (in Portuguese: *Solicitar acesso básico*).

### Step 4: Fill the application form

The form has 12 questions. Here's what each one wants and how to answer:

**Field 1 — API contact email is accurate** ✅ Check the box.

**Field 2 — MCC ID** Format `XXX-XXX-XXXX`. Visible at the top-right of `ads.google.com` when signed into your manager account.

**Field 3 — Contact email** Your monitored email. Google's hint says "company domain preferred" — `you@yourdomain.com` scores marginally better than gmail, but gmail is accepted especially for individual developers.

**Field 4 — Ongoing Google relationship?** `No` unless you actually have a Google partnerships / account-manager contact.

**Field 5 — Company URL** Your primary business website. For individual developers, a GitHub profile URL (e.g. `https://github.com/yourusername`) is accepted. Do not use placeholder domains.

**Field 6 — Business model and how you use Google Ads** The most important field. Aim for 3–4 paragraphs covering:

- What your business does (or that you're an individual developer)
- How you use Google Ads (drive traffic, lead-gen, etc.)
- What your tool does — describe the actual workflow, not just "API access"
- Volume estimate (under 15,000 ops/day for Basic)
- Safety / data handling — especially important for tools that touch mutations

Example (small business + OSS tool):

> [Company name] ([URL]) is a [business type] that runs Google Ads campaigns to drive [traffic / leads / customers]. We are using `google-ads-mcp` (https://github.com/matheusslg/google-ads-mcp), an open-source Model Context Protocol server that surfaces Google Ads operations to AI assistants through workflow-shaped tools — account-health audits, performance summaries with period-over-period deltas, search-terms triage, and guardrailed mutation tools (campaign pause/enable, budget updates with caps, bid updates, negative-keyword additions).
>
> The tool runs locally on our machines and connects to our Google Ads account using our own developer token; there is no hosted backend and no data leaves our environment. Every mutation tool is safe-by-construction: it accepts a `dry_run: bool = False` parameter and at least one numeric guardrail (`max_increase_percent`, `absolute_cap`, or `max_bid_cap`), refusing any operation whose computed delta exceeds the cap. Default cap is `max_increase_percent: 50` when no explicit guardrail is supplied.
>
> Expected API usage: low-volume dev/test/production use for our own ad operations, well under the 15,000 operations/day Basic Access limit.

**Field 7 — Design documentation (.pdf, .doc, or .rtf upload)** Upload [PRD.md](../PRD.md) converted to PDF. Easiest path: open the file on GitHub in your browser → Cmd+P → "Save as PDF". The PRD documents the safety model, output-shape contract, and non-goals — all positive signals to reviewers.

**Field 8 — Who has access to the tool?**

- `Internal users` — only you and your employees use it
- `External users - use by general public or clients` — published OSS, anyone can install
- `Both internal and external users` — both (the typical answer for `google-ads-mcp`-derived deployments)

**Field 9 — Use token with someone else's tool?** `No` — you're using your token in `google-ads-mcp`, which you control.

**Field 10 — App Conversion / Remarketing API?** `No` — `google-ads-mcp` does not use these APIs.

**Field 11 — Campaign types your tool supports** Comma-separated list. For typical small-business use: `Search, Display`. Add other types (`Shopping`, `Performance Max`, `Video`, `Demand Gen`) only if you actually run those campaign types AND the tool's mutation surface handles them cleanly. As of v1, Performance Max is out of scope.

**Field 12 — Capabilities your tool provides** Check exactly these two:

- ✅ **Campaign Management** — covers `pause_campaign`, `enable_campaign`, `update_campaign_budget`, `update_keyword_bid`, `add_negative_keywords`
- ✅ **Reporting** — covers `get_performance`, `list_search_terms`, `summarize_performance`, `audit_account_health`

Do NOT check:

- ❌ Account Creation (out of PRD scope)
- ❌ Account Management (refers to MCC hierarchy operations, out of scope)
- ❌ Campaign Creation (PRD routes campaign creation through `draft_campaign_csv` + human review, not direct API mutation)
- ❌ Keyword Planning Services (the tool uses the search-terms report, not `KeywordPlanIdeaService`)

**Acknowledgments** Check both.

### Step 5: Submit

You'll see a confirmation screen ("Your email has been sent") and receive a confirmation email at your API contact email shortly after.

## What to expect after submission

- Google sends an automated receipt to your API contact email immediately.
- Initial decision typically arrives within **~3 business days** (per Google's confirmation screen).
- The compliance team may email back with clarifying questions before deciding. Watch your inbox.

## Using the Test Account tier in the meantime

While you wait for Basic Access approval, you can fully develop and test `google-ads-mcp` against a **Test Account** under your manager account.

To create a test account:

1. Sign in to your manager account at `ads.google.com`.
2. Click *Accounts* → `+` → **Create test account**.
3. Test accounts come pre-populated with sample campaigns and ad groups; no real money, no real ads served.

Test Accounts support every read tool and every mutation tool in `google-ads-mcp` — they operate on synthetic data instead of your real campaigns. This is the setup the project itself uses for issues #1 (bootstrap), #4–#6 (read tools), and #7 (v0.1.0 release validation).

## After approval

Once you receive the approval email:

1. Return to https://ads.google.com/aw/apicenter.
2. Copy your developer token from the API Center page.
3. Run `uvx google-ads-mcp setup` — the wizard will prompt for the developer token, your `client_secrets.json` path (the OAuth 2.0 Desktop client you created in Google Cloud Console), your Manager (MCC) ID, and the default Google Ads account ID. It then runs the OAuth flow against a local browser tab and writes everything to `~/.config/google-ads-mcp/credentials.json`.

## If you're rejected

Common rejection patterns (community-gathered — Google does not publish a comprehensive list):

- **Vague use case in Field 6**: "Manage Google Ads with AI" is too generic; "Pause campaigns when CPL exceeds threshold X, with mandatory dry-run preview" is concrete and acceptable.
- **Non-functional URL in Field 5**: must resolve and look legitimate. Check that it loads in an incognito window.
- **Generic placeholder email in Field 3**: avoid `test@`, `info@`, or unmonitored aliases. A real personal or company address is better.
- **Mismatched scope in Field 12**: capabilities should match what your code actually does. Checking "Account Creation" when your code doesn't create accounts invites follow-up.
- **Unconvincing safety story for mutation-heavy tools**: Field 6 should explicitly describe guardrails, dry-run flows, or human-in-the-loop steps.

If rejected with a specific reason, address the reason directly and reapply. If rejected without specifics, contact Google's API support channel via the API Center and request clarification.

## Notes specific to `google-ads-mcp` end users

- **Each user must apply individually.** No shared-token model. You cannot use another user's token, even with consent.
- **Your developer token must match your MCC.** A developer token issued under one MCC cannot access accounts under a different MCC.
- **The token is tied to its tier.** A Test-tier token cannot access production accounts regardless of other credentials.
- **OAuth2 credentials are separate.** Each user also needs their own OAuth2 client ID + refresh token. See [issue #3](https://github.com/matheusslg/google-ads-mcp/issues/3) once the setup helper ships.

---

## This project's own application status

| Field | Value |
|---|---|
| Applicant | Cavallini Imóveis (`https://cavalliniimoveis.com.br/`) |
| Maintainer GitHub | `matheusslg` |
| Submission date | 2026-05-19 |
| Current tier | Test Account (Basic Access pending) |

Authoritative current status lives in [`progress.md`](../progress.md).
