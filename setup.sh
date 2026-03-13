#!/bin/bash
set -e

echo "========================================="
echo "  README Sync Pipeline - EC2 Setup"
echo "  (Multi-Repo Version)"
echo "========================================="

# --- Configuration (edit these) ---
GITHUB_USER="your-github-username"
CHATBOT_REPO="assets-chatbot"
REPOS_DIR="/home/ubuntu/repos"
APP_DIR="/home/ubuntu/git-readme-sync-sword"

# --- Install dependencies ---
echo "📦 Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv git pandoc

# --- Create repos directory ---
echo "📁 Setting up repos directory..."
mkdir -p "$REPOS_DIR"

# --- Clone chatbot repo (the only one we need upfront) ---
if [ ! -d "$REPOS_DIR/$CHATBOT_REPO" ]; then
    echo "Cloning $CHATBOT_REPO..."
    git clone "git@github.com:$GITHUB_USER/$CHATBOT_REPO.git" "$REPOS_DIR/$CHATBOT_REPO"
else
    echo "$CHATBOT_REPO already cloned."
fi

# Source repos will be auto-cloned on first webhook trigger.
echo "ℹ️  Source repos will be auto-cloned when their first webhook fires."

# --- Setup Python environment ---
echo "🐍 Setting up Python environment..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# --- Create .env file if missing ---
if [ ! -f "$APP_DIR/.env" ]; then
    echo "📝 Creating .env file (edit this with your values)..."
    cat > "$APP_DIR/.env" << EOF
REPOS_BASE_DIR=$REPOS_DIR
CHATBOT_REPO_PATH=$REPOS_DIR/$CHATBOT_REPO
CHATBOT_CONTEXT_DIR=context/repos
GIT_BRANCH=main
GROQ_API_KEY=your-groq-api-key-here
GROQ_API_URL=https://api.groq.com/openai/v1/chat/completions
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_TIMEOUT=90
WEBHOOK_SECRET=your-webhook-secret-here
APP_PORT=5000
GIT_USER_NAME=readme-bot
GIT_USER_EMAIL=readme-bot@automation
EOF
    echo "⚠️  Edit $APP_DIR/.env with your actual values!"
fi

# --- Install systemd service ---
echo "⚙️  Installing systemd service..."
sudo cp "$APP_DIR/readme-sync.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable readme-sync
sudo systemctl start readme-sync

echo ""
echo "========================================="
echo "  ✅ Setup complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Edit $APP_DIR/.env with your actual values"
echo "  2. Add your EC2 SSH key to GitHub (for push access to all repos)"
echo "  3. For EACH source repo, add a GitHub webhook:"
echo "     URL: http://<your-ec2-ip>:5000/webhook"
echo "     Secret: same as .env WEBHOOK_SECRET"
echo "     Events: Just the push event"
echo "  4. Restart: sudo systemctl restart readme-sync"
echo "  5. Check logs: sudo journalctl -u readme-sync -f"
echo ""
echo "Adding a new repo? Just add the webhook on GitHub."
echo "The pipeline will auto-clone it on first trigger."
echo ""