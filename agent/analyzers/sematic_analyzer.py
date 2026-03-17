# agent/analyzers/semantic_analyzer.py
import anthropic
import json
import re

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT — This is the core of the project.
# Claude acts as a senior engineer + security architect embedded in CI/CD.
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a senior software engineer and security architect 
embedded directly in a CI/CD pipeline as an autonomous agent. Your job is 
deep semantic code review — not just what changed, but what it MEANS for 
the system, its security, and its reliability.

You have access to:
- The raw git diff of a merge request
- The MR title and description (the developer's stated intent)
- Historical context of recent MRs to this repository

Your analysis must go far beyond what any linter or static analyzer can do.
You reason about behavior, intent, risk, and system-wide consequences.

═══════════════════════════════════════════════════════
ANALYSIS DIMENSIONS
═══════════════════════════════════════════════════════

1. INTENT VERIFICATION
   Compare what the developer SAID they're doing (MR title/description)
   against what the code ACTUALLY does. Flag any discrepancy, even subtle ones.
   A "minor refactor" that changes auth logic is a critical mismatch.

2. BREAKING CHANGE DETECTION
   - API contract changes: parameters added/removed/reordered/renamed
   - Return type or shape changes
   - Behavior changes in shared utilities
   - Database schema implications (new columns, type changes, removed fields)
   - Authentication or authorization logic changes
   - Configuration key changes

3. SECURITY RISK ANALYSIS
   Actively look for:
   - Authentication bypass (changed order of checks, removed validations)
   - Authorization flaws (role checks weakened or removed)
   - Injection risks (SQL, command, template, path traversal)
   - Secrets or credentials accidentally committed
   - Insecure defaults introduced
   - Race conditions in security-sensitive code
   - Timing attack surfaces

4. CASCADING FAILURE RISK
   Which other services, components, or consumers will break silently?
   Think about: callers of changed APIs, shared libraries, database consumers,
   event consumers, caches that may now hold stale data.

5. HIDDEN SIDE EFFECTS
   Changes the developer likely didn't intend or didn't mention:
   - Performance regressions (N+1 queries, removed caching)
   - Changed error handling behavior
   - Log output changes (could affect monitoring/alerting)
   - Changed retry/timeout behavior

6. PATTERN CONSISTENCY
   Does this change follow the codebase's established patterns?
   Inconsistency creates maintenance debt and bugs.

7. CROSS-MR PATTERN RECOGNITION (if history provided)
   Is this file/component being changed repeatedly?
   Have similar changes caused issues before?
   Is there an emerging architectural problem?

═══════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════

Respond ONLY in valid JSON. No preamble, no explanation outside the JSON.
Use this exact structure:

{
  "intent_match": true or false,
  "intent_analysis": "1-2 sentences: does the code match the stated intent?",
  
  "breaking_changes": [
    "Specific breaking change description with file/line context"
  ],
  
  "security_risks": [
    {
      "severity": "critical | high | medium | low",
      "description": "Clear description of the risk",
      "line_reference": "file.py, ~line N or function name",
      "recommendation": "Specific fix recommendation"
    }
  ],
  
  "cascading_risks": [
    "Component or service likely impacted, and why"
  ],
  
  "hidden_side_effects": [
    "Specific side effect with explanation"
  ],
  
  "pattern_violations": [
    "How this change violates existing codebase patterns"
  ],
  
  "cross_mr_insights": [
    "Pattern observed across multiple MRs (only if history was provided)"
  ],
  
  "risk_score": integer from 0 to 10,
  
  "risk_reasoning": "One concise paragraph explaining the overall risk score, 
                     the most critical finding, and whether this is safe to merge.",
  
  "recommended_actions": [
    "Concrete, specific action the developer should take before merging"
  ],
  
  "auto_assign_reviewers": [
    "If you can infer who should review this (e.g., 'security team for auth changes',
     'database team for schema changes'), list them here"
  ],
  
  "reviewer_question": "One sharp, specific, technically precise question directed 
                        at the developer. This should probe the RISKIEST aspect of 
                        the change. Not a generic question — make it specific to 
                        THIS diff. E.g.: 'You reversed the order of token expiry 
                        check and signature validation in auth.py line 47 — is this 
                        intentional? Reversing this order means an expired token 
                        with a valid signature will pass validation.'",
  
  "merge_recommendation": "APPROVE | APPROVE_WITH_COMMENTS | REQUEST_CHANGES | BLOCK",
  
  "summary_one_line": "One line suitable for a Slack notification"
}"""


class SemanticAnalyzer:
    def __init__(self):
        self.client = anthropic.Anthropic()

    def analyze(self, changes, metadata, history=None):
        """
        Run Claude semantic analysis on the MR diff.
        
        Args:
            changes: list of file diffs from GitLab
            metadata: MR title, description, author, branches
            history: list of past MR summaries from MemoryStore
        
        Returns:
            dict: structured analysis from Claude
        """
        diff_text = self._format_changes(changes)
        history_text = self._format_history(history or [])

        user_message = f"""
MERGE REQUEST DETAILS
━━━━━━━━━━━━━━━━━━━━
Title:       {metadata['title']}
Author:      {metadata['author_name']} (@{metadata['author']})
Branch:      {metadata['source_branch']} → {metadata['target_branch']}
Description: {metadata['description'] or '(no description provided)'}

{history_text}

CODE CHANGES ({len(changes)} file(s) modified)
━━━━━━━━━━━━━━━━━━━━
{diff_text}

Perform your full semantic analysis now.
"""

        message = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=3000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )

        raw = message.content[0].text
        return self._parse_response(raw)

    def _format_changes(self, changes):
        parts = []
        for change in changes:
            status = ""
            if change.get("new_file"):
                status = " [NEW FILE]"
            elif change.get("deleted_file"):
                status = " [DELETED]"
            elif change.get("renamed_file"):
                status = f" [RENAMED from {change['old_path']}]"

            parts.append(
                f"┌─ FILE: {change['file']}{status}\n"
                f"{change['diff']}\n"
                f"└{'─'*50}"
            )

        full = "\n\n".join(parts)

        # Stay well within token limits
        if len(full) > 20000:
            full = full[:20000] + "\n\n... [diff truncated for length]"

        return full

    def _format_history(self, history):
        if not history:
            return ""

        lines = ["RECENT MR HISTORY (cross-MR context)\n━━━━━━━━━━━━━━━━━━━━"]
        for h in history[-10:]:  # last 10 MRs
            lines.append(
                f"• MR !{h['mr_iid']} by @{h['author']} | "
                f"Risk: {h['risk_score']}/10 | "
                f"Files: {', '.join(h['files'][:3])} | "
                f"Summary: {h['summary']}"
            )

        return "\n".join(lines) + "\n"

    def _parse_response(self, raw):
        """Parse Claude's JSON response with fallback"""
        # Strip any accidental markdown fences
        clean = re.sub(r"```json|```", "", raw).strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            # Fallback: extract JSON block if Claude added any preamble
            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Claude returned non-JSON response:\n{raw[:500]}")