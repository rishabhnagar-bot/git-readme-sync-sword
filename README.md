# git-readme-sync-pipeline

A FastAPI webhook server that automatically keeps README files up to date across multiple GitHub repositories using an LLM (Groq).

## How it works

1. GitHub sends a push webhook to this service
2. The service pulls the latest code from the source repo
3. It extracts the diff and current README, then calls Groq to generate an updated README
4. The updated README is committed back to the source repo
5. The README is also converted to `.docx` and synced to a chatbot context repo (`assets-chatbot`)

## Setup

```bash
pip install -r requirements.txt
brew install pandoc  # required for .docx conversion
```

Copy `.env` and fill in your values:

```env
WEBHOOK_SECRET=your_github_webhook_secret
GROQ_API_KEY=your_groq_api_key
REPOS_BASE_DIR=/path/to/local/repos
CHATBOT_REPO_PATH=/path/to/assets-chatbot
GIT_USER_NAME=readme-bot
GIT_USER_EMAIL=readme-bot@automation
```

## Running

```bash
uvicorn app:app --host 0.0.0.0 --port 5000
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/webhook` | GitHub push webhook receiver |
| `GET` | `/health` | Health check |
| `POST` | `/trigger/{repo_name}` | Manually trigger pipeline for a repo |

## Testing

Health check:
```bash
curl http://localhost:5000/health
```

Manual trigger (repo must already be cloned locally):
```bash
curl -X POST http://localhost:5000/trigger/my-repo-name
```

Simulate a GitHub webhook:
```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -d '{
    "ref": "refs/heads/main",
    "pusher": {"name": "someone"},
    "repository": {"name": "my-repo", "ssh_url": "git@github.com:org/my-repo.git"}
  }'
```

## Project structure

```
.
├── app.py                  # FastAPI app and webhook handler
├── config.py               # Config via environment variables
├── requirements.txt
├── services/
│   ├── git_service.py      # Git operations (clone, pull, diff, commit, push)
│   ├── llm_service.py      # Groq API integration
│   └── sync_service.py     # Pipeline orchestration
└── readme-sync.service     # systemd unit file for EC2 deployment
```
