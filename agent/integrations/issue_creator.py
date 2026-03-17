# agent/integrations/issue_creator.py
"""
Issue Creator — Feature 2

When risk score >= 6, automatically creates a GitLab issue to track
the risk. This proves the agent "takes action" — not just commenting,
but creating work items that live in the project backlog.
"""
import requests
import os
from datetime import datetime


class IssueCreator:
    def __init__(self):
        self.token = os.getenv("GITLAB_TOKEN")
        self.base_url = os.getenv("CI_SERVER_URL", "https://gitlab.com") + "/api/v4"
        self.headers = {"PRIVATE-TOKEN": self.token}

    def create_risk_issue(self, project_id, mr_iid, analysis, metadata):
        """
        Auto-create a GitLab issue for this MR's risks.
        Returns the URL of the created issue.
        """
        risk = analysis["risk_score"]
        title = self._build_title(risk, metadata)
        description = self._build_description(mr_iid, analysis, metadata)
        labels = self._build_labels(analysis)

        url = f"{self.base_url}/projects/{project_id}/issues"

        response = requests.post(
            url,
            headers=self.headers,
            json={
                "title": title,
                "description": description,
                "labels": ",".join(labels),
            }
        )

        if response.status_code == 201:
            issue = response.json()
            issue_url = issue["web_url"]
            issue_iid = issue["iid"]

            # Cross-link: comment on the MR referencing the new issue
            self._cross_link_mr(project_id, mr_iid, issue_iid, issue_url)

            return issue_url

        return None

    def _build_title(self, risk, metadata):
        if risk >= 8:
            prefix = "🔴 [CRITICAL RISK]"
        elif risk >= 6:
            prefix = "🟠 [HIGH RISK]"
        else:
            prefix = "🟡 [MEDIUM RISK]"

        return (
            f"{prefix} Digital Twin: Risk detected in "
            f"'{metadata['title'][:60]}'"
        )

    def _build_description(self, mr_iid, analysis, metadata):
        risk = analysis["risk_score"]

        # Format security risks
        sec_risks = analysis.get("security_risks", [])
        sec_lines = ""
        if sec_risks:
            sec_lines = "\n### Security Risks\n"
            for r in sec_risks:
                sec_lines += (
                    f"- **[{r['severity'].upper()}]** {r['description']}  \n"
                    f"  Fix: {r.get('recommendation', 'Review required')}\n"
                )

        # Format breaking changes
        breaking = analysis.get("breaking_changes", [])
        breaking_lines = ""
        if breaking:
            breaking_lines = "\n### Breaking Changes\n"
            breaking_lines += "\n".join(f"- {b}" for b in breaking) + "\n"

        # Format required actions as a checklist
        actions = analysis.get("recommended_actions", [])
        checklist = "\n### Required Actions\n"
        checklist += "\n".join(f"- [ ] {a}" for a in actions) + "\n"

        return f"""## Digital Twin Risk Report

**Detected in MR:** !{mr_iid} — {metadata['title']}  
**Author:** @{metadata['author']}  
**Branch:** `{metadata['source_branch']}` → `{metadata['target_branch']}`  
**Risk Score:** {risk}/10  
**Detected at:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  

---

### Summary
{analysis.get('risk_reasoning', '')}
{sec_lines}{breaking_lines}
### Cascading Impact
{chr(10).join(f'- {c}' for c in analysis.get('cascading_risks', [])) or '- None identified'}
{checklist}

---

### Reviewer Question
> {analysis.get('reviewer_question', '')}

---

*This issue was automatically created by [Digital Twin Agent](https://gitlab.com).  
Close this issue once all required actions above are completed.*
"""

    def _build_labels(self, analysis):
        labels = ["digital-twin", "automated"]

        risk = analysis["risk_score"]
        if risk >= 8:
            labels.append("risk::critical")
        elif risk >= 6:
            labels.append("risk::high")
        else:
            labels.append("risk::medium")

        if any(r["severity"] == "critical"
               for r in analysis.get("security_risks", [])):
            labels.append("security")

        if analysis.get("breaking_changes"):
            labels.append("breaking-change")

        return labels

    def _cross_link_mr(self, project_id, mr_iid, issue_iid, issue_url):
        """Add a short comment on the MR linking to the created issue"""
        url = (
            f"{self.base_url}/projects/{project_id}"
            f"/merge_requests/{mr_iid}/notes"
        )
        requests.post(
            url,
            headers=self.headers,
            json={
                "body": (
                    f"📋 **Risk tracking issue created:** #{issue_iid}  \n"
                    f"Complete the checklist in that issue before merging.\n"
                    f"{issue_url}"
                )
            }
        )