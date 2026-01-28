# DevCommit

A command-line AI tool for autocommits.

## Features

- 🤖 **Multi-AI Provider Support** - Choose from Gemini, Groq, OpenAI, Claude, Ollama, or custom APIs
- 🚀 Automatic commit generation using AI
- 📝 **Changelog Generation** - Automatically generate markdown changelogs from your changes
- 📁 Directory-based commits - create separate commits for each root directory
- 🎯 Interactive mode to choose between global or directory-based commits
- 📄 **Commit specific files or folders** - Stage and commit only selected files/directories
- 🔄 **Regenerate commit messages** - Don't like the suggestions? Regenerate with one click
- 🚀 **Push to remote** - Automatically push commits after committing
- ⚙️ Flexible configuration - use environment variables or .dcommit file
- 🏠 Self-hosted model support - use your own AI infrastructure
- 🆓 Multiple free tier options available

![DevCommit Demo](https://i.imgur.com/erPaZjc.png)

## Installation

1. **Install DevCommit**

   **Option 1: Using pip (local installation)**

   ```bash
   pip install devcommit
   ```

   **Option 2: Using pipx (global installation, recommended)**

   ```bash
   # Install pipx if you don't have it
   python3 -m pip install --user pipx
   python3 -m pipx ensurepath

   # Install DevCommit globally
   pipx install devcommit
   ```

   > **💡 Why pipx?** pipx installs CLI tools in isolated environments, preventing dependency conflicts while making them globally available.

   **All AI providers are included by default!** ✅ Gemini, OpenAI, Groq, OpenRouter, Anthropic, Ollama, and Custom API support.

2. **Set Up Configuration (Required: API Key)**  
   DevCommit requires an API key for your chosen AI provider. You can configure it using **any** of these methods:

   **Priority Order:** `.dcommit` file → Environment Variables → Defaults

   ### Option 1: Environment Variables (Quickest)

   ```bash
   # Using Gemini (default)
   export GEMINI_API_KEY='your-api-key-here'

   # Or using Groq (recommended for free tier)
   export AI_PROVIDER='groq'
   export GROQ_API_KEY='your-groq-key'
   # Optional: set model (provider-specific key or MODEL_NAME as a fallback)
   export GROQ_MODEL='llama-3.3-70b-versatile'   # or
   export MODEL_NAME='llama-3.3-70b-versatile'

   # Add to ~/.bashrc or ~/.zshrc for persistence
   echo "export GEMINI_API_KEY='your-key'" >> ~/.bashrc
   ```

   ### Option 2: .dcommit File (Home Directory)

   ```bash
   cat > ~/.dcommit << 'EOF'
   GEMINI_API_KEY = your-api-key-here
   LOCALE = en
   MAX_NO = 1
   COMMIT_TYPE = conventional
   # Model selection (provider-specific key takes priority, MODEL_NAME is the fallback)
   # GEMINI_MODEL / OPENAI_MODEL / GROQ_MODEL / OPENROUTER_MODEL / ANTHROPIC_MODEL / OLLAMA_MODEL / CUSTOM_MODEL
   MODEL_NAME = gemini-2.5-flash
   COMMIT_MODE = auto
   EOF
   ```

   ### Option 3: .dcommit File (Virtual Environment)

   ```bash
   mkdir -p $VIRTUAL_ENV/config
   cat > $VIRTUAL_ENV/config/.dcommit << 'EOF'
   GEMINI_API_KEY = your-api-key-here
   LOCALE = en
   MAX_NO = 1
   COMMIT_TYPE = conventional
   MODEL_NAME = gemini-2.0-flash-exp
   COMMIT_MODE = auto
   EOF
   ```

   **Get your API key:** https://aistudio.google.com/app/apikey

## Usage

After installation, you can start using DevCommit directly in your terminal:

```bash
devcommit
```

### Basic Usage

- **Stage all changes and commit:**

  ```bash
  devcommit --stageAll
  ```

- **Commit staged changes:**
  ```bash
  devcommit
  ```

### Directory-Based Commits

DevCommit supports generating separate commits per root directory, which is useful when you have changes across multiple directories.

#### Configuration Options

You can set your preferred commit mode in the `.dcommit` configuration file using the `COMMIT_MODE` variable:

- **`COMMIT_MODE = auto`** (default): Automatically prompts when multiple directories are detected
- **`COMMIT_MODE = directory`**: Always use directory-based commits for multiple directories
- **`COMMIT_MODE = global`**: Always create one commit for all changes
- **`COMMIT_MODE = related`**: Group related changes together using AI analysis

**Priority order:** CLI flag (`--directory`) → Config file (`COMMIT_MODE`) → Interactive prompt (if `auto`)

#### Command-Line Usage

- **Interactive mode (auto):** When you have changes in multiple directories, DevCommit will automatically ask if you want to:

  - 🌐 Create one commit for all changes (global commit)
  - 📁 Create separate commits per directory
  - 🔗 Group related changes together (AI-powered)

- **Force directory-based commits:**
  ```bash
  devcommit --directory
  # or
  devcommit -d
  ```

When using directory-based commits, you can:

1. Select which directories to commit (use Space to select, Enter to confirm)
2. For each selected directory, review and choose a commit message
3. Each directory gets its own commit with AI-generated messages based on its changes

### Related Changes Grouping (AI-Powered)

DevCommit can intelligently group related changes together based on **semantic relationships**, regardless of directory structure. This creates clean, logical commits that reflect what you actually changed.

#### Grouping Principles

The AI analyzes your changes using these priorities:

1. **Feature/Intent-Based Grouping** (Highest Priority)
   - All files implementing the SAME feature go together
   - Example: Adding "User Comments" groups schema + endpoints + migrations + tests + services = **1 commit**

2. **Entity/Domain-Based Grouping**
   - Changes to the same domain entity belong together
   - Looks for: shared entity names, table names, class names, import relationships

3. **Bug Fix Grouping**
   - A bug fix touching multiple areas stays as one logical fix
   - Grouped by the bug being fixed, not file location

4. **Refactoring Grouping**
   - Renaming across 10 files = 1 commit, not 10 separate commits

5. **Configuration Grouping**
   - Config changes + code that uses that config = 1 commit

#### How It Works

1. DevCommit analyzes all staged file diffs
2. AI examines the **content** of changes to find relationships:
   - Shared entity/class names
   - Import relationships between files
   - Shared database tables
   - Shared API endpoints
   - Test-to-implementation relationships
   - Naming conventions (user_model.py, user_controller.py → same entity)
3. Files are grouped by **what they accomplish together**, not by directory
4. Each group gets a commit with type badge: ✨ feature, 🐛 bugfix, ♻️ refactor, etc.

#### Performance Considerations

**Token Usage:** The "Group related changes together" feature analyzes all file diffs in a single AI call to understand relationships, which consumes more tokens than other commit modes. This is because:

- All file diffs are sent to the AI simultaneously for semantic analysis
- The AI generates commit messages for each group in the same call
- Larger changesets (many files or large diffs) will use proportionally more tokens

**When to Use:**
- ✅ Best for: Medium-sized changesets (5-50 files) where logical grouping matters
- ✅ Ideal when: You want semantically coherent commits regardless of directory structure
- ⚠️ Consider alternatives for: Very large changesets (100+ files) or when token costs are a concern

For large changesets, you might prefer:
- **Directory-based commits** (`COMMIT_MODE=directory`) - processes each directory separately
- **Global commit** (`COMMIT_MODE=global`) - one commit for everything

#### Configuration

Set `COMMIT_MODE = related` in your `.dcommit` file to always use related grouping:

```bash
cat > ~/.dcommit << 'EOF'
GEMINI_API_KEY = your-api-key-here
COMMIT_MODE = related
EOF
```

Or select it interactively when prompted (with `COMMIT_MODE = auto`):

```
❯ Commit strategy (Use arrow keys)
    🌐 One commit for all changes
    📁 Separate commits per directory
  ❯ 🔗 Group related changes together
```

#### Real-World Example

You're working on multiple things and have changes across many files and directories:

**Staged files:**
```
schema/appointment.py          # New appointment model
src/api/appointments.py        # Appointment endpoints  
src/services/booking_service.py # Booking logic
migrations/003_appointments.sql # Database migration
tests/test_appointments.py     # Feature tests
src/auth/session.py            # Fixed session timeout (unrelated)
src/middleware/auth.py         # Fixed session timeout (unrelated)
config/redis.py                # Updated cache settings (unrelated)
```

**DevCommit analyzes the code and groups by semantic relationship:**

```
╭────────────────────────────────────────────────────────────╮
│  ✅ Found 3 logical group(s)                               │
╰────────────────────────────────────────────────────────────╯

  ✨ add-appointment-booking [feature] (5 files)
     Add appointment booking system with scheduling functionality
       └─ schema/appointment.py
       └─ src/api/appointments.py
       └─ src/services/booking_service.py
       └─ migrations/003_appointments.sql
       └─ tests/test_appointments.py

  🐛 fix-session-timeout [bugfix] (2 files)
     Fix user session expiring prematurely on idle
       └─ src/auth/session.py
       └─ src/middleware/auth.py

  ⚙️ update-redis-config [config] (1 file)
     Update Redis cache TTL and connection pool settings
       └─ config/redis.py
```

**Result:** 3 focused, logical commits instead of 8 directory-based commits!

The AI identifies relationships by analyzing:
- Shared class/function names in the diffs
- Import statements connecting files
- Database table names
- API endpoint patterns
- File naming conventions

#### Group Selection Options

After DevCommit analyzes and groups your changes, you'll see three options:

1. **✅ Commit all groups** - Automatically processes all groups sequentially (no prompts between groups)
2. **📋 Select specific groups** - Choose which groups to commit:
   - No groups are pre-selected (you must explicitly select with Space)
   - If you press Enter without selecting any, you'll be re-prompted with: "⚠️  You need to select at least one group to continue"
   - After committing each selected group, you'll be asked if you want to continue to the next
3. **🔄 Regenerate grouping** - Re-runs the AI analysis to create new groups (useful if the initial grouping isn't ideal)

**Example workflow:**
```
✅ Found 5 logical group(s)

? What would you like to do?
  ✅ Commit all groups
  📋 Select specific groups
  🔄 Regenerate grouping

[User selects "Select specific groups"]

? Select groups to commit
  (none selected - use Space to toggle)
  
[User presses Enter without selecting]
⚠️  You need to select at least one group to continue
Use Space to select groups, then press Enter

? Select groups to commit
  [✓] ✨ add-user-feature [feature] (4 files)
  [ ] 🐛 fix-bug [bugfix] (2 files)
  [✓] 📝 update-docs [docs] (3 files)
  
✓ Selected 2 group(s) to commit

[After committing first group]
? Continue to next group (1 remaining)? (y/n)
```

### Commit Specific Files or Folders

DevCommit allows you to commit specific files or folders. This is useful when you want to commit only certain changes without affecting other staged files.

**Usage:**

```bash
# Commit specific files (must be staged first)
git add file1.py file2.py
devcommit --files file1.py file2.py

# Stage and commit specific files in one command
devcommit --stageAll --files file1.py file2.py

# Commit specific folders (must be staged first)
git add src/ tests/
devcommit --files src/ tests/

# Stage and commit multiple directories
devcommit -s -f src/core src/modules/account/ src/modules/auth/

# Short form
devcommit -s -f file1.py file2.py
```

When using `--files` or `-f`:

- Without `--stageAll`: Only commits files that are already staged (filters staged files to match specified paths)
- With `--stageAll`: Stages the specified files/folders and then commits them
- AI generates commit messages based on changes in those files
- Works with both individual files and entire directories
- Files with no changes are automatically filtered out

#### Commit Mode Behavior with `--files`

The `--files` flag respects your `COMMIT_MODE` setting:

- **`COMMIT_MODE=directory`** with `--files`:
  - **Individual files**: Each file gets its own separate commit
    - Example: `devcommit -f src/test1.py src/test2.py` creates 2 separate commits
  - **Directories**: Each directory gets one commit containing all its files
    - Example: `devcommit -f src/core src/modules/account/` creates 2 commits (one per directory)

- **`COMMIT_MODE=global`** with `--files`:
  - All specified files/directories are committed together in a single commit
  - Example: `devcommit -f src/test1.py src/test2.py` creates 1 commit for both files

- **`COMMIT_MODE=auto`** with `--files`:
  - Always prompts you to choose between one commit for all files or separate commits
  - If you select directory mode: individual files get separate commits, directories get one commit each
  - If you select global mode: everything is committed together

### Push to Remote

DevCommit can automatically push your commits to the remote repository after committing.

**Usage:**

```bash
# Commit all staged changes and push
devcommit --push

# Commit specific files and push
devcommit --files file1.py file2.py --push

# Stage, commit, and push in one command
devcommit --stageAll --push

# Short form
devcommit -p
devcommit -f file1.py -p
```

**Note:** The push operation will only execute if commits were successfully made. If you cancel the commit, the push will be skipped.

### Regenerate Commit Messages

Don't like the AI-generated commit messages? You can regenerate them on the fly!

When viewing commit message options, you'll see:
- Numbered commit message suggestions
- ✏️ Enter custom message
- 🔄 **Regenerate commit messages** (new!)
- ❌ Cancel

Selecting "Regenerate commit messages" will:
- Call the AI again to generate new suggestions
- Show the new messages in the same prompt
- Allow you to regenerate again or select a message

This works for all commit modes (global, directory, and per-file commits).

### Changelog Generation

DevCommit can automatically generate markdown changelog files from your changes using AI.

**Usage:**

```bash
# Generate changelog after committing
devcommit --changelog

# Generate changelog before staging (recommended)
devcommit --stageAll --changelog

# Short form
devcommit -s -c

# With specific files
devcommit --stageAll --changelog --files src/
```

**How it works:**

- **With `--stageAll`**: Changelog is generated from unstaged changes **before** staging
- **Without `--stageAll`**: Changelog is generated from the last commit **after** committing
- Changelogs are saved as markdown files with datetime-based names (e.g., `2026-01-28_00-55-30.md`)
- Default directory: `changelogs/` (configurable via `CHANGELOG_DIR` in `.dcommit`)
- Uses Keep a Changelog format with AI-generated content

**Example workflow:**

```bash
# Make changes to your code
# ...

# Stage all changes and generate changelog before committing
devcommit --stageAll --changelog

# The changelog file is created in changelogs/ directory
# Then changes are staged and committed
```

### Additional Options

- `--excludeFiles` or `-e`: Exclude specific files from the diff
- `--generate` or `-g`: Specify number of commit messages to generate
- `--commitType` or `-t`: Specify the type of commit (e.g., conventional)
- `--stageAll` or `-s`: Stage all changes before committing
- `--directory` or `-d`: Force directory-based commits
- `--files` or `-f`: Stage and commit specific files or folders (can specify multiple)
- `--push` or `-p`: Push commits to remote after committing
- `--changelog` or `-c`: Generate changelog file from changes

### Examples

```bash
# Stage all and commit with directory-based option
devcommit --stageAll --directory

# Commit with specific commit type
devcommit --commitType conventional

# Exclude lock files
devcommit --excludeFiles package-lock.json yarn.lock

# Stage and commit specific files
devcommit --files file1.py file2.py

# Stage and commit specific folders
devcommit --files src/ tests/

# Stage and commit multiple files and folders at once
devcommit --files src/ file1.py tests/ config.json

# Commit and push
devcommit --push

# Commit specific files and push
devcommit --files file1.py file2.py --push

# Stage and commit multiple directories with directory mode
devcommit -s -f src/core src/modules/account/ --directory

# Stage and commit, then push
devcommit -s -f src/core src/modules/account/ -p

# Generate changelog before staging and committing
devcommit --stageAll --changelog

# Generate changelog after committing
devcommit --changelog

# Generate changelog with specific files
devcommit -s -c -f src/
```

## AI Provider Support

DevCommit now supports **multiple AI providers**! Choose from:

| Provider         | Free Tier          | Speed       | Quality   | Get API Key                                       |
| ---------------- | ------------------ | ----------- | --------- | ------------------------------------------------- |
| 🆓 **Gemini**    | 15 req/min, 1M/day | Fast        | Good      | [Get Key](https://aistudio.google.com/app/apikey) |
| ⚡ **Groq**      | Very generous      | **Fastest** | Good      | [Get Key](https://console.groq.com/keys)          |
| 🌐 **OpenRouter**| Free models available | Fast      | Good      | [Get Key](https://openrouter.ai/keys)            |
| 🤖 **OpenAI**    | $5 trial           | Medium      | **Best**  | [Get Key](https://platform.openai.com/api-keys)   |
| 🧠 **Anthropic** | Limited trial      | Medium      | Excellent | [Get Key](https://console.anthropic.com/)         |
| 🏠 **Ollama**    | **Unlimited**      | Medium      | Good      | [Install](https://ollama.ai/)                     |
| 🔧 **Custom**    | Varies             | Varies      | Varies    | Your server                                       |

### Quick Setup Examples

**Using Groq (Recommended for free tier):**

```bash
export AI_PROVIDER=groq
export GROQ_API_KEY='your-groq-api-key'
devcommit
```

**Using OpenRouter.ai (Access to multiple free models):**

```bash
export AI_PROVIDER=openrouter
export OPENROUTER_API_KEY='your-openrouter-api-key'
# Optional: specify model (default: meta-llama/llama-3.3-70b-instruct:free)
export OPENROUTER_MODEL='meta-llama/llama-3.3-70b-instruct:free'
devcommit
```

**Popular free models on OpenRouter (add `:free` suffix):**

**Recommended Models:**
- `meta-llama/llama-3.3-70b-instruct:free` - Llama 3.3 70B Instruct (Powerful & General Purpose)
- `google/gemma-3-27b-it:free` - Google Gemma 3 27B Instruct (Efficient & Capable)
- `openai/gpt-oss-120b:free` - OpenAI GPT-OSS 120B (Large & Experimental)
- `tngtech/deepseek-r1t-chimera:free` - DeepSeek R1T Chimera (Strong Reasoning)
- `qwen/qwen3-next-80b-a3b-instruct:free` - Qwen3 Next 80B (Advanced Instruction Following)

**Important Notes:**
- **Logging Requirements:** Some free models may log your prompts and responses for model improvement purposes. This means:
  - Your code diffs and commit messages may be stored by the provider
  - **Do NOT use free models with logging for sensitive/confidential code**
  - Check each model's documentation on OpenRouter for specific logging policies
- **Rate Limits:** Free models typically have rate limits (requests per minute/day)
- **Trial Use:** Some free models are marked as "trial use only" - not for production

Check [OpenRouter's models page](https://openrouter.ai/models?q=%3Afree) for the latest list, restrictions, and logging policies for each model.

**Using Ollama (Local, no API key needed):**

```bash
# Install Ollama: https://ollama.ai/
ollama pull llama3
export AI_PROVIDER=ollama
devcommit
```

**Using Custom API:**

```bash
export AI_PROVIDER=custom
export CUSTOM_API_URL='http://localhost:8000/v1'
export CUSTOM_API_KEY='your-key'
export CUSTOM_MODEL='your-model'
devcommit
```

## Configuration Reference

All configuration can be set via **environment variables** or **`.dcommit` file**:

### AI Provider Settings

| Variable      | Description             | Default  | Options                                                     |
| ------------- | ----------------------- | -------- | ----------------------------------------------------------- |
| `AI_PROVIDER` | Which AI service to use | `gemini` | `gemini`, `openai`, `groq`, `openrouter`, `anthropic`, `ollama`, `custom` |

### Provider-Specific Settings

**Gemini:**
| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | - |
| `GEMINI_MODEL` | Model name | `gemini-2.0-flash-exp` |

**OpenAI:**
| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | - |
| `OPENAI_MODEL` | Model name | `gpt-4o-mini` |

**Groq:**
| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key ([Get it here](https://console.groq.com/)) | - |
| `GROQ_MODEL` | Model name | `llama-3.3-70b-versatile` |

**OpenRouter:**
| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key ([Get it here](https://openrouter.ai/keys)) | - |
| `OPENROUTER_MODEL` | Model name (add `:free` suffix for free models) | `meta-llama/llama-3.3-70b-instruct:free` |

**Anthropic:**
| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `ANTHROPIC_MODEL` | Model name | `claude-3-haiku-20240307` |

**Ollama (Local):**
| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Model name | `llama3` |

**Custom (OpenAI-compatible):**
| Variable | Description | Default |
|----------|-------------|---------|
| `CUSTOM_API_URL` | API endpoint URL | - |
| `CUSTOM_API_KEY` | API key (optional) | - |
| `CUSTOM_MODEL` | Model name | `default` |

### General Settings

| Variable        | Description                          | Default                                                | Options                                  |
| --------------- | ------------------------------------ | ------------------------------------------------------ | ---------------------------------------- |
| `LOCALE`        | Language for commit messages         | `en-US`                                                | Any locale code (e.g., `en`, `es`, `fr`) |
| `MAX_NO`        | Number of commit message suggestions | `1`                                                    | Any positive integer                     |
| `COMMIT_TYPE`   | Style of commit messages             | `general`                                              | `general`, `conventional`, etc.          |
| `COMMIT_MODE`   | Default commit strategy              | `auto`                                                 | `auto`, `directory`, `global`, `related` |
| `EXCLUDE_FILES` | Files to exclude from diff           | `package-lock.json, pnpm-lock.yaml, yarn.lock, *.lock` | Comma-separated file patterns            |
| `MAX_TOKENS`    | Maximum tokens for AI response       | `8192`                                                 | Any positive integer                     |
| `CHANGELOG_DIR` | Directory for changelog files        | `changelogs`                                           | Any directory path                       |

### Configuration Priority

1. **`.dcommit` file** (highest priority)
2. **Environment variables**
3. **Built-in defaults** (lowest priority)

### Using Environment Variables

```bash
# Basic setup with Gemini (default)
export GEMINI_API_KEY='your-api-key-here'
export COMMIT_MODE='directory'
export COMMIT_TYPE='conventional'

# Or use Groq (faster, free)
export AI_PROVIDER='groq'
export GROQ_API_KEY='your-groq-key'

# Add to ~/.bashrc for persistence
```

### Using .dcommit File

See `.dcommit.example` for a complete configuration template with all providers.

**Note:** The `.dcommit` file is **optional**. DevCommit will work with just environment variables!
