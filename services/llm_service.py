import requests
import logging
import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a technical documentation assistant. 
Your job is to update a project README based on code changes.

Rules:
- Only modify sections affected by the diff.
- Preserve the existing structure, tone, and formatting.
- If new endpoints, dependencies, config, or behavior were added/removed/changed, reflect that.
- If the diff is trivial (comments, formatting, whitespace) and doesn't affect docs, return the README unchanged.
- Return ONLY the full updated README. No explanation, no markdown fences."""


def build_prompt(repo_name, current_readme, diff, changed_files, commit_msg):
    return f"""You are updating the README for a project called "{repo_name}".

Here is the CURRENT README:

<current_readme>
{current_readme}
</current_readme>

COMMIT MESSAGE:
{commit_msg}

FILES CHANGED:
{changed_files}

FULL DIFF:
<diff>
{diff}
</diff>

Update the README to reflect these changes. Return ONLY the complete updated README."""


def update_readme(repo_name, current_readme, diff, changed_files, commit_msg):
    """Send diff + README to Groq API and get updated README back."""
    prompt = build_prompt(repo_name, current_readme, diff, changed_files, commit_msg)

    logger.info(f"Calling Groq API ({config.GROQ_MODEL}) to update README for {repo_name}...")

    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_completion_tokens": 4096
    }

    try:
        response = requests.post(
            config.GROQ_API_URL,
            headers=headers,
            json=payload,
            timeout=config.GROQ_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()

        # Groq follows OpenAI response format
        updated = data["choices"][0]["message"]["content"]

        if not updated.strip():
            logger.warning("Groq returned empty response.")
            return None

        # Clean up if LLM wraps in markdown fences
        updated = updated.strip()
        if updated.startswith("```markdown"):
            updated = updated[len("```markdown"):].strip()
        if updated.startswith("```"):
            updated = updated[3:].strip()
        if updated.endswith("```"):
            updated = updated[:-3].strip()

        logger.info(f"Groq returned updated README for {repo_name}.")
        return updated

    except requests.RequestException as e:
        logger.error(f"Groq API request failed for {repo_name}: {e}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"Response body: {e.response.text}")
        return None