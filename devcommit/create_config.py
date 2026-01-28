import os


def create_dcommit():
    dcommit_content = """# DevCommit Configuration File (OPTIONAL)
# This file is optional - you can use environment variables instead!
# 
# Copy this file to:
#   - ~/.dcommit (for global config)
#   - $VIRTUAL_ENV/config/.dcommit (for venv-specific config)
#
# Or use environment variables:
#   export GEMINI_API_KEY='your-api-key-here'
#   export COMMIT_MODE='directory'
#
# Priority: .dcommit file > Environment Variables > Defaults

# ════════════════════════════════════════════════════════════════
# AI Provider Configuration
# ════════════════════════════════════════════════════════════════

# AI Provider (default: gemini)
# Options: gemini, openai, groq, anthropic, ollama, custom
AI_PROVIDER = gemini

# ─── Gemini (Google) ───
# Get API key from: https://aistudio.google.com/app/apikey
GEMINI_API_KEY = your-api-key-here
GEMINI_MODEL = gemini-2.0-flash-exp

# ─── OpenAI ───
# OPENAI_API_KEY = your-openai-key
# OPENAI_MODEL = gpt-4o-mini

# ─── Groq (Fast & Free) ───
# Get API key from: https://console.groq.com/
# GROQ_API_KEY = your-groq-key
# GROQ_MODEL = llama-3.3-70b-versatile

# ─── Anthropic Claude ───
# ANTHROPIC_API_KEY = your-anthropic-key
# ANTHROPIC_MODEL = claude-3-haiku-20240307

# ─── OpenRouter ───
# OPENROUTER_API_KEY = your-openrouter-key
# OPENROUTER_MODEL = meta-llama/llama-3.3-70b-instruct:free

# ─── Ollama (Local) ───
# OLLAMA_BASE_URL = http://localhost:11434
# OLLAMA_MODEL = llama3

# ─── Custom API (OpenAI-compatible) ───
# CUSTOM_API_URL = http://your-server/v1
# CUSTOM_API_KEY = your-key
# CUSTOM_MODEL = your-model-name

# ════════════════════════════════════════════════════════════════
# General Configuration
# ════════════════════════════════════════════════════════════════

# Language/locale for commit messages (default: en-US)
LOCALE = en

# Number of commit message suggestions to generate (default: 1)
MAX_NO = 1

# Type of commit messages (default: general)
# Options: general, conventional, etc.
COMMIT_TYPE = conventional

# Gemini model to use (default: gemini-1.5-flash)
MODEL_NAME = gemini-1.5-flash

# Commit mode (default: auto)
# Options:
#   - auto: Prompts when multiple directories are detected
#   - directory: Always use directory-based commits for multiple directories
#   - global: Always create one commit for all changes
COMMIT_MODE = auto

# Files to exclude from diff (default: package-lock.json, pnpm-lock.yaml, yarn.lock, *.lock)
# Comma-separated list of file patterns
EXCLUDE_FILES = *.lock, dist/*, build/*, node_modules/*

# Directory for changelog files (default: changelogs)
# Used when --changelog flag is passed
CHANGELOG_DIR = changelogs
    """
    
    if "VIRTUAL_ENV" in os.environ:
        target_directory = os.path.join(
            os.environ.get("VIRTUAL_ENV", ""), "config"
        )
    else:
        target_directory = os.path.expanduser("~/")

    os.makedirs(target_directory, exist_ok=True)
    dcommit_file = os.path.join(target_directory, ".dcommit")

    if os.path.exists(dcommit_file):
        print(f"⚠️  Config file already exists at: {dcommit_file}")
        print("❌ Operation cancelled to prevent overwriting.")
        return

    with open(dcommit_file, "w") as file:
        file.write(dcommit_content.strip())
    print(f"✅ .dcommit file created at: {dcommit_file}")


if __name__ == "__main__":
    create_dcommit()
