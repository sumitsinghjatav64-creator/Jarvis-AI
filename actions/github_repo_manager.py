import os
import subprocess
import sys
from pathlib import Path
from core import confirm

_BASE_DIR = Path(__file__).resolve().parent.parent
_REPOS_DIR = _BASE_DIR / "workspace" / "repos"
_REPOS_DIR.mkdir(parents=True, exist_ok=True)

if sys.platform == "win32":
    _WIN_HIDE = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _WIN_HIDE = {}

def clone_or_update_repo(repo_url: str) -> str:
    """Clones a GitHub repository or updates it if already present."""
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    target_dir = _REPOS_DIR / repo_name

    try:
        if target_dir.exists() and (target_dir / ".git").exists():
            subprocess.run(
                ["git", "-C", str(target_dir), "pull"],
                capture_output=True, text=True, check=True, timeout=60, **_WIN_HIDE
            )
            status = f"Updated existing repo '{repo_name}'"
        else:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(target_dir)],
                capture_output=True, text=True, check=True, timeout=120, **_WIN_HIDE
            )
            status = f"Cloned new repo '{repo_name}'"

        # Summary of contents
        files = [p.relative_to(target_dir).as_posix() for p in target_dir.glob("*") if not p.name.startswith(".")]
        readme = ""
        readme_path = target_dir / "README.md"
        if readme_path.exists():
            readme = readme_path.read_text(encoding="utf-8", errors="ignore")[:1500]

        return (
            f"✅ {status} at {target_dir.as_posix()}.\n"
            f"Root Files: {', '.join(files[:15])}\n"
            f"README Overview:\n{readme or 'No README.md found.'}"
        )
    except Exception as e:
        return f"Failed to clone/pull repository '{repo_url}': {e}"

def run_repo_command(repo_name: str, command: str) -> str:
    """Runs a terminal/build/test command inside a cloned repository."""
    target_dir = _REPOS_DIR / repo_name
    if not target_dir.exists():
        return f"Repository directory '{repo_name}' not found under {_REPOS_DIR}."

    try:
        res = subprocess.run(
            command,
            cwd=str(target_dir),
            shell=True,
            capture_output=True,
            text=True,
            timeout=180,
            **_WIN_HIDE
        )
        out = (res.stdout + "\n" + res.stderr).strip()
        return f"Command exit code: {res.returncode}\nOutput:\n{out[:2500]}"
    except Exception as e:
        return f"Error executing command in {repo_name}: {e}"

def github_manager(parameters: dict, player=None, **kwargs) -> str:
    action = parameters.get("action", "clone")
    repo_url = parameters.get("repo_url", "")
    repo_name = parameters.get("repo_name", "")
    command = parameters.get("command", "")

    if action == "clone":
        if not repo_url:
            return "Please provide a valid repo_url."
        return clone_or_update_repo(repo_url)
    elif action == "run":
        if not repo_name or not command:
            return "Specify both 'repo_name' and 'command' to run."
        if Path(repo_name).name != repo_name or repo_name in {".", ".."}:
            return "Invalid repository name. Use a single folder name under workspace/repos."
        if confirm.pending_title():
            return "A confirmation is already waiting on the HUD. Resolve it before running another command."
        return confirm.request(
            key="github_repo_command",
            title=f"Run command in repository {repo_name}?",
            detail=f"Repository: {repo_name}\nCommand: {command}",
            run=lambda: run_repo_command(repo_name, command),
        )
    return "Unknown action. Use 'clone' or 'run'."

TOOL = {
    "name": "github_manager",
    "description": "Clones/updates GitHub repositories in a local workspace. Running a repository command requires explicit HUD confirmation.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'clone' to clone/update a repo | 'run' to execute a command inside a cloned repo"
            },
            "repo_url": {
                "type": "STRING",
                "description": "GitHub repository HTTPS URL (e.g., https://github.com/user/repo)"
            },
            "repo_name": {
                "type": "STRING",
                "description": "Name of the target repo folder for running commands"
            },
            "command": {
                "type": "STRING",
                "description": "Shell command to run inside the repo (e.g., 'pip install -r requirements.txt', 'python test.py')"
            }
        },
        "required": ["action"]
    },
    "handler": github_manager
}