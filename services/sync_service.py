import logging
import os
import tempfile
import pypandoc
import config
from services import git_service, llm_service

logger = logging.getLogger(__name__)

AUTO_COMMIT_TAG = "[auto-readme]"


def markdown_to_docx(markdown_content, output_path):
    """Convert markdown string to .docx file using pandoc."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
        tmp.write(markdown_content)
        tmp_path = tmp.name

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        pypandoc.convert_file(tmp_path, "docx", outputfile=output_path)
        logger.info(f"Converted README to docx: {output_path}")
    finally:
        os.unlink(tmp_path)


def run_pipeline(repo_name: str, clone_url: str):
    """
    Full pipeline for any repo:
    1. Ensure repo is cloned on EC2 (auto-clone if first time)
    2. Pull latest
    3. Check if last commit is ours (avoid loop)
    4. Extract diff + current README
    5. Call LLM to update README
    6. Commit & push updated README back to source repo
    7. Convert README to .docx
    8. Place .docx in assets-chatbot/context/repos/<repo-name>.docx
    9. Commit & push to Assets-Chatbot
    """
    chatbot_repo = config.CHATBOT_REPO_PATH

    logger.info("=" * 50)
    logger.info(f"PIPELINE START: {repo_name}")
    logger.info("=" * 50)

    # Step 1: Ensure repo exists locally
    repo_path = git_service.ensure_repo_cloned(repo_name, clone_url)

    # Step 2: Pull latest
    logger.info(f"Pulling latest {repo_name}...")
    git_service.pull_latest(repo_path)

    # Step 3: Skip if last commit was ours
    last_msg = git_service.get_commit_message(repo_path)
    if AUTO_COMMIT_TAG in last_msg:
        logger.info(f"Last commit in {repo_name} was auto-generated. Skipping.")
        return {"status": "skipped", "repo": repo_name, "reason": "auto-commit detected"}

    # Step 4: Extract diff and current README
    diff = git_service.get_latest_diff(repo_path)
    changed_files = git_service.get_changed_files(repo_path)
    current_readme = git_service.read_file(repo_path, "README.md")

    if not diff:
        logger.info(f"No diff found for {repo_name}. Skipping.")
        return {"status": "skipped", "repo": repo_name, "reason": "empty diff"}

    # Step 5: Call LLM
    updated_readme = llm_service.update_readme(
        repo_name, current_readme, diff, changed_files, last_msg
    )

    if not updated_readme:
        return {"status": "error", "repo": repo_name, "reason": "LLM returned no content"}

    if updated_readme.strip() == current_readme.strip():
        logger.info(f"README unchanged for {repo_name} after LLM analysis.")
        return {"status": "skipped", "repo": repo_name, "reason": "no README changes needed"}

    # Step 6: Write and push README back to source repo
    git_service.write_file(repo_path, "README.md", updated_readme)
    pushed = git_service.commit_and_push(
        repo_path, "README.md", f"docs: update README {AUTO_COMMIT_TAG}"
    )
    logger.info(f"{repo_name} README pushed: {pushed}")

    # Step 7 & 8: Convert to .docx and place in chatbot context
    logger.info(f"Syncing {repo_name} to Assets-Chatbot...")
    git_service.pull_latest(chatbot_repo)

    context_file = os.path.join(config.CHATBOT_CONTEXT_DIR, f"{repo_name}.docx")
    full_docx_path = os.path.join(chatbot_repo, context_file)

    markdown_to_docx(updated_readme, full_docx_path)

    # Step 9: Commit and push chatbot repo
    pushed_chatbot = git_service.commit_and_push(
        chatbot_repo,
        context_file,
        f"context: sync {repo_name} README {AUTO_COMMIT_TAG}"
    )
    logger.info(f"Assets-Chatbot context pushed for {repo_name}: {pushed_chatbot}")

    logger.info(f"PIPELINE COMPLETE: {repo_name}")
    return {
        "status": "success",
        "repo": repo_name,
        "readme_updated": pushed,
        "chatbot_synced": pushed_chatbot,
        "context_file": context_file
    }