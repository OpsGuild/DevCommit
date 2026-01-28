#!/usr/bin/env python3
"""Git utilities"""

import os
import subprocess
from collections import defaultdict
from typing import Dict, List, Optional


class KnownError(Exception):
    pass


def assert_git_repo() -> str:
    """
    Asserts that the current directory is a Git repository.
    Returns the top-level directory path of the repository.
    """

    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        raise KnownError('The current directory must be a Git repository!')


def exclude_from_diff(path: str) -> str:
    """
    Prepares a Git exclusion path string for the diff command.
    """

    return f':(exclude){path}'


def get_default_excludes() -> List[str]:
    """
    Get list of files to exclude from diff.
    Priority: Config > Defaults
    """
    try:
        from devcommit.utils.logger import config
        
        # Get from config (supports comma-separated list)
        exclude_config = config("EXCLUDE_FILES", default="")
        
        if exclude_config:
            # Parse comma-separated values and strip whitespace
            config_excludes = [f.strip() for f in exclude_config.split(",") if f.strip()]
            return config_excludes
    except:
        pass
    
    # No default exclusions; rely entirely on user configuration.
    return []


# Get default files to exclude (can be overridden via config)
files_to_exclude = get_default_excludes()


def get_staged_diff(
        exclude_files: Optional[List[str]] = None) -> Optional[dict]:
    """
    Gets the list of staged files and their diff, excluding specified files.
    """
    exclude_files = exclude_files or []
    diff_cached = ['git', 'diff', '--cached', '--diff-algorithm=minimal']
    excluded_from_diff = (
        [exclude_from_diff(f) for f in files_to_exclude + exclude_files])

    try:
        # Get the list of staged files excluding specified files
        files = subprocess.run(
            diff_cached + ['--name-only'] + excluded_from_diff,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        files_result = (
            files.stdout.strip().split('\n') if files.stdout.strip() else []
        )
        if not files_result:
            return None

        # Get the staged diff excluding specified files
        diff = subprocess.run(
            diff_cached + excluded_from_diff,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        diff_result = diff.stdout.strip()

        return {
            'files': files_result,
            'diff': diff_result
        }
    except subprocess.CalledProcessError:
        return None


def get_detected_message(files: List[str]) -> str:
    """
    Returns a message indicating the number of staged files.
    """
    return (
        f"Detected {len(files):,} staged file{'s' if len(files) > 1 else ''}"
    )


def group_files_by_directory(files: List[str]) -> Dict[str, List[str]]:
    """
    Groups files by their root directory (first-level directory).
    Files in the repository root are grouped under 'root'.
    """
    grouped = defaultdict(list)
    
    for file_path in files:
        # Get the first directory in the path
        parts = file_path.split(os.sep)
        if len(parts) > 1:
            root_dir = parts[0]
        else:
            root_dir = 'root'
        grouped[root_dir].append(file_path)
    
    return dict(grouped)


def get_diff_for_files(files: List[str], exclude_files: Optional[List[str]] = None) -> str:
    """
    Gets the diff for specific files.
    """
    exclude_files = exclude_files or []
    
    # Filter out excluded files from the list
    all_excluded = files_to_exclude + exclude_files
    filtered_files = [
        f for f in files 
        if not any(f.endswith(excl.replace('*', '')) or excl.replace(':(exclude)', '') in f 
                   for excl in all_excluded)
    ]
    
    if not filtered_files:
        return ""
    
    try:
        diff = subprocess.run(
            ['git', 'diff', '--cached', '--diff-algorithm=minimal', '--'] + filtered_files,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return diff.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def get_files_from_paths(paths: List[str]) -> List[str]:
    """
    Gets all files from given paths (handles both files and directories).
    Returns a list of file paths relative to the repository root.
    """
    repo_root = assert_git_repo()
    all_files = []
    
    for path in paths:
        # Normalize path
        normalized_path = os.path.normpath(path)
        full_path = os.path.join(repo_root, normalized_path) if not os.path.isabs(path) else path
        
        if not os.path.exists(full_path):
            raise KnownError(f"Path does not exist: {path}")
        
        if os.path.isfile(full_path):
            # It's a file, get relative path
            rel_path = os.path.relpath(full_path, repo_root)
            all_files.append(rel_path)
        elif os.path.isdir(full_path):
            # It's a directory, get all files in it
            try:
                result = subprocess.run(
                    ['git', 'ls-files', '--', normalized_path],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=repo_root
                )
                files_in_dir = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
                all_files.extend(files_in_dir)
            except subprocess.CalledProcessError:
                # If git ls-files fails, try to find files manually
                for root, dirs, files in os.walk(full_path):
                    # Skip .git directories
                    if '.git' in dirs:
                        dirs.remove('.git')
                    for file in files:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, repo_root)
                        all_files.append(rel_path)
    
    # Remove duplicates and return
    return list(set(all_files))


def stage_files(files: List[str]) -> None:
    """
    Stages specific files.
    """
    if not files:
        return
    
    try:
        subprocess.run(
            ['git', 'add', '--'] + files,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except subprocess.CalledProcessError as e:
        raise KnownError(f"Failed to stage files: {e.stderr}")


def get_current_branch() -> str:
    """
    Gets the current git branch name.
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        raise KnownError("Failed to get current branch name")


def has_commits_to_push(branch: Optional[str] = None, remote: str = "origin") -> bool:
    """
    Checks if there are commits ahead of the remote that need to be pushed.
    Returns True if there are commits to push, False otherwise.
    """
    if branch is None:
        branch = get_current_branch()
    
    try:
        # Check if remote tracking branch exists
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', f'{branch}@{{upstream}}'],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        upstream = result.stdout.strip()
    except subprocess.CalledProcessError:
        # No upstream branch, assume we need to push
        return True
    
    try:
        # Check if local branch is ahead of remote
        result = subprocess.run(
            ['git', 'rev-list', '--count', f'{upstream}..{branch}'],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        ahead_count = int(result.stdout.strip())
        return ahead_count > 0
    except (subprocess.CalledProcessError, ValueError):
        # If we can't determine, assume we need to push
        return True


def push_to_remote(branch: Optional[str] = None, remote: str = "origin") -> None:
    """
    Pushes the current branch to the remote repository.
    """
    if branch is None:
        branch = get_current_branch()
    
    try:
        # Check if remote exists
        result = subprocess.run(
            ['git', 'remote', 'get-url', remote],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except subprocess.CalledProcessError:
        raise KnownError(f"Remote '{remote}' does not exist. Please add a remote first.")
    
    # Check if there are commits to push
    if not has_commits_to_push(branch, remote):
        return  # Nothing to push
    
    try:
        # Don't capture stdout/stderr to allow interactive prompts (e.g., for authentication)
        # This allows the user to see what's happening and enter credentials if needed
        subprocess.run(
            ['git', 'push', remote, branch],
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise KnownError(f"Failed to push to remote. Please check your authentication and try again.")


def generate_relation_grouping_prompt(files: List[str], diffs: Dict[str, str]) -> str:
    """
    Generate a comprehensive prompt for AI to analyze and group related files
    based on semantic relationships, feature context, and change intent.
    """
    num_files = len(files)
    
    prompt_parts = [
        "=" * 70,
        "TASK: INTELLIGENTLY GROUP CODE CHANGES INTO MINIMAL LOGICAL COMMITS",
        "=" * 70,
        "",
        "You are a senior software architect. Your goal is to analyze code changes and group them",
        "into the MINIMUM number of logical commits that make sense together.",
        "",
        f"You have {num_files} files to analyze. Your goal is to create as FEW groups as possible",
        "while keeping each group semantically coherent.",
        "",
        "⚠️  CRITICAL: DO NOT create one group per file! That defeats the entire purpose.",
        "⚠️  CRITICAL: Look for the BROADER PATTERN - what is the developer trying to accomplish?",
        "",
        "=" * 70,
        "GROUPING STRATEGY (Think like a code reviewer):",
        "=" * 70,
        "",
        "STEP 1: IDENTIFY THE BIG PICTURE",
        "   - What is the overall intent of these changes?",
        "   - Are these files part of a larger feature, batch addition, or refactoring?",
        "   - Would a code reviewer expect these files to be in the same PR/commit?",
        "",
        "STEP 2: GROUP AGGRESSIVELY",
        "   - Files added together as part of the same initiative = ONE GROUP",
        "   - Multiple config/data files of the same type = ONE GROUP", 
        "   - Example: Adding 10 new YAML command files = ONE GROUP 'add-command-definitions'",
        "   - Example: Adding docker.yaml, kubernetes.yaml, pm2.yaml = ONE GROUP 'add-devops-commands'",
        "   - Example: Schema + API + Migration + Tests for same entity = ONE GROUP",
        "",
        "STEP 3: SEPARATE BY DISTINCT INTENT",
        "   - Separate different KINDS of work (e.g. New Feature vs Bug Fix)",
        "   - A bug fix in module A + a new feature in module B = 2 groups",
        "   - Documentation updates only = separate group (unless part of a new feature)",
        "   - If two changes are unrelated, DO NOT force them together just to reduce groups",
        "",
        "=" * 70,
        "EXAMPLES OF CORRECT GROUPING:",
        "=" * 70,
        "",
        "EXAMPLE 1 - Adding multiple command/config files:",
        "  Files: repository/devops/docker.yaml, repository/devops/k8s.yaml,",
        "         repository/languages/python.yaml, repository/languages/go.yaml,",
        "         repository/security/ufw.yaml",
        "  WRONG: 5 separate groups (one per file) ❌",
        "  CORRECT: 1 group 'add-bundled-command-definitions' ✓",
        "  WHY: All files serve the same purpose - adding command definitions to the repository",
        "",
        "EXAMPLE 2 - New feature with multiple components:",
        "  Files: models/user.py, api/users.py, tests/test_users.py, migrations/001_users.sql",
        "  WRONG: 4 separate groups ❌",
        "  CORRECT: 1 group 'add-user-management' ✓",
        "  WHY: All files are part of implementing the user feature",
        "",
        "EXAMPLE 3 - Mixed changes (separate ONLY when purposes differ):",
        "  Files: models/user.py, api/users.py (new feature)",
        "         scripts/deploy.sh (unrelated script fix)",
        "  CORRECT: 2 groups - 'add-user-feature' and 'fix-deploy-script' ✓",
        "  WHY: These serve genuinely different purposes",
        "",
        "EXAMPLE 4 - Documentation updates:",
        "  Files: README.md, docs/SETUP.md, docs/API.md, docs/GUIDE.md",
        "  WRONG: 4 separate groups ❌",
        "  CORRECT: 1 group 'update-documentation' ✓",
        "  WHY: All documentation changes should be together",
        "",
        "=" * 70,
        "SIGNALS THAT FILES BELONG TOGETHER:",
        "=" * 70,
        "",
        "- Same parent directory or related directories (e.g., repository/devops/*, repository/languages/*)",
        "- Same file extension/type being added (e.g., multiple .yaml, .json, .md files)",
        "- Same naming pattern (e.g., *_controller.py, *_service.py for same entity)",
        "- Part of the same feature (model + controller + test + migration)",
        "- Added in the same 'batch' - multiple new files of similar purpose",
        "- Import relationships between files",
        "- Same entity/domain being modified",
        "",
        "=" * 70,
        "ANTI-PATTERNS TO AVOID:",
        "=" * 70,
        "",
        "❌ Creating one group per file (defeats the purpose of grouping!)",
        "❌ Grouping by file extension only (all .py together, all .yaml together)",
        "❌ Grouping by exact directory (each subdirectory as separate group)",
        "❌ Being too granular - ask 'would a reviewer want these separate?'",
        "",
        "✓ Group by INTENT and PURPOSE",
        "✓ Group by WHAT the changes accomplish TOGETHER",
        "✓ Be AGGRESSIVE about grouping - fewer commits is usually better",
        "✓ Aim for 2-5 groups typically, not 10+ groups",
        "",
        "=" * 70,
        f"FILES TO ANALYZE ({num_files} files):",
        "=" * 70,
    ]
    
    for file_path in files:
        prompt_parts.append(f"  - {file_path}")
    
    prompt_parts.append("")
    prompt_parts.append("=" * 60)
    prompt_parts.append("FILE DIFFS (analyze content for relationships):")
    prompt_parts.append("=" * 60)
    prompt_parts.append("")
    
    for file_path, diff in diffs.items():
        # Truncate very long diffs but keep enough context for analysis
        truncated_diff = diff[:3000] + "\n... [truncated]" if len(diff) > 3000 else diff
        prompt_parts.append(f"### FILE: {file_path}")
        prompt_parts.append("```diff")
        prompt_parts.append(truncated_diff)
        prompt_parts.append("```")
        prompt_parts.append("")
    
    # Get commit type and MAX_NO configuration
    try:
        from devcommit.utils.logger import config as get_config
        commit_type = get_config("COMMIT_TYPE", default="normal")
        max_no = get_config("MAX_NO", default=1, cast=int)
    except:
        commit_type = "normal"
        max_no = 1
    
    commit_format_instruction = ""
    if commit_type == "conventional":
        commit_format_instruction = """
- 'commit_messages': Array of EXACTLY {max_no} conventional commit messages in format: <type>(<scope>): <description>
  Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert
  Each message should be a different variation/perspective of the same change
  Example for max_no=3: ["feat(auth): add JWT token refresh", "feat(auth): implement token refresh mechanism", "feat(auth): enable automatic token renewal"]
""".format(max_no=max_no)
    else:
        commit_format_instruction = """
- 'commit_messages': Array of EXACTLY {max_no} clear, concise git commit messages (imperative mood, max 72 chars)
  Each message should be a different variation/perspective of the same change
  Example for max_no=3: ["Add user authentication with JWT tokens", "Implement JWT-based user authentication", "Add JWT token authentication system"]
""".format(max_no=max_no)
    
    # Calculate suggested max groups based on file count
    suggested_max_groups = max(2, min(5, num_files // 3))
    
    prompt_parts.extend([
        "=" * 70,
        "OUTPUT REQUIREMENTS:",
        "=" * 70,
        "",
        f"⚠️  TARGET: Create {suggested_max_groups} or fewer groups for these {num_files} files.",
        f"⚠️  Having {num_files} groups (one per file) is WRONG. Group aggressively!",
        "",
        "Respond with ONLY a JSON array. Each group should have:",
        "- 'group': A descriptive kebab-case name (e.g., 'add-bundled-command-sets', 'update-documentation')",
        "- 'files': Array of ALL file paths that belong together (use EXACT paths from input)",
        "- 'description': One sentence describing what ALL these files accomplish TOGETHER",
        "- 'type': One of 'feature', 'bugfix', 'refactor', 'config', 'docs', 'test', 'chore'",
        commit_format_instruction,
        "",
        "EXAMPLE - Given 14 YAML config files in repository/*, create 1-2 groups, NOT 14:",
        '[',
        '  {',
        '    "group": "add-bundled-command-definitions",',
        '    "files": ["repository/devops/docker.yaml", "repository/devops/k8s.yaml", "repository/languages/python.yaml", "repository/languages/go.yaml", "repository/security/ufw.yaml", "...all other yaml files..."],',
        '    "description": "Add comprehensive set of bundled command definitions for devops, languages, and security tools",',
        '    "type": "feature",',
        '    "commit_messages": ' + (
            '["feat(repo): add bundled command definitions", "feat(commands): add devops, language, and security command sets", "feat: add comprehensive bundled command library"]' if commit_type == "conventional" else
            '["Add bundled command definitions for devops, languages, and security", "Add comprehensive set of command definitions to repository", "Add initial set of bundled command files"]'
        ),
        '  }',
        ']',
        "",
        "REMEMBER:",
        f"- You have {num_files} files. Aim for {suggested_max_groups} or fewer groups.",
        "- Multiple similar files (like YAML configs, or docs) = ONE group",
        "- Output ONLY the JSON array, no explanations, no markdown code blocks",
        "- Use the EXACT file paths from the input (copy them exactly)",
        "- Every file must appear in exactly one group"
    ])
    
    return "\n".join(prompt_parts)


def parse_relation_groups(ai_response: str, all_files: List[str]) -> Dict[str, Dict[str, any]]:
    """
    Parse AI response and return grouped files with descriptions.
    Falls back to intelligent grouping if parsing fails.
    """
    import json
    import re
    
    try:
        # Clean up the response - remove markdown code blocks if present
        cleaned = ai_response.strip()
        cleaned = re.sub(r'^```[\w]*\n?', '', cleaned)
        cleaned = re.sub(r'\n?```$', '', cleaned)
        cleaned = cleaned.strip()
        
        # Try to find JSON array in the response
        json_match = re.search(r'\[[\s\S]*\]', cleaned)
        if json_match:
            cleaned = json_match.group(0)
        
        groups_list = json.loads(cleaned)
        
        result = {}
        grouped_files = set()
        
        # Type emoji mapping for display
        type_emoji = {
            "feature": "✨",
            "bugfix": "🐛",
            "refactor": "♻️",
            "config": "⚙️",
            "docs": "📝",
            "test": "🧪",
            "chore": "🔧"
        }
        
        for group_data in groups_list:
            group_name = group_data.get("group", "unknown")
            files = group_data.get("files", [])
            description = group_data.get("description", "")
            change_type = group_data.get("type", "chore")
            
            # Handle both old format (commit_message) and new format (commit_messages array)
            commit_messages = group_data.get("commit_messages", [])
            if not commit_messages:
                # Fallback to old format
                single_message = group_data.get("commit_message", "")
                if single_message:
                    commit_messages = [single_message]
            
            # Validate files exist in our list (handle both exact match and normalized paths)
            valid_files = []
            for f in files:
                if f in all_files:
                    valid_files.append(f)
                else:
                    # Try normalized path matching
                    normalized = os.path.normpath(f)
                    for actual_file in all_files:
                        if os.path.normpath(actual_file) == normalized or actual_file.endswith(f) or f.endswith(actual_file):
                            valid_files.append(actual_file)
                            break
            
            # Remove duplicates while preserving order
            valid_files = list(dict.fromkeys(valid_files))
            
            if valid_files:
                # Ensure unique group names
                base_name = group_name
                counter = 1
                while group_name in result:
                    group_name = f"{base_name}-{counter}"
                    counter += 1
                
                emoji = type_emoji.get(change_type, "📦")
                result[group_name] = {
                    "files": valid_files,
                    "description": description,
                    "type": change_type,
                    "emoji": emoji,
                    "commit_messages": commit_messages  # Always an array
                }
                grouped_files.update(valid_files)
        
        # Handle any files not included in groups
        ungrouped = [f for f in all_files if f not in grouped_files]
        if ungrouped:
            # Try to create a meaningful name for ungrouped files
            result["miscellaneous-changes"] = {
                "files": ungrouped,
                "description": "Other changes not directly related to main features",
                "type": "chore",
                "emoji": "📦",
                "commit_messages": []  # Empty - will be generated later if needed
            }
        
        return result
        
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # Log the error for debugging but don't show to user
        import logging
        logger = logging.getLogger("__devcommit__")
        logger.debug(f"Failed to parse AI grouping response: {e}")
        logger.debug(f"AI response was: {ai_response[:500]}...")  # First 500 chars
        
        # Fallback: use intelligent grouping based on file patterns
        # Note: This fallback doesn't have pre-generated commit messages,
        # so they will be generated when the group is processed
        return _fallback_intelligent_grouping(all_files)


def _fallback_intelligent_grouping(files: List[str]) -> Dict[str, Dict[str, any]]:
    """
    Fallback grouping when AI parsing fails.
    Groups files based on common patterns and naming conventions.
    """
    import re
    
    groups = {}
    grouped_files = set()
    
    # Extract potential entity names from file paths
    entity_patterns = {}
    
    for file_path in files:
        # Get the base filename without extension
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Remove common prefixes/suffixes to find entity names
        # e.g., test_user -> user, user_controller -> user, UserModel -> User
        cleaned_name = re.sub(r'^(test_|spec_)', '', base_name, flags=re.IGNORECASE)
        cleaned_name = re.sub(r'(_test|_spec|_controller|_service|_model|_schema|_migration|_api|_route|_handler)$', '', cleaned_name, flags=re.IGNORECASE)
        cleaned_name = re.sub(r'(Controller|Service|Model|Schema|Migration|Api|Route|Handler|Test|Spec)$', '', cleaned_name)
        cleaned_name = cleaned_name.lower()
        
        if cleaned_name and len(cleaned_name) > 1:
            if cleaned_name not in entity_patterns:
                entity_patterns[cleaned_name] = []
            entity_patterns[cleaned_name].append(file_path)
    
    # Create groups from entity patterns (only if more than 1 file)
    for entity, entity_files in entity_patterns.items():
        if len(entity_files) > 1:
            group_name = f"{entity}-related"
            groups[group_name] = {
                "files": entity_files,
                "description": f"Changes related to {entity}",
                "type": "feature",
                "emoji": "📦",
                "commit_messages": []  # Empty - will be generated later if needed
            }
            grouped_files.update(entity_files)
    
    # Handle ungrouped files - group by directory
    ungrouped = [f for f in files if f not in grouped_files]
    if ungrouped:
        dir_groups = group_files_by_directory(ungrouped)
        for dir_name, dir_files in dir_groups.items():
            groups[f"{dir_name}-changes"] = {
                "files": dir_files,
                "description": f"Changes in {dir_name} directory",
                "type": "chore",
                "emoji": "📁",
                "commit_messages": []  # Empty - will be generated later if needed
            }
    
    return groups if groups else {
        "all-changes": {
            "files": files,
            "description": "All staged changes",
            "type": "chore",
            "emoji": "📦",
            "commit_messages": []  # Empty - will be generated later if needed
        }
    }
