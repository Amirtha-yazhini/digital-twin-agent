# agent/analyzers/memory_store.py
"""
Cross-MR Memory Store — Feature 4

Persists analysis history across merge requests so Claude can detect
patterns like: "This is the 4th time auth_service was changed this week
and each time risk score was > 7."

Storage: JSON file committed to a dedicated branch, or local file 
in CI artifacts. For production use, swap _load/_save for Redis or 
a database.
"""
import json
import os
import requests
import base64
from datetime import datetime


class MemoryStore:
    def __init__(self, project_id):
        self.project_id = project_id
        self.token = os.getenv("GITLAB_TOKEN")
        self.base_url = os.getenv("CI_SERVER_URL", "https://gitlab.com") + "/api/v4"
        self.headers = {"PRIVATE-TOKEN": self.token}
        self.memory_file = "/tmp/digital_twin_memory.json"
        self._history = None

    # ── Public API ────────────────────────────────────────────────

    def get_history(self):
        """Load past MR analysis records"""
        if self._history is None:
            self._history = self._load()
        return self._history

    def save_mr(self, mr_iid, analysis, metadata, changes):
        """Save this MR's analysis for future cross-MR context"""
        history = self.get_history()

        record = {
            "mr_iid": mr_iid,
            "author": metadata["author"],
            "title": metadata["title"],
            "files": [c["file"] for c in changes],
            "risk_score": analysis["risk_score"],
            "summary": analysis.get("summary_one_line", ""),
            "breaking_changes": analysis.get("breaking_changes", []),
            "security_risks": [
                r["severity"] for r in analysis.get("security_risks", [])
            ],
            "merge_recommendation": analysis.get("merge_recommendation", ""),
            "timestamp": datetime.utcnow().isoformat(),
        }

        history.append(record)

        # Keep last 50 MRs to avoid bloat
        if len(history) > 50:
            history = history[-50:]

        self._history = history
        self._save(history)

    def get_pattern_summary(self):
        """
        Generate a human-readable pattern summary across MRs.
        Used for the cross-MR insight section.
        """
        history = self.get_history()
        if not history:
            return None

        # Count high-risk MRs
        high_risk = [h for h in history if h["risk_score"] >= 7]

        # Find repeatedly-changed files
        file_counts = {}
        for h in history:
            for f in h["files"]:
                file_counts[f] = file_counts.get(f, 0) + 1

        hotspots = [f for f, count in file_counts.items() if count >= 3]

        # Find authors with recurring high-risk MRs
        author_risk = {}
        for h in history:
            if h["risk_score"] >= 7:
                author_risk[h["author"]] = author_risk.get(h["author"], 0) + 1

        return {
            "total_mrs": len(history),
            "high_risk_count": len(high_risk),
            "hotspot_files": hotspots,
            "high_risk_authors": author_risk,
        }

    # ── Storage backend ───────────────────────────────────────────

    def _load(self):
        """
        Load history. Tries GitLab repo storage first, falls back to local file.
        In CI, we use a GitLab repository file on a dedicated branch so memory
        persists across pipeline runs.
        """
        # Try GitLab repo file first (persistent across CI runs)
        gitlab_data = self._load_from_gitlab()
        if gitlab_data is not None:
            return gitlab_data

        # Fall back to local file (useful for local dev/testing)
        if os.path.exists(self.memory_file):
            with open(self.memory_file, "r") as f:
                return json.load(f)

        return []

    def _save(self, history):
        """Save history to both local file and GitLab repo"""
        # Always save locally
        with open(self.memory_file, "w") as f:
            json.dump(history, f, indent=2)

        # Try to persist to GitLab repo (so it survives across CI runs)
        self._save_to_gitlab(history)

    def _load_from_gitlab(self):
        """Load memory file from a dedicated branch in the repo"""
        try:
            url = (
                f"{self.base_url}/projects/{self.project_id}"
                f"/repository/files/digital_twin_memory.json"
            )
            response = requests.get(
                url,
                headers=self.headers,
                params={"ref": "digital-twin-memory"},
                timeout=5
            )
            if response.status_code == 200:
                content = base64.b64decode(
                    response.json()["content"]
                ).decode("utf-8")
                return json.loads(content)
        except Exception:
            pass
        return None

    def _save_to_gitlab(self, history):
        """Persist memory file to a dedicated branch in the repo"""
        try:
            content = base64.b64encode(
                json.dumps(history, indent=2).encode("utf-8")
            ).decode("utf-8")

            url = (
                f"{self.base_url}/projects/{self.project_id}"
                f"/repository/files/digital_twin_memory.json"
            )

            # Try update first, then create
            for method in ("put", "post"):
                response = getattr(requests, method)(
                    url,
                    headers=self.headers,
                    json={
                        "branch": "digital-twin-memory",
                        "content": content,
                        "encoding": "base64",
                        "commit_message": "chore: update digital twin memory",
                    },
                    timeout=10
                )
                if response.status_code in (200, 201):
                    break

        except Exception as e:
            # Non-fatal — memory just won't persist across runs
            print(f"[memory] Could not save to GitLab: {e}")