import subprocess

def get_changed_files(repo_path):

    try:
        result = subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD~1"],
            cwd=repo_path
        )

        files = result.decode().splitlines()

        return files

    except:
        return []