#!/usr/bin/env python
"""Generate changelog files from git diffs using AI"""

import os
from datetime import datetime

from devcommit.app.ai_providers import get_ai_provider
from devcommit.utils.logger import config


def generate_changelog_prompt() -> str:
    """Generate the prompt for changelog creation"""
    return """You are a changelog generator. Analyze the git diff and create a structured changelog in Keep a Changelog format.

Follow these guidelines:
1. Use markdown format with clear sections
2. Categorize changes into: Added, Changed, Fixed, Removed, Deprecated, Security
3. Write clear, user-friendly descriptions (not implementation details)
4. Group related changes together
5. Focus on what changed from a user/developer perspective
6. Be concise but informative

Format:
# Changelog

## [Unreleased]

### Added
- List new features

### Changed
- List changes to existing functionality

### Fixed
- List bug fixes

### Removed
- List removed features

Only include sections that have changes. Do not add empty sections."""


def generate_changelog(diff: str) -> str:
    """Generate changelog content from git diff using AI.

    Args:
        diff: Git diff string

    Returns:
        Formatted markdown changelog content
    """
    prompt = generate_changelog_prompt()

    provider = get_ai_provider(config)

    max_tokens = config("MAX_TOKENS", default=8192, cast=int)
    changelog_content = provider.generate_commit_message(
        diff, prompt, max_tokens
    )

    return changelog_content


def save_changelog(content: str, directory: str = None) -> str:
    """Save changelog content to a file.

    Args:
        content: Changelog markdown content
        directory: Directory to save changelog (default from config)

    Returns:
        Path to the saved changelog file
    """
    if directory is None:
        directory = config("CHANGELOG_DIR", default="changelogs")

    now = datetime.now()
    year_directory = now.strftime("%Y")
    month_directory = now.strftime("%m")
    target_directory = os.path.join(directory, year_directory, month_directory)

    # Create the year/month directory structure if it doesn't exist
    os.makedirs(target_directory, exist_ok=True)

    filename = now.strftime("%Y-%m-%d_%H-%M-%S.md")
    filepath = os.path.join(target_directory, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath
