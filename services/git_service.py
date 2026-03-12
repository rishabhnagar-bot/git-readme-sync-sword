import subprocess
import logging
import os
import config

logger = logging.getLogger(__name__)


def _run(cmd, cwd=None):
    """Run a shell command and return stdout."""
    logger.info(f"Running: {' '.join(cmd)} (cwd={cwd})")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        logger.error(f"Command failed: {result.stderr}")
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def _configure_git(repo_path):
    """Set git user for automated commits."""
    _run(["git", "config", "user.name", config.GIT_USER_NAME], cwd=repo_path)
    _run(["git", "config", "user.email", config.GIT_USER_EMAIL], cwd=repo_path)


def get_repo_path(repo_name):
    """Get the local path for a repo by name."""
    return os.path.join(config.REPOS_BASE_DIR, repo_name)


def ensure_repo_cloned(repo_name, clone_url):
    """Clone the repo if it doesn't exist locally. Returns repo path."""
    repo_path = get_repo_path(repo_name)

    if os.path.exists(repo_path):
        logger.info(f"Repo {repo_name} already cloned at {repo_path}")
        return repo_path

    if not clone_url:
        raise RuntimeError(
            f"Repo {repo_name} not found at {repo_path} and no clone URL provided."
        )

    logger.info(f"Cloning {repo_name} from {clone_url}...")
    os.makedirs(config.REPOS_BASE_DIR, exist_ok=True)
    _run(["git", "clone", clone_url, repo_path])
    logger.info(f"Cloned {repo_name} to {repo_path}")
    return repo_path


def pull_latest(repo_path):
    """Pull the latest changes from remote."""
    _run(["git", "checkout", config.GIT_BRANCH], cwd=repo_path)
    _run(["git", "pull", "origin", config.GIT_BRANCH], cwd=repo_path)


def get_latest_diff(repo_path):
    """Get the diff of the most recent commit."""
    return _run(["git", "show", "--stat", "--patch", "HEAD"], cwd=repo_path)


def get_changed_files(repo_path):
    """Get list of files changed in the latest commit."""
    return _run(
        ["git", "diff-tree", "--no-commit-id", "--name-status", "-r", "HEAD"],
        cwd=repo_path
    )


def get_commit_message(repo_path):
    """Get the latest commit message."""
    return _run(["git", "log", "-1", "--pretty=%B"], cwd=repo_path)


def read_file(repo_path, relative_path):
    """Read a file from the repo."""
    full_path = os.path.join(repo_path, relative_path)
    try:
        with open(full_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"File not found: {full_path}")
        return ""


def write_file(repo_path, relative_path, content):
    """Write content to a file in the repo."""
    full_path = os.path.join(repo_path, relative_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)


def commit_and_push(repo_path, file_path, message):
    """Stage a file, commit, and push. Returns True if a commit was made."""
    _configure_git(repo_path)
    _run(["git", "add", file_path], cwd=repo_path)

    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=repo_path
    )
    if result.returncode == 0:
        logger.info("No changes to commit.")
        return False

    _run(["git", "commit", "-m", message], cwd=repo_path)
    _run(["git", "push", "origin", config.GIT_BRANCH], cwd=repo_path)
    logger.info(f"Pushed to {repo_path} on branch {config.GIT_BRANCH}")
    return True