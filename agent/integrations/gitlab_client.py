import requests
import os

GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")

def post_comment(project_id, mr_id, message):

    url = f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests/{mr_id}/notes"

    headers = {
        "PRIVATE-TOKEN": GITLAB_TOKEN
    }

    data = {
        "body": message
    }

    requests.post(url, headers=headers, data=data)