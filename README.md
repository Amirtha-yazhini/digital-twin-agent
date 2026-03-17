# Digital Twin Agent

> **Autonomous DevOps agent that reads code like a senior engineer — catching semantic risk, security flaws, and system-wide impact before deployment.**

[![GitLab CI](https://img.shields.io/badge/GitLab-CI%2FCD-orange)](https://gitlab.com)
[![Powered by Claude](https://img.shields.io/badge/Powered%20by-Claude%20(Anthropic)-blue)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## The Problem

Modern CI/CD pipelines verify that code **compiles and passes tests**. They cannot answer the question that matters most:

> **What will happen to the entire system when this change goes live?**

A "minor refactor" that reverses the order of two validation checks can create an authentication bypass. Tests pass. Linter passes. Code ships. Production breaks.

Static analyzers catch syntax. Unit tests catch regressions. **Nothing catches semantic risk** — until now.

---

## Solution

Digital Twin Agent embeds Claude directly into GitLab CI/CD as an **autonomous code review agent**. When a developer opens a merge request, the agent:

1. **Reads the actual code diff** — not just filenames, the real changes
2. **Analyzes semantic intent** — does the code do what the commit message claims?
3. **Detects security risks** — auth bypasses, injection risks, broken validation order
4. **Simulates cascading impact** — which services will break downstream?
5. **Takes action** — blocks dangerous merges, creates issues, asks targeted questions
6. **Remembers across MRs** — detects patterns like "this file has been changed 4 times this week, each with risk > 7"

---

## The Four Features

### 1. Semantic Diff Analysis (Core)
Claude reads the raw code diff and reasons about **what the change means**, not just what changed. It catches:
- Intent mismatches (commit says "refactor", code changes auth logic)
- Security risks (reversed validation order, removed permission checks)
- Breaking API contract changes
- Hidden side effects (performance regressions, changed error behavior)

### 2. Autonomous Action (Not Just Comments)
The agent doesn't just report — it **acts**:
- Automatically **blocks the MR** (sets Draft status) if risk score ≥ 8 or critical security risk detected
- **Creates a GitLab issue** with a risk checklist that must be completed before merge
- **Assigns reviewers** based on what expertise the change requires

### 3. Socratic Reviewer Dialogue
Claude posts a **targeted, technically precise question** to the developer in the MR thread — behaving like a senior engineer, not a bot:
> *"You reversed the order of token expiry check and signature validation in `validate_token()` line 47. Is this intentional? The original order prevents expired tokens from passing signature checks — reversing it means an expired token with a valid signature will successfully authenticate."*

When the developer replies, Claude evaluates their answer and either approves or escalates.

### 4. Cross-MR Memory
Claude remembers analysis history across merge requests. It detects patterns like:
- "This is the 4th change to `auth_service.py` this week — each with risk score > 7"
- "Three consecutive MRs to this component introduced breaking changes"
- "This component has become a hotspot — architectural review recommended"

---

## How It Works

```
Developer opens Merge Request
          ↓
GitLab Pipeline triggers Digital Twin Agent
          ↓
┌─────────────────────────────────────┐
│  1. Fetch raw diff from GitLab API  │
│  2. Load cross-MR memory            │
│  3. Claude semantic analysis        │
│     - Intent verification           │
│     - Security risk detection       │
│     - Breaking change detection     │
│     - Cascading impact simulation   │
│     - Cross-MR pattern recognition  │
└─────────────────────────────────────┘
          ↓
┌─────────────────────────────────────┐
│  Actions taken:                     │
│  • Post full analysis to MR         │
│  • Block MR if critical risk        │
│  • Create GitLab issue + checklist  │
│  • Post Socratic question in thread │
│  • Save to cross-MR memory          │
└─────────────────────────────────────┘
          ↓
Developer sees risk report + question
          ↓
Developer replies → Claude evaluates answer
          ↓
Merge approved or escalated
```

---

## Example Output

### MR Analysis Comment
```
🤖 Digital Twin Agent — Semantic Analysis

Risk Score: 9/10 ██████████ 🔴 CRITICAL
Recommendation: ⛔ BLOCK

Intent Match: ❌ Code does NOT match stated intent
"Commit says 'clean up logic' but reverses security-critical 
validation order in auth_service.py"

🔒 Security Risks
🔴 [CRITICAL] Token expiry bypass: swapping validation order allows 
expired tokens with valid signatures to authenticate.
📍 validate_token(), ~line 47
💡 Restore expiry check before signature verification

⚠️ Breaking Changes
- Token validation contract changed: callers depending on 
  expiry-first behavior may see different error responses

🌊 Cascading Impact
- api_gateway: all authenticated endpoints affected
- frontend: session management assumes current token behavior

✅ Required Actions Before Merge
- [ ] Restore original validation order or document why reversal is safe
- [ ] Add integration test for expired token rejection
- [ ] Security team review required
```

### Socratic Question
```
💬 Question for @developer:

You reversed the order of token expiry check and signature validation 
in validate_token (line 47). Is this intentional? The original order 
prevents expired tokens from passing signature checks — reversing it 
means an expired token with a valid signature will successfully 
authenticate.

(Risk Score: 9/10 — answering this is required before merge)
```

---

## Project Structure

```
digital-twin-agent/
│
├── agent/
│   ├── main.py                          # Orchestrator
│   │
│   ├── analyzers/
│   │   ├── diff_fetcher.py              # GitLab API — fetch raw diffs
│   │   ├── semantic_analyzer.py         # Claude — core reasoning engine
│   │   └── memory_store.py              # Cross-MR persistent memory
│   │
│   ├── integrations/
│   │   ├── mr_reporter.py               # Post report + block MR
│   │   ├── issue_creator.py             # Auto-create risk issues
│   │   └── socratic_dialogue.py         # Ask + evaluate dev responses
│   │
│   └── webhook_handler.py               # Flask server for reply webhooks
│
├── demo_repo/
│   ├── auth_service.py                  # Demo file to trigger the agent
│   └── DEMO_SCENARIO.md                 # Exact demo steps
│
├── .gitlab-ci.yml
├── requirements.txt
└── README.md
```

---

## Installation

```bash
git clone https://github.com/your-username/digital-twin-agent.git
cd digital-twin-agent
pip install -r requirements.txt
```

---

## GitLab Setup

### 1. Add CI/CD Variables
In your GitLab repo: **Settings → CI/CD → Variables**

| Variable | Value |
|---|---|
| `GITLAB_TOKEN` | Your GitLab personal access token (scopes: `api`) |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |

### 2. The pipeline runs automatically
Push code or open a merge request — the agent runs automatically via `.gitlab-ci.yml`.

### 3. (Optional) Enable Socratic dialogue webhooks
Deploy `agent/webhook_handler.py` and add a GitLab webhook:
- **Settings → Webhooks → Add webhook**
- URL: `https://your-server/webhook`
- Trigger: **Comments**

---

## Why This Matters

Digital Twin Agent transforms CI/CD from **reactive testing** to **proactive semantic intelligence**.

| | Traditional CI | Digital Twin Agent |
|---|---|---|
| Catches syntax errors | ✅ | ✅ |
| Catches test regressions | ✅ | ✅ |
| Catches semantic intent mismatches | ❌ | ✅ |
| Catches security logic flaws | ❌ | ✅ |
| Understands cascading impact | ❌ | ✅ |
| Remembers patterns across MRs | ❌ | ✅ |
| Takes autonomous action | ❌ | ✅ |
| Asks targeted questions | ❌ | ✅ |

---

## License

MIT License
