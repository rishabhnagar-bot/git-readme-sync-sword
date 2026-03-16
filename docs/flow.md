## Multi-Repo Flow — End to End

Let's say a developer pushes code to **Repo X** (one of your 20+ repos).

---

### Step 1: GitHub fires webhook

GitHub sees a push to Repo X's `main` branch and sends a POST request to your EC2:

```
POST http://<ec2-ip>:5000/webhook

Headers:
  X-GitHub-Event: push
  X-Hub-Signature-256: sha256=abc123...

Body (JSON):
  {
    "ref": "refs/heads/main",
    "pusher": { "name": "developer-name" },
    "repository": {
      "name": "repo-x",
      "ssh_url": "git@github.com:your-org/repo-x.git"
    }
  }
```

---

### Step 2: FastAPI receives and validates (`app.py`)

The webhook endpoint runs through 5 checks in order:

1. **Signature check** — verifies the HMAC SHA-256 signature matches your secret. Rejects if invalid.
2. **Event check** — is it a `push` event? Ignores `pull_request`, `issues`, etc.
3. **Branch check** — is the `ref` equal to `refs/heads/main`? Ignores pushes to feature branches.
4. **Bot check** — is the pusher `readme-bot`? If yes, this is our own auto-commit pushing back, so ignore it. This is **loop prevention layer 1**.
5. **Extract repo info** — pulls `repo_name` ("repo-x") and `clone_url` ("git@github.com:your-org/repo-x.git") from the payload.

All checks pass → queues `run_pipeline("repo-x", "git@github.com:...")` as a **background task** and immediately returns `202 Accepted` to GitHub so the webhook doesn't time out.

---

### Step 3: Pipeline runs in background (`sync_service.py`)

**3a. Ensure repo is cloned** (`git_service.py`)

Checks if `/home/ubuntu/repos/repo-x` exists on EC2. If this is the **first time** Repo X triggers a webhook, it doesn't exist yet — so the pipeline runs `git clone git@github.com:your-org/repo-x.git /home/ubuntu/repos/repo-x` automatically. Next time, it skips this step.

**3b. Pull latest**

Runs `git pull origin main` inside `/home/ubuntu/repos/repo-x` to get the latest code including the commit that triggered this webhook.

**3c. Loop prevention layer 2**

Reads the last commit message. If it contains `[auto-readme]`, that means the last commit was made by our bot — so it stops. This prevents: developer pushes → bot updates README and pushes → GitHub fires webhook again → bot would update again → infinite loop.

**3d. Extract the diff**

Runs three git commands on Repo X:
- `git show --stat --patch HEAD` → the full diff of what changed
- `git diff-tree --no-commit-id --name-status -r HEAD` → list of files added/modified/deleted
- `git log -1 --pretty=%B` → the commit message

Also reads the current `README.md` from disk.

**3e. Call your LLM**

Sends a prompt to your LLM endpoint containing:
- The repo name ("repo-x")
- The current README
- The commit message
- The list of changed files
- The full diff

The prompt asks: "Update this README to reflect these changes. Only change sections affected by the diff. If the changes are trivial, return the README unchanged."

The LLM returns the full updated README.

**3f. Push updated README back to Repo X**

Writes the LLM's output to `/home/ubuntu/repos/repo-x/README.md`, then:
```
git add README.md
git commit -m "docs: update README [auto-readme]"
git push origin main
```

Now **Repo X on GitHub** has the updated README. The commit message contains `[auto-readme]` so when GitHub fires another webhook for this push, step 3c will catch it and stop.

**3g. Pull Assets-Chatbot**

Runs `git pull origin main` inside `/home/ubuntu/repos/assets-chatbot` to get the latest state.

**3h. Convert README to .docx**

Takes the updated README markdown, writes it to a temp file, runs pandoc to convert it to `.docx`, and places the output at:
```
/home/ubuntu/repos/assets-chatbot/context/repos/repo-x.docx
```

The filename is derived from the repo name — so each repo gets its own `.docx` file automatically.

**3i. Push to Assets-Chatbot**

```
git add context/repos/repo-x.docx
git commit -m "context: sync repo-x README [auto-readme]"
git push origin main
```

Now **Assets-Chatbot on GitHub** has the updated context file for Repo X.

---

### What the Assets-Chatbot context directory looks like over time

```
assets-chatbot/
└── context/
    └── repos/
        ├── simple-python-app.docx    ← synced when simple-python-app is pushed
        ├── repo-b.docx               ← synced when repo-b is pushed
        ├── repo-c.docx               ← synced when repo-c is pushed
        ├── auth-service.docx          ← synced when auth-service is pushed
        └── ...                        ← grows automatically
```

Each `.docx` is only updated when its corresponding source repo gets a push. They're independent of each other.

---

### Loop prevention — 3 layers

| Layer | Where | How |
|-------|-------|-----|
| 1 | `app.py` | Webhook ignores pushes where `pusher.name` is `readme-bot` |
| 2 | `sync_service.py` | Pipeline stops if last commit message contains `[auto-readme]` |
| 3 | Natural | Bot pushes via SSH → GitHub fires webhook → caught by layer 1 or 2 |

---

### Adding repo #21 in the future

1. Go to the new repo on GitHub → Settings → Webhooks
2. Add `http://<ec2-ip>:5000/webhook`, same secret, push events only
3. That's it. First push auto-clones the repo on EC2 and everything flows.

No config files to edit, no code to change, no deployments to make.