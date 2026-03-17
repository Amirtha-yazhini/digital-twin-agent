# agent/analyzers/diff_fetcher.py
import requests
import os


class GitLabDiffFetcher:
    def __init__(self):
        self.token = os.getenv("GITLAB_TOKEN")
        self.base_url = os.getenv("CI_SERVER_URL", "https://gitlab.com") + "/api/v4"
        self.headers = {"PRIVATE-TOKEN": self.token}

    def get_mr_changes(self, project_id, mr_iid):
        """Fetch actual raw code diffs from the MR"""
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}/changes"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json()

        changes = []
        for change in data.get("changes", []):
            changes.append({
                "file": change["new_path"],
                "old_path": change.get("old_path", change["new_path"]),
                "diff": change["diff"],
                "new_file": change.get("new_file", False),
                "deleted_file": change.get("deleted_file", False),
                "renamed_file": change.get("renamed_file", False),
            })

        return changes

    def get_mr_metadata(self, project_id, mr_iid):
        """Get MR title, description, author, branch info"""
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{mr_iid}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json()

        return {
            "title": data["title"],
            "description": data.get("description", "") or "",
            "author": data["author"]["username"],
            "author_name": data["author"]["name"],
            "source_branch": data["source_branch"],
            "target_branch": data["target_branch"],
            "mr_url": data["web_url"],
            "created_at": data["created_at"],
        }

    def get_file_content(self, project_id, file_path, ref="main"):
        """Fetch full file content for deeper context (optional)"""
        import base64
        url = f"{self.base_url}/projects/{project_id}/repository/files/{requests.utils.quote(file_path, safe='')}"
        response = requests.get(url, headers=self.headers, params={"ref": ref})
        if response.status_code == 200:
            content = base64.b64decode(response.json()["content"]).decode("utf-8")
            return content
        return None