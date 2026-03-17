# agent/integrations/mr_reporter.py
"""
MR Reporter — Feature 2 (partial)

Posts the full semantic analysis as a formatted MR comment.
Blocks the merge if risk is critical.
"""
import requests
import os


class MRReporter:
    def __init__(self):
        self.token = os.getenv("GITLAB_TOKEN")
        self.base_url = os.getenv("CI_SERVER_URL", "https://gitlab.com") + "/api/v4"
        self.headers = {"PRIVATE-TOKEN": self.token}

    def post_analysis(self, project_id, mr_iid, analysis, metadata):
        """Post the main analysis report as an MR comment"""
        comment = self._format_report(analysis, metadata)
        self._post_note(project_id, mr_iid, comment)

    def block_merge_if_critical(self, project_id, mr_iid, analysis):
        """
        Block the MR if risk score >= 8 or any critical security risk found.
        Returns True if blocked.
        """
        has_critical_security = any(
            r["severity"] == "critical"
            for r in analysis.get("security_risks", [])
        )
        should_block = (
            analysis["risk_score"] >= 8
            or has_critical_security
            or analysis.get("merge_recommendation") == "BLOCK"
        )

        if should_block:
            block_comment = (
                "## ⛔ MERGE BLOCKED — Digital Twin Agent\n\n"
                f"**Risk Score: {analysis['risk_score']}/10**\n\n"
                "This merge request has been automatically blocked due to "
                "critical risk findings.\n\n"
                "**Reasons for block:**\n"
            )

            if has_critical_security:
                for r in analysis.get("security_risks", []):
                    if r["severity"] == "critical":
                        block_comment += f"- 🔴 CRITICAL: {r['description']}\n"

            if analysis["risk_score"] >= 8:
                block_comment += (
                    f"- Risk score {analysis['risk_score']}/10 "
                    f"exceeds threshold (8/10)\n"
                )

            block_comment += (
                "\n**Required before unblocking:**\n"
                + "\n".join(
                    f"- {a}"
                    for a in analysis.get("recommended_actions", [])
                )
                + "\n\n*To override, a maintainer must manually approve.*"
            )

            self._post_note(project_id, mr_iid, block_comment)
            self._set_wip(project_id, mr_iid)

        return should_block

    def _set_wip(self, project_id, mr_iid):
        """Mark MR as Draft to prevent accidental merge"""
        url = (
            f"{self.base_url}/projects/{project_id}"
            f"/merge_requests/{mr_iid}"
        )
        # Prefix title with Draft: to block merge
        mr = requests.get(url, headers=self.headers).json()
        current_title = mr.get("title", "")
        if not current_title.startswith("Draft:"):
            requests.put(
                url,
                headers=self.headers,
                json={"title": f"Draft: {current_title}"}
            )

    def _post_note(self, project_id, mr_iid, body):
        url = (
            f"{self.base_url}/projects/{project_id}"
            f"/merge_requests/{mr_iid}/notes"
        )
        requests.post(url, headers=self.headers, json={"body": body})

    def _format_report(self, analysis, metadata):
        risk = analysis["risk_score"]

        if risk >= 8:
            risk_badge = "🔴 CRITICAL"
            risk_bar = "█████████░"
        elif risk >= 6:
            risk_badge = "🟠 HIGH"
            risk_bar = "███████░░░"
        elif risk >= 4:
            risk_badge = "🟡 MEDIUM"
            risk_bar = "█████░░░░░"
        else:
            risk_badge = "🟢 LOW"
            risk_bar = "███░░░░░░░"

        rec_emoji = {
            "APPROVE": "✅",
            "APPROVE_WITH_COMMENTS": "💬",
            "REQUEST_CHANGES": "🔄",
            "BLOCK": "⛔",
        }.get(analysis.get("merge_recommendation", ""), "❓")

        # ── Intent match section ──
        intent_icon = "✅" if analysis.get("intent_match") else "❌"
        intent_section = (
            f"**Intent Match:** {intent_icon}  \n"
            f"{analysis.get('intent_analysis', '')}\n"
        )

        # ── Security risks section ──
        sec_risks = analysis.get("security_risks", [])
        if sec_risks:
            security_section = "\n### 🔒 Security Risks\n"
            for r in sec_risks:
                sev_emoji = {
                    "critical": "🔴", "high": "🟠",
                    "medium": "🟡", "low": "🔵"
                }.get(r["severity"], "⚪")
                security_section += (
                    f"- {sev_emoji} **[{r['severity'].upper()}]** "
                    f"{r['description']}  \n"
                    f"  📍 `{r.get('line_reference', 'see diff')}`  \n"
                    f"  💡 _{r.get('recommendation', '')}_\n"
                )
        else:
            security_section = "\n### 🔒 Security Risks\n✅ None detected\n"

        # ── Breaking changes section ──
        breaking = analysis.get("breaking_changes", [])
        if breaking:
            breaking_section = "\n### ⚠️ Breaking Changes\n"
            breaking_section += "\n".join(f"- {b}" for b in breaking) + "\n"
        else:
            breaking_section = "\n### ⚠️ Breaking Changes\n✅ None detected\n"

        # ── Cascading risks ──
        cascading = analysis.get("cascading_risks", [])
        cascade_section = "\n### 🌊 Cascading Impact\n"
        if cascading:
            cascade_section += "\n".join(f"- {c}" for c in cascading) + "\n"
        else:
            cascade_section += "✅ No cascading risks detected\n"

        # ── Hidden side effects ──
        side_effects = analysis.get("hidden_side_effects", [])
        if side_effects:
            side_section = "\n### 👻 Hidden Side Effects\n"
            side_section += "\n".join(f"- {e}" for e in side_effects) + "\n"
        else:
            side_section = ""

        # ── Cross-MR insights ──
        cross_mr = analysis.get("cross_mr_insights", [])
        if cross_mr:
            cross_section = "\n### 📈 Cross-MR Pattern Insights\n"
            cross_section += "\n".join(f"- {i}" for i in cross_mr) + "\n"
        else:
            cross_section = ""

        # ── Recommended actions ──
        actions = analysis.get("recommended_actions", [])
        actions_section = "\n### ✅ Required Actions Before Merge\n"
        if actions:
            actions_section += "\n".join(
                f"- [ ] {a}" for a in actions
            ) + "\n"
        else:
            actions_section += "No actions required.\n"

        # ── Auto-assign reviewers ──
        reviewers = analysis.get("auto_assign_reviewers", [])
        reviewer_section = ""
        if reviewers:
            reviewer_section = "\n### 👥 Suggested Reviewers\n"
            reviewer_section += "\n".join(f"- {r}" for r in reviewers) + "\n"

        return (
            f"## 🤖 Digital Twin Agent — Semantic Analysis\n\n"
            f"| | |\n|---|---|\n"
            f"| **Risk Score** | `{risk}/10` {risk_bar} {risk_badge} |\n"
            f"| **Recommendation** | {rec_emoji} `{analysis.get('merge_recommendation', 'N/A')}` |\n"
            f"| **Author** | @{metadata['author']} |\n"
            f"| **Branch** | `{metadata['source_branch']}` → `{metadata['target_branch']}` |\n\n"
            f"> {analysis.get('summary_one_line', '')}\n\n"
            f"---\n\n"
            f"{intent_section}"
            f"{security_section}"
            f"{breaking_section}"
            f"{cascade_section}"
            f"{side_section}"
            f"{cross_section}"
            f"{actions_section}"
            f"{reviewer_section}"
            f"\n---\n\n"
            f"### 📊 Risk Reasoning\n"
            f"{analysis.get('risk_reasoning', '')}\n\n"
            f"---\n"
            f"<sub>🤖 Powered by Digital Twin Agent + Claude | "
            f"[View full run logs in pipeline]</sub>\n"
        )