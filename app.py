import hmac
import hashlib
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

app = FastAPI(title="README Sync Pipeline")


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


def run_pipeline_safe():
    """Wrapper to catch and log errors in background task."""
    try:
        result = run_pipeline()
        logger.info(f"Pipeline result: {result}")
    except Exception:
        logger.exception("Pipeline failed in background task.")


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
    if event != "push":
        return {"status": "ignored", "event": event}

    # 3. Parse payload
    payload = await request.json()

    # 4. Only act on pushes to the target branch
    ref = payload.get("ref", "")
    target_ref = f"refs/heads/{config.GIT_BRANCH}"
    if ref != target_ref:
        logger.info(f"Push to {ref}, ignoring (watching {target_ref}).")
        return {"status": "ignored", "ref": ref}

    # 5. Skip if pusher is our bot (loop prevention)
    pusher = payload.get("pusher", {}).get("name", "")
    if pusher == config.GIT_USER_NAME:
        logger.info("Push from bot, ignoring.")
        return {"status": "ignored", "reason": "bot push"}

    # 6. Run pipeline in background so GitHub gets a fast response
    logger.info(f"Push to {config.GIT_BRANCH} detected. Queuing pipeline...")
    background_tasks.add_task(run_pipeline_safe)

    return JSONResponse(
        status_code=202,
        content={"status": "accepted", "message": "Pipeline queued"}
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/trigger")
async def manual_trigger(background_tasks: BackgroundTasks):
    """Manual trigger for testing."""
    logger.info("Manual pipeline trigger.")
    background_tasks.add_task(run_pipeline_safe)
    return JSONResponse(
        status_code=202,
        content={"status": "accepted", "message": "Pipeline queued"}
    )