#!/usr/bin/env python
"""Generate changelog files from git diffs using AI"""

import os
import re
from datetime import datetime
from typing import List, Tuple

from devcommit.app.ai_providers import get_ai_provider
from devcommit.utils.git import get_current_branch
from devcommit.utils.logger import config

PLACEHOLDER_LINES = {
    "list new features",
    "list changes to existing functionality",
    "list bug fixes",
    "list removed features",
    "none",
    "n/a",
    "na",
    "no changes",
}

DEFAULT_CHANGELOG_MODE = "timestamped"
BRANCH_CHANGELOG_MODES = {"branch", "branch_single", "single", "per_branch"}


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
7. Include only sections that have real content
8. Use ## [Unreleased] only when it contains at least one non-empty subsection

Format:
# Changelog

## [Unreleased] (optional)

### Added (optional)
- Describe added features (only if any)

### Changed (optional)
- Describe changed behavior (only if any)

Do not include empty section headings or placeholders."""


def _strip_fences(content: str) -> str:
    lines = content.strip().splitlines()
    if len(lines) >= 2 and lines[0].strip().startswith("```"):
        if lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return content.strip()


def _split_by_heading(
    lines: List[str], level: int
) -> Tuple[List[str], List[Tuple[str, List[str]]]]:
    """Split content by markdown heading level."""
    heading_prefix = "#" * level + " "
    preamble: List[str] = []
    sections: List[Tuple[str, List[str]]] = []
    current_heading: str | None = None
    current_body: List[str] = []

    for line in lines:
        if line.startswith(heading_prefix):
            if current_heading is not None:
                sections.append((current_heading.strip(), current_body))
            current_heading = line
            current_body = []
            continue

        if current_heading is None:
            preamble.append(line)
        else:
            current_body.append(line)

    if current_heading is not None:
        sections.append((current_heading.strip(), current_body))

    return preamble, sections


def _strip_blank_edges(lines: List[str]) -> List[str]:
    start = 0
    end = len(lines)

    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1

    return lines[start:end]


def _is_placeholder_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped in {"-", "*", "+"}:
        return True

    candidate = stripped
    for marker in ("- ", "* ", "+ "):
        if candidate.startswith(marker):
            candidate = candidate[len(marker) :].strip()
            break

    candidate_lower = candidate.lower().rstrip(".")
    if candidate_lower in PLACEHOLDER_LINES:
        return True

    if re.fullmatch(r"(none|no changes|n/?a)\.?$", candidate_lower):
        return True

    return False


def _has_informative_content(lines: List[str]) -> bool:
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if _is_placeholder_line(stripped):
            continue
        return True
    return False


def _clean_second_level_body(lines: List[str]) -> List[str]:
    intro, subsections = _split_by_heading(lines, 3)
    cleaned: List[str] = []
    kept_subsections: List[Tuple[str, List[str]]] = []

    for heading, body in subsections:
        body = _strip_blank_edges(body)
        if _has_informative_content(body):
            kept_subsections.append((heading, body))

    intro = _strip_blank_edges(intro)
    keep_intro = _has_informative_content(intro)
    if not keep_intro and not kept_subsections:
        return []

    if keep_intro:
        cleaned.extend(intro)

    for index, (heading, body) in enumerate(kept_subsections):
        if cleaned:
            cleaned.append("")
        cleaned.append(heading)
        cleaned.extend(body)
        if index < len(kept_subsections) - 1:
            cleaned.append("")

    return cleaned


def normalize_changelog_content(content: str) -> str:
    """Normalize AI output and remove empty sections/placeholders."""
    content = _strip_fences(content)
    raw_lines = _strip_blank_edges(content.splitlines())
    if not raw_lines:
        return "# Changelog"

    title = "# Changelog"
    body_lines = raw_lines
    if raw_lines[0].startswith("# "):
        title = raw_lines[0].strip()
        body_lines = _strip_blank_edges(raw_lines[1:])

    _, sections = _split_by_heading(body_lines, 2)
    rebuilt_lines: List[str] = [title]

    if sections:
        kept_sections: List[Tuple[str, List[str]]] = []
        for heading, body in sections:
            cleaned_body = _clean_second_level_body(body)
            if cleaned_body:
                kept_sections.append((heading, cleaned_body))

        if kept_sections:
            rebuilt_lines.append("")
            for index, (heading, body) in enumerate(kept_sections):
                rebuilt_lines.append(heading)
                rebuilt_lines.extend(body)
                if index < len(kept_sections) - 1:
                    rebuilt_lines.append("")
    else:
        body_lines = _strip_blank_edges(body_lines)
        if _has_informative_content(body_lines):
            rebuilt_lines.append("")
            rebuilt_lines.extend(body_lines)

    return "\n".join(_strip_blank_edges(rebuilt_lines)) + "\n"


def _to_section_name(heading: str) -> str:
    return heading.removeprefix("###").strip()


def _extract_category_blocks(content: str) -> List[Tuple[str, List[str]]]:
    """Extract non-empty category blocks from normalized changelog content."""
    lines = _strip_blank_edges(content.splitlines())
    if lines and lines[0].startswith("# "):
        lines = _strip_blank_edges(lines[1:])

    _, sections = _split_by_heading(lines, 2)
    category_items: List[Tuple[str, List[str]]] = []

    for _, section_body in sections:
        section_intro, subsections = _split_by_heading(section_body, 3)
        if subsections:
            for heading, body in subsections:
                body = _strip_blank_edges(body)
                if _has_informative_content(body):
                    category_items.append((_to_section_name(heading), body))
            continue

        section_intro = _strip_blank_edges(section_intro)
        if _has_informative_content(section_intro):
            category_items.append(("Changed", section_intro))

    if category_items:
        preferred_order = [
            "Added",
            "Changed",
            "Fixed",
            "Removed",
            "Deprecated",
            "Security",
        ]
        ordered: List[Tuple[str, List[str]]] = []
        used_indices: set[int] = set()

        for name in preferred_order:
            for idx, item in enumerate(category_items):
                if idx in used_indices:
                    continue
                category_name, _ = item
                if category_name.lower() == name.lower():
                    ordered.append(item)
                    used_indices.add(idx)

        for idx, item in enumerate(category_items):
            if idx not in used_indices:
                ordered.append(item)

        return ordered

    return category_items


def _strip_top_heading(content: str) -> str:
    lines = _strip_blank_edges(content.splitlines())
    if lines and lines[0].startswith("# "):
        return "\n".join(_strip_blank_edges(lines[1:]))
    return "\n".join(lines)


def _save_timestamped_changelog(
    content: str, directory: str, branch_name: str, now: datetime
) -> str:
    year_directory = now.strftime("%Y")
    month_directory = now.strftime("%m")
    day_directory = now.strftime("%d")
    target_directory = os.path.join(
        directory, branch_name, year_directory, month_directory, day_directory
    )
    os.makedirs(target_directory, exist_ok=True)

    filename = now.strftime("%H-%M-%S.md")
    filepath = os.path.join(target_directory, filename)

    with open(filepath, "w", encoding="utf-8") as file:
        file.write(content)

    return filepath


def _save_branch_changelog(
    content: str, directory: str, branch_name: str, now: datetime
) -> str:
    os.makedirs(directory, exist_ok=True)
    filepath = os.path.join(directory, f"{branch_name}.md")

    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    categories = _extract_category_blocks(content)
    entry_lines: List[str] = [f"## [{timestamp}]"]

    if categories:
        for section_name, section_lines in categories:
            entry_lines.append("")
            entry_lines.append(f"### {section_name}")
            entry_lines.extend(section_lines)
    else:
        content_body = _strip_top_heading(content)
        if content_body.strip():
            entry_lines.append("")
            entry_lines.extend(content_body.splitlines())

    new_entry = "\n".join(_strip_blank_edges(entry_lines)).strip()

    previous_body = ""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as file:
            previous_body = _strip_top_heading(file.read()).strip()

    output_lines = ["# Changelog", "", new_entry]
    if previous_body:
        output_lines.extend(["", previous_body])

    with open(filepath, "w", encoding="utf-8") as file:
        file.write("\n".join(_strip_blank_edges(output_lines)) + "\n")

    return filepath


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

    return normalize_changelog_content(changelog_content)


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

    changelog_mode = (
        config("CHANGELOG_MODE", default=DEFAULT_CHANGELOG_MODE).strip().lower()
    )
    normalized_content = normalize_changelog_content(content)

    now = datetime.now()
    branch_name = get_current_branch().replace("/", "-")
    if changelog_mode in BRANCH_CHANGELOG_MODES:
        return _save_branch_changelog(
            normalized_content, directory, branch_name, now
        )

    return _save_timestamped_changelog(
        normalized_content, directory, branch_name, now
    )
