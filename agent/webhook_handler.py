# agent/webhook_handler.py
"""
Webhook Handler

GitLab can call this endpoint whenever someone comments on an MR.
This enables the Socratic dialogue loop:

  Claude asks question → Developer replies → Claude evaluates → loop

Setup in GitLab:
  Settings → Webhooks → Add webhook
  URL: https://your-server/webhook
  Trigger: Comments
"""
from flask import Flask, request, jsonify
import os
import json

from integrations.socratic_dialogue import SocraticDialogue

app = Flask(__name__)

# In production, store these in Redis or a database
# For the hackathon, use a simple JSON file
PENDING_QUESTIONS_FILE = "/tmp/pending_questions.json"


def load_pending():
    if os.path.exists(PENDING_QUESTIONS_FILE):
        with open(PENDING_QUESTIONS_FILE) as f:
            return json.load(f)
    return {}


def save_pending(data):
    with open(PENDING_QUESTIONS_FILE, "w") as f:
        json.dump(data, f, indent=2)


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """Handle GitLab webhook events"""
    data = request.json

    # Only handle note (comment) events on MRs
    if data.get("object_kind") != "note":
        return jsonify({"status": "ignored"}), 200

    object_attrs = data.get("object_attributes", {})
    noteable_type = object_attrs.get("noteable_type")

    if noteable_type != "MergeRequest":
        return jsonify({"status": "ignored"}), 200

    author = data.get("user", {}).get("username", "")
    note_body = object_attrs.get("note", "")
    discussion_id = object_attrs.get("discussion_id")
    mr_iid = data.get("merge_request", {}).get("iid")
    project_id = data.get("project", {}).get("id")

    # Ignore notes from the bot itself
    bot_username = os.getenv("GITLAB_BOT_USERNAME", "digital-twin-bot")
    if author == bot_username:
        return jsonify({"status": "ignored - own note"}), 200

    # Check if this is a reply to one of our Socratic questions
    pending = load_pending()
    key = f"{project_id}:{mr_iid}:{discussion_id}"

    if key in pending:
        # Developer has replied to Claude's question!
        question_context = pending[key]

        socratic = SocraticDialogue()
        evaluation = socratic.follow_up_analysis(
            project_id=str(project_id),
            mr_iid=str(mr_iid),
            discussion_id=discussion_id,
            original_question=question_context["question"],
            developer_answer=note_body,
            original_analysis=question_context["analysis"]
        )

        # Remove from pending after handling
        del pending[key]
        save_pending(pending)

        return jsonify({
            "status": "processed",
            "satisfactory": evaluation["answer_satisfactory"]
        }), 200

    return jsonify({"status": "no pending question for this thread"}), 200


@app.route("/register_question", methods=["POST"])
def register_question():
    """
    Called by the agent after posting a Socratic question,
    to register it as pending so we can match replies later.
    """
    data = request.json
    pending = load_pending()

    key = (
        f"{data['project_id']}:{data['mr_iid']}:{data['discussion_id']}"
    )
    pending[key] = {
        "question": data["question"],
        "analysis": data["analysis"],
    }
    save_pending(pending)

    return jsonify({"status": "registered"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)