# agent/integrations/socratic_dialogue.py
"""
Socratic Dialogue — Feature 3 (The "wow" moment)

Instead of just reporting, Claude opens a dialogue in the MR thread.
It asks a sharp, targeted question and then LISTENS for the developer's
response. If the developer replies, the next pipeline run (or a webhook)
can trigger a follow-up.

This makes Claude behave like a senior engineer in a code review, not a bot.

Flow:
  1. Claude posts a targeted question as an MR thread note
  2. Developer replies in the thread
  3. (Optional) Webhook triggers follow_up_analysis() with developer's answer
  4. Claude evaluates the answer and either approves or escalates
"""
import anthropic
import requests
import os
import json
import re

FOLLOWUP_SYSTEM_PROMPT = """You are a senior engineer reviewing a developer's 
response to a code review question. You previously flagged a risk in their 
merge request and asked them a specific question. Now they have responded.

Your job:
1. Evaluate whether their answer adequately addresses the risk
2. If satisfactory: provide a brief approval note and suggest approval
3. If unsatisfactory or evasive: explain specifically what's still missing
4. If their answer reveals a NEW risk you hadn't considered: flag it

Be direct, technical, and specific. Not adversarial — constructive.

Respond in JSON:
{
  "answer_satisfactory": true or false,
  "evaluation": "Your assessment of their answer in 2-3 sentences",
  "remaining_concerns": ["Any concerns not addressed by their answer"],
  "follow_up_question": "A follow-up question if needed, or null",
  "updated_recommendation": "APPROVE | APPROVE_WITH_COMMENTS | REQUEST_CHANGES | BLOCK"
}"""


class SocraticDialogue:
    def __init__(self):
        self.token = os.getenv("GITLAB_TOKEN")
        self.base_url = os.getenv("CI_SERVER_URL", "https://gitlab.com") + "/api/v4"
        self.headers = {"PRIVATE-TOKEN": self.token}
        self.client = anthropic.Anthropic()

    def post_question(self, project_id, mr_iid, analysis, metadata):
        """
        Post Claude's Socratic question as a dedicated MR thread.
        This is separate from the main report — it invites dialogue.
        """
        question = analysis.get("reviewer_question", "")
        if not question:
            return

        risk = analysis["risk_score"]
        author = metadata["author"]

        # Craft the question with full context so it reads like
        # a senior engineer wrote it, not a bot
        comment = self._format_question(
            question, risk, author, analysis
        )

        # Post as a new thread (discussion) not just a note
        url = (
            f"{self.base_url}/projects/{project_id}"
            f"/merge_requests/{mr_iid}/discussions"
        )

        response = requests.post(
            url,
            headers=self.headers,
            json={"body": comment}
        )

        return response.json() if response.status_code == 201 else None

    def follow_up_analysis(
        self, project_id, mr_iid, discussion_id,
        original_question, developer_answer, original_analysis
    ):
        """
        Called when a developer replies to Claude's question.
        Claude evaluates the answer and responds in the thread.
        
        This can be triggered by a GitLab webhook on note creation.
        """
        message = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1000,
            system=FOLLOWUP_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"""
Original risk context:
- Risk Score: {original_analysis['risk_score']}/10
- Risk reasoning: {original_analysis.get('risk_reasoning', '')}

My question to the developer:
{original_question}

Developer's response:
{developer_answer}

Evaluate their response.
"""
            }]
        )

        raw = message.content[0].text
        clean = re.sub(r"```json|```", "", raw).strip()

        try:
            evaluation = json.loads(clean)
        except json.JSONDecodeError:
            evaluation = {
                "answer_satisfactory": False,
                "evaluation": raw,
                "remaining_concerns": [],
                "follow_up_question": None,
                "updated_recommendation": "REQUEST_CHANGES"
            }

        # Post Claude's follow-up in the same thread
        follow_up_comment = self._format_followup(evaluation)

        url = (
            f"{self.base_url}/projects/{project_id}"
            f"/merge_requests/{mr_iid}/discussions/{discussion_id}/notes"
        )

        requests.post(
            url,
            headers=self.headers,
            json={"body": follow_up_comment}
        )

        return evaluation

    def _format_question(self, question, risk, author, analysis):
        """
        Format the Socratic question to read like a thoughtful senior 
        engineer, not a bot report.
        """
        context_lines = []

        # Add the most critical finding as context for the question
        sec_risks = analysis.get("security_risks", [])
        critical = [r for r in sec_risks if r["severity"] == "critical"]
        if critical:
            context_lines.append(
                f"I noticed a potential **{critical[0]['severity']} security concern** "
                f"in this change: {critical[0]['description']}"
            )
        elif analysis.get("breaking_changes"):
            context_lines.append(
                f"This change appears to introduce a **breaking change**: "
                f"{analysis['breaking_changes'][0]}"
            )

        context_para = (
            "\n".join(context_lines) + "\n\n" if context_lines else ""
        )

        return f"""### 💬 Code Review — Question for @{author}

{context_para}**Question:**
> {question}

*I'm asking because this is the riskiest aspect of this change "
(Risk Score: {risk}/10). Your answer will help determine if this "
is safe to merge.*

*— Digital Twin Agent (powered by Claude)*"""

    def _format_followup(self, evaluation):
        """Format Claude's follow-up response to developer's answer"""
        if evaluation["answer_satisfactory"]:
            icon = "✅"
            heading = "Answer accepted"
        else:
            icon = "🔄"
            heading = "Further clarification needed"

        comment = f"### {icon} {heading}\n\n{evaluation['evaluation']}\n"

        if evaluation.get("remaining_concerns"):
            comment += "\n**Remaining concerns:**\n"
            comment += "\n".join(
                f"- {c}" for c in evaluation["remaining_concerns"]
            ) + "\n"

        if evaluation.get("follow_up_question"):
            comment += (
                f"\n**Follow-up question:**\n"
                f"> {evaluation['follow_up_question']}\n"
            )

        comment += (
            f"\n**Updated recommendation:** "
            f"`{evaluation['updated_recommendation']}`"
        )

        return comment