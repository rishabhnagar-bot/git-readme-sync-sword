import hmac
import hashlib
import json
import logging
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
import config
from services.sync_service import run_pipeline

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="README Sync Pipeline (Multi-Repo)")


def verify_github_signature(payload: bytes, signature: str | None) -> bool:
    """Verify the GitHub webhook HMAC SHA-256 signature."""
    if not config.WEBHOOK_SECRET:
        return True

    if not signature:
        return False

    expected = "sha256=" + hmac.new(
        config.WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def run_pipeline_safe(repo_name: str, clone_url: str):
    """Wrapper to catch and log errors in background task."""
    try:
        result = run_pipeline(repo_name, clone_url)
        logger.info(f"Pipeline result for {repo_name}: {result}")
    except Exception:
        logger.exception(f"Pipeline failed for {repo_name}.")


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()

    # 1. Verify signature
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_github_signature(body, signature):
        logger.warning("Invalid webhook signature.")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # 2. Only act on push events
    event = request.headers.get("X-GitHub-Event", "")
    if event == "ping":
        return {"status": "pong"}
    if event != "push":
        return {"status": "ignored", "event": event}

    # 3. Parse payload from the body we already read
    payload = json.loads(body)

    # 4. Only act on pushes to the target branch
    ref = payload.get("ref", "")
    target_ref = f"refs/heads/{config.GIT_BRANCH}"
    if ref != target_ref:
        logger.info(f"Push to {ref}, ignoring (watching {target_ref}).")
        return {"status": "ignored", "ref": ref}

    # 5. Skip if pusher is our bot
    pusher = payload.get("pusher", {}).get("name", "")
    if pusher == config.GIT_USER_NAME:
        logger.info("Push from bot, ignoring.")
        return {"status": "ignored", "reason": "bot push"}

    # 6. Extract repo info from payload
    repo_info = payload.get("repository", {})
    repo_name = repo_info.get("name", "")
    clone_url = repo_info.get("ssh_url", "")

    if not repo_name or not clone_url:
        logger.error("Could not extract repo name or clone URL from payload.")
        raise HTTPException(status_code=400, detail="Missing repository info")

    # 7. Run pipeline in background
    logger.info(f"Push to {repo_name}/{config.GIT_BRANCH} detected. Queuing pipeline...")
    background_tasks.add_task(run_pipeline_safe, repo_name, clone_url)

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "repo": repo_name,
            "message": "Pipeline queued"
        }
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/trigger/{repo_name}")
async def manual_trigger(repo_name: str, background_tasks: BackgroundTasks):
    """Manual trigger for a specific repo (for testing)."""
    logger.info(f"Manual pipeline trigger for {repo_name}.")

    # For manual triggers, construct the clone URL from convention
    # Adjust this if your GitHub org/user is different
    clone_url = ""  # Will use existing clone if already on disk

    background_tasks.add_task(run_pipeline_safe, repo_name, clone_url)
    return JSONResponse(
        status_code=202,
        content={"status": "accepted", "repo": repo_name, "message": "Pipeline queued"}
    )