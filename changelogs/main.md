# Changelog

## [2026-10-23 05:56:44]

### Added
- **Git Alias Support**: You can now use a custom Git alias instead of the default `git commit` command. Configure it via the `--commit-alias` command-line flag or set `GIT_COMMIT_ALIAS` in your configuration file (e.g., `~/.dcommit`).
- **Commit Alias Validation**: DevCommit now verifies that the specified Git alias is properly configured before attempting to commit, preventing runtime errors.
- **Documentation**: Added a dedicated section in the README explaining how to configure and use Git commit aliases, including examples for setting a default alias.

### Changed
- **Refactored Commit Logic**: Centralized the commit execution process into a single `commit_changes` utility function. This simplifies the codebase and ensures consistent behavior across all commit modes (global, directory, file, and related-group).
- **Configuration Table Updates**: Updated the General Settings configuration table in the README to document the new `GIT_COMMIT_ALIAS` variable and its default value.
- **Formatting Improvements**: Minor formatting and alignment fixes applied to various Markdown tables and lists in the README for better readability.

## [2026-09-18 03:28:34]

### Changed
- Bumped project version to 0.1.5.7.
