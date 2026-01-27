import os
import subprocess

# Suppress Google gRPC/ALTS warnings before any imports
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '3'
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '1'

from InquirerPy import get_style, inquirer
from rich.console import Console

from devcommit.app.gemini_ai import generateCommitMessage
from devcommit.utils.git import (KnownError, assert_git_repo,
                                 get_detected_message, get_diff_for_files,
                                 get_files_from_paths, get_staged_diff,
                                 group_files_by_directory, has_commits_to_push,
                                 push_to_remote, stage_files,
                                 generate_relation_grouping_prompt,
                                 parse_relation_groups)
from devcommit.utils.logger import Logger, config
from devcommit.utils.parser import CommitFlag, parse_arguments

logger_instance = Logger("__devcommit__")
logger = logger_instance.get_logger()


# Function to check if any commits exist
def has_commits() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0


def sanitize_commit_messages(messages):
    """Filter out error messages from commit message list.
    
    Args:
        messages: String or list of commit messages
        
    Returns:
        List of valid commit messages with error messages filtered out
    """
    # Convert string to list if needed
    if isinstance(messages, str):
        if not messages or messages.strip() == "":
            return []
        messages = messages.split("|")
    
    # Filter out error messages and empty strings
    valid_messages = []
    for msg in messages:
        if not msg:
            continue
        msg = msg.strip()
        # Skip if it's an error message
        if msg.startswith("Error generating commit message:"):
            continue
        if msg and msg.strip():
            valid_messages.append(msg)
    
    return valid_messages


# Main function
def main(flags: CommitFlag = None):
    if flags is None:
        flags = parse_arguments()

    try:
        assert_git_repo()
        console = Console()
        
        # Print stylish header with gradient effect
        console.print()
        console.print("╭" + "─" * 60 + "╮", style="bold cyan")
        console.print("│" + " " * 60 + "│", style="bold cyan")
        console.print("│" + "  🚀 [bold white on cyan] DevCommit [/bold white on cyan]  [bold white]AI-Powered Commit Generator[/bold white]".ljust(76) + "│", style="bold cyan")
        console.print("│" + " " * 60 + "│", style="bold cyan")
        console.print("╰" + "─" * 60 + "╯", style="bold cyan")
        
        # Display provider and model info
        provider = config("AI_PROVIDER", default="gemini").lower()
        model = ""
        
        # Helper to get model with fallback: provider-specific > MODEL_NAME > default
        def get_model(provider_key, fallback_default):
            provider_model = config(provider_key, default=None)
            if provider_model:
                return provider_model
            generic_model = config("MODEL_NAME", default=None)
            if generic_model:
                return generic_model
            return fallback_default
        
        if provider == "ollama":
            model = config("OLLAMA_MODEL", default="llama3")
        elif provider == "gemini":
            model = get_model("GEMINI_MODEL", "gemini-2.0-flash-exp")
        elif provider == "openai":
            model = get_model("OPENAI_MODEL", "gpt-4o-mini")
        elif provider == "groq":
            model = get_model("GROQ_MODEL", "llama-3.3-70b-versatile")
        elif provider == "openrouter":
            model = get_model("OPENROUTER_MODEL", "mistralai/devstral-2512:free")
        elif provider == "anthropic":
            model = get_model("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        elif provider == "custom":
            model = get_model("CUSTOM_MODEL", "default")
        
        console.print(f"[dim]Provider:[/dim] [bold magenta]{provider}[/bold magenta] [dim]│[/dim] [dim]Model:[/dim] [bold magenta]{model}[/bold magenta]")
        console.print()

        # Handle staging
        push_files_list = []
        original_paths = []  # Keep track of original paths (files or directories) passed
        if flags["files"] and len(flags["files"]) > 0:
            original_paths = flags["files"]
            
            # Get the list of files from paths first
            try:
                push_files_list = get_files_from_paths(flags["files"])
                if not push_files_list:
                    raise KnownError("No files found in the specified paths")
            except KnownError as e:
                raise e
            except Exception as e:
                raise KnownError(f"Failed to get files from paths: {str(e)}")

        if flags["stageAll"]:
            if push_files_list:
                # Stage specific files/folders only
                console.print("[bold cyan]📦 Staging specific files/folders...[/bold cyan]")
                console.print(f"[dim]Found {len(push_files_list)} file(s) to stage[/dim]")
                for file in push_files_list:
                    console.print(f"  [cyan]▸[/cyan] [white]{file}[/white]")
                
                stage_files(push_files_list)
                console.print("[bold green]✅ Files staged successfully[/bold green]\n")
            else:
                # Stage all changes
                stage_changes(console)
                console.print("[bold green]✅ All changes staged successfully[/bold green]\n")

        # Get staged files
        if push_files_list and len(push_files_list) > 0:
            if flags["stageAll"]:
                # If --files was used with --stageAll, we already staged those files
                # Create a staged dict with only those files
                staged = {
                    "files": push_files_list,
                    "diff": get_diff_for_files(push_files_list, flags["excludeFiles"])
                }
                if not staged["diff"]:
                    raise KnownError("No changes found in the specified files/folders")
                
                console.print(f"\n[bold green]✅ {get_detected_message(staged['files'])}[/bold green]")
                console.print("[dim]" + "─" * 60 + "[/dim]")
                for file in staged["files"]:
                    console.print(f"  [cyan]▸[/cyan] [white]{file}[/white]")
                console.print("[dim]" + "─" * 60 + "[/dim]")
            else:
                # If --files was used without --stageAll, filter staged files to only those specified
                # First, get all staged files (this will error if nothing is staged)
                all_staged = get_staged_diff(flags["excludeFiles"])
                if not all_staged:
                    raise KnownError(
                        "No staged changes found. Stage your changes manually, or "
                        "automatically stage specific files with the `--stageAll --files` flag."
                    )
                
                # Filter to only include files that match the specified paths
                filtered_files = []
                for staged_file in all_staged["files"]:
                    # Check if this staged file is in our push_files_list
                    if staged_file in push_files_list:
                        filtered_files.append(staged_file)
                
                if not filtered_files:
                    raise KnownError(
                        f"None of the specified files/folders are staged. "
                        f"Please stage them first with 'git add' or use '--stageAll --files'"
                    )
                
                # Create a staged dict with only the filtered files
                staged = {
                    "files": filtered_files,
                    "diff": get_diff_for_files(filtered_files, flags["excludeFiles"])
                }
                if not staged["diff"]:
                    raise KnownError("No changes found in the specified files/folders")
                
                console.print(f"\n[bold green]✅ {get_detected_message(staged['files'])}[/bold green]")
                console.print("[dim]" + "─" * 60 + "[/dim]")
                for file in staged["files"]:
                    console.print(f"  [cyan]▸[/cyan] [white]{file}[/white]")
                console.print("[dim]" + "─" * 60 + "[/dim]")
        else:
            staged = detect_staged_files(console, flags["excludeFiles"])
        
        # Determine commit strategy
        # Priority: CLI flag > config (file or env) > interactive prompt
        # Strategy can be: "global", "directory", "related", or None (to prompt)
        commit_strategy = None
        
        # Special handling when --files is used: check if we should use per-file commits
        is_files_mode = push_files_list and len(push_files_list) > 0
        
        # Check CLI flag first (--directory forces directory mode)
        if flags.get("directory", False):
            commit_strategy = "directory"
        
        # If not set via CLI, check config (file or environment variable)
        if commit_strategy is None:
            commit_mode = config("COMMIT_MODE", default="auto").lower()
            if commit_mode == "directory":
                commit_strategy = "directory"
            elif commit_mode == "global":
                commit_strategy = "global"
            elif commit_mode == "related":
                commit_strategy = "related"
            # If "auto" or not set, fall through to interactive prompt (commit_strategy stays None)
        
        # If still not set (auto mode), check if there are multiple directories and prompt
        if commit_strategy is None:
            if is_files_mode:
                # When --files is used with auto mode, always prompt
                # Group files to show directory structure, but prompt for strategy selection
                grouped = group_files_by_directory(staged["files"])
                console.print()
                console.print("╭" + "─" * 60 + "╮", style="bold yellow")
                console.print("│" + "  📂 [bold white]Files from multiple locations detected[/bold white]".ljust(70) + "│", style="bold yellow")
                console.print("╰" + "─" * 60 + "╯", style="bold yellow")
                console.print()
                console.print(f"  [dim]Found {len(staged['files'])} file(s) to commit[/dim]")
                console.print()
                # Prompt for strategy selection
                commit_strategy = prompt_commit_strategy(console, grouped, is_files_mode=True)
            else:
                # Regular auto mode: check directories
                grouped = group_files_by_directory(staged["files"])
                if len(grouped) > 1:
                    commit_strategy = prompt_commit_strategy(console, grouped, is_files_mode=False)
                else:
                    # Only one directory, default to global
                    commit_strategy = "global"
        
        # Track if any commits were made
        commit_made = False
        
        if commit_strategy == "related":
            # Use AI to group related changes together
            commit_made = process_per_related_commits(console, staged, flags)
        elif commit_strategy == "directory":
            # When --files is used with directory mode
            if is_files_mode:
                # Check if original paths were directories or individual files
                # If directories were passed, group by those directories
                # If individual files were passed, treat each file separately
                has_directories = False
                if original_paths:
                    repo_root = assert_git_repo()
                    for path in original_paths:
                        normalized_path = os.path.normpath(path)
                        full_path = os.path.join(repo_root, normalized_path) if not os.path.isabs(path) else path
                        if os.path.isdir(full_path):
                            has_directories = True
                            break
                
                if has_directories:
                    # Group files by the original directories passed
                    commit_made = process_per_directory_commits_from_paths(console, staged, flags, original_paths)
                else:
                    # Individual files passed, treat each file separately
                    commit_made = process_per_file_commits(console, staged, flags)
            else:
                commit_made = process_per_directory_commits(console, staged, flags)
        else:
            # Global mode (default): Pass staged dict so process_global_commit knows which files to commit
            # (important when --files is used)
            commit_made = process_global_commit(console, flags, staged=staged)
        
        # Handle push if requested and a commit was actually made
        if flags.get("push", False) and commit_made:
            push_changes(console)
        elif flags.get("push", False) and not commit_made:
            console.print("\n[bold yellow]⚠️  No commits were made, skipping push[/bold yellow]\n")
        
        # Print stylish completion message only if commits were made
        if commit_made:
            console.print()
            console.print("╭" + "─" * 60 + "╮", style="bold green")
            console.print("│" + " " * 60 + "│", style="bold green")
            console.print("│" + "     ✨ [bold white]All commits completed successfully![/bold white] ✨     ".ljust(68) + "│", style="bold green")
            console.print("│" + " " * 60 + "│", style="bold green")
            console.print("╰" + "─" * 60 + "╯", style="bold green")
            console.print()

    except KeyboardInterrupt:
        console.print("\n\n[bold yellow]⚠️  Operation cancelled by user[/bold yellow]\n")
        return
    except KnownError as error:
        logger.error(str(error))
        # Don't print here - Rich status context already displays the error
        pass
    except subprocess.CalledProcessError as error:
        logger.error(str(error))
        console.print(f"\n[bold red]❌ Git command failed:[/bold red] [red]{error}[/red]\n")
    except Exception as error:
        logger.error(str(error))
        console.print(f"\n[bold red]❌ Unexpected error:[/bold red] [red]{error}[/red]\n")


def stage_changes(console):
    with console.status(
        "[cyan]🔄 Staging changes...[/cyan]",
        spinner="dots",
        spinner_style="cyan"
    ):
        subprocess.run(["git", "add", "--all"], check=True)


def detect_staged_files(console, exclude_files):
    with console.status(
        "[cyan]🔍 Detecting staged files...[/cyan]",
        spinner="dots",
        spinner_style="cyan"
    ):
        staged = get_staged_diff(exclude_files)
        if not staged:
            raise KnownError(
                "No staged changes found. Stage your changes manually, or "
                "automatically stage all changes with the `--stageAll` flag."
            )
        console.print(
            f"\n[bold green]✅ {get_detected_message(staged['files'])}[/bold green]"
        )
        console.print("[dim]" + "─" * 60 + "[/dim]")
        for file in staged["files"]:
            console.print(f"  [cyan]▸[/cyan] [white]{file}[/white]")
        console.print("[dim]" + "─" * 60 + "[/dim]")
        return staged


def analyze_changes(console, files=None):
    """Analyze changes for commit message generation.
    
    Args:
        console: Rich console for output
        files: Optional list of specific files to analyze. If None, analyzes all staged files.
    """
    import sys
    
    # Store any exception to re-raise after status context exits
    caught_exception = None
    
    with console.status(
        "[magenta]🤖 AI analyzing changes...[/magenta]",
        spinner="dots",
        spinner_style="magenta"
    ):
        if files:
            # Analyze only specific files
            diff = get_diff_for_files(files)
        else:
            # Analyze all staged files
            diff = subprocess.run(
                ["git", "diff", "--staged"],
                stdout=subprocess.PIPE,
                text=True,
            ).stdout

        if not diff:
            raise KnownError(
                "No diff could be generated. Ensure you have changes staged."
            )

        # Suppress stderr during AI call to hide ALTS warnings
        _stderr = sys.stderr
        _devnull = open(os.devnull, 'w')
        sys.stderr = _devnull
        
        try:
            commit_message = generateCommitMessage(diff)
        except KnownError as e:
            # Catch KnownError to prevent Rich status from printing it
            caught_exception = e
            commit_message = None
        finally:
            sys.stderr = _stderr
            _devnull.close()
        
        # If we caught an exception, we'll re-raise it after the status context exits
        if caught_exception:
            pass  # Will be raised below
        else:
            commit_message = sanitize_commit_messages(commit_message)

            if not commit_message:
                raise KnownError("No commit messages were generated. Try again.")
    
    # Re-raise the exception outside the status context to avoid duplicate printing
    if caught_exception:
        raise caught_exception
    
    return commit_message


def prompt_commit_message(console, commit_message, regenerate_callback=None):
    """Prompt user to select a commit message.
    
    Args:
        console: Rich console for output
        commit_message: List of generated commit messages
        regenerate_callback: Optional function to call when regenerate is selected.
                            Should return a new list of commit messages.
    
    Returns:
        Selected commit message string, "regenerate" to regenerate, or None if cancelled
    """
    tag = (
        "Select commit message"
        if len(commit_message) > 1
        else "Confirm commit message"
    )
    style = get_style({
        "question": "#00d7ff bold",
        "questionmark": "#00d7ff bold",
        "pointer": "#00d7ff bold",
        "instruction": "#7f7f7f",
        "answer": "#00d7ff bold",
        "fuzzy_info": ""  # Hide the counter
    }, style_override=False)
    
    console.print()
    console.print("[bold cyan]📝 Generated Commit Messages:[/bold cyan]")
    console.print()
    
    # Add numbered options (plain text since InquirerPy doesn't support ANSI in choices)
    numbered_choices = []
    for idx, msg in enumerate(commit_message, 1):
        if isinstance(msg, str):
            numbered_choices.append({"name": f"  {idx}. {msg}", "value": msg})
        else:
            numbered_choices.append(msg)
    
    choices = [
        *numbered_choices,
        {"name": "  ✏️  Enter custom message", "value": "custom"},
    ]
    
    # Add regenerate option if callback is provided
    if regenerate_callback:
        choices.append({"name": "  🔄 Regenerate commit messages", "value": "regenerate"})
    
    choices.append({"name": "  ❌ Cancel", "value": "cancel"})
    
    action = inquirer.fuzzy(
        message=tag,
        style=style,
        choices=choices,
        default=None,
        instruction="(Type to filter or use arrows)",
        qmark="❯",
        info=False  # Disable info/counter
    ).execute()

    if action == "cancel":
        console.print("\n[bold yellow]⚠️  Commit cancelled[/bold yellow]\n")
        return None
    elif action == "custom":
        return prompt_custom_message(console)
    elif action == "regenerate":
        return "regenerate"
    return action


def prompt_custom_message(console):
    """Prompt user to enter a custom commit message."""
    console.print()
    console.print("[bold cyan]✏️  Enter your custom commit message:[/bold cyan]")
    console.print()
    
    style = get_style({
        "question": "#00d7ff bold",
        "questionmark": "#00d7ff bold",
        "pointer": "#00d7ff bold",
        "instruction": "#7f7f7f",
        "answer": "#00d7ff bold"
    }, style_override=False)
    
    custom_message = inquirer.text(
        message="Commit message:",
        style=style,
        qmark="❯",
        validate=lambda result: len(result.strip()) > 0,
        filter=lambda result: result.strip()
    ).execute()
    
    if not custom_message:
        console.print("\n[bold yellow]⚠️  No message entered, commit cancelled[/bold yellow]\n")
        return None
    
    return custom_message


def commit_changes(console, commit, raw_argv, files=None):
    """Commit changes.
    
    Args:
        console: Rich console for output
        commit: Commit message
        raw_argv: Additional git commit arguments
        files: Optional list of specific files to commit. If None, commits all staged files.
    """
    if files:
        # Commit only specific files
        subprocess.run(["git", "commit", "-m", commit, *raw_argv, "--"] + files)
    else:
        # Commit all staged files
        subprocess.run(["git", "commit", "-m", commit, *raw_argv])
    console.print("\n[bold green]✅ Committed successfully![/bold green]")


def push_changes(console):
    """Push commits to remote repository."""
    # Check if there are commits to push first
    try:
        if not has_commits_to_push():
            console.print("\n[bold yellow]ℹ️  No commits to push (already up to date)[/bold yellow]\n")
            return
    except KnownError:
        # If we can't determine, try to push anyway
        pass
    
    console.print("\n[cyan]🚀 Pushing to remote...[/cyan]")
    console.print("[dim]Note: You may be prompted for authentication[/dim]\n")
    
    try:
        # Run push with stdin/stdout/stderr connected to terminal
        # This allows interactive prompts (authentication) to work properly
        result = subprocess.run(
            ['git', 'push'],
            check=False,  # Don't raise on error, we'll check return code
            stdin=None,   # Inherit stdin for interactive prompts
            stdout=None,  # Don't capture stdout - let it show in terminal
            stderr=None   # Don't capture stderr - let it show in terminal
        )
        
        if result.returncode == 0:
            console.print("\n[bold green]✅ Pushed to remote successfully![/bold green]")
        else:
            raise KnownError("Push failed. Please check the output above for details.")
    except FileNotFoundError:
        raise KnownError("Git command not found. Please ensure git is installed.")
    except Exception as e:
        if isinstance(e, KnownError):
            raise
        raise KnownError(f"Push failed: {str(e)}")


def prompt_commit_strategy(console, grouped, is_files_mode=False):
    """Prompt user to choose between global, directory-based, or related-changes commits.
    
    Args:
        console: Rich console for output
        grouped: Dictionary of directories and their files
        is_files_mode: If True, directory mode means per-file commits (when --files is used)
    
    Returns:
        - "global": One commit for all changes
        - "directory": Separate commits per directory (or per-file in files mode)
        - "related": Group related changes together using AI analysis
    """
    console.print()
    console.print("╭" + "─" * 60 + "╮", style="bold yellow")
    console.print("│" + "  📂 [bold white]Multiple directories detected[/bold white]".ljust(70) + "│", style="bold yellow")
    console.print("╰" + "─" * 60 + "╯", style="bold yellow")
    console.print()
    
    for directory, files in grouped.items():
        console.print(f"  [yellow]▸[/yellow] [bold white]{directory}[/bold white] [dim]({len(files)} file(s))[/dim]")
    console.print()
    
    style = get_style({
        "question": "#00d7ff bold",
        "questionmark": "#00d7ff bold",
        "pointer": "#00d7ff bold",
        "instruction": "#7f7f7f",
        "answer": "#00d7ff bold"
    }, style_override=False)
    
    if is_files_mode:
        # When --files is used, directory mode means per-file commits
        choices = [
            {"name": "  🌐 One commit for all files", "value": "global"},
            {"name": "  📄 Separate commit for each file", "value": "directory"},
            {"name": "  🔗 Group related changes together", "value": "related"},
        ]
    else:
        # Normal mode: directory mode means per-directory commits
        choices = [
            {"name": "  🌐 One commit for all changes", "value": "global"},
            {"name": "  📁 Separate commits per directory", "value": "directory"},
            {"name": "  🔗 Group related changes together", "value": "related"},
        ]
    
    strategy = inquirer.select(
        message="Commit strategy",
        style=style,
        choices=choices,
        default=None,
        instruction="(Use arrow keys)",
        qmark="❯"
    ).execute()
    
    return strategy


def process_global_commit(console, flags, staged=None):
    """Process a single global commit for all changes.
    
    Args:
        console: Rich console for output
        flags: Commit flags
        staged: Optional staged dict with files. If provided, only commits those files.
    
    Returns True if a commit was made, False otherwise."""
    # If staged dict is provided (e.g., from --files), use only those files
    files_to_commit = staged["files"] if staged and staged.get("files") else None
    
    # Regenerate loop
    while True:
        commit_message = analyze_changes(console, files=files_to_commit)
        
        # Create regenerate callback
        def regenerate():
            return analyze_changes(console, files=files_to_commit)
        
        selected_commit = prompt_commit_message(console, commit_message, regenerate_callback=regenerate)
        
        if selected_commit == "regenerate":
            # User wants to regenerate, loop again
            continue
        elif selected_commit:
            commit_changes(console, selected_commit, flags["rawArgv"], files=files_to_commit)
            return True
        else:
            return False


def process_per_directory_commits(console, staged, flags):
    """Process separate commits for each directory.
    Returns True if at least one commit was made, False otherwise."""
    grouped = group_files_by_directory(staged["files"])
    commits_made = False
    
    console.print()
    console.print("╭" + "─" * 60 + "╮", style="bold magenta")
    console.print("│" + f"  🔮 [bold white]Processing {len(grouped)} directories[/bold white]".ljust(71) + "│", style="bold magenta")
    console.print("╰" + "─" * 60 + "╯", style="bold magenta")
    console.print()
    
    # Ask if user wants to commit all or select specific directories
    style = get_style({
        "question": "#00d7ff bold",
        "questionmark": "#00d7ff bold",
        "pointer": "#00d7ff bold",
        "instruction": "#7f7f7f",
        "answer": "#00d7ff bold",
        "checkbox": "#00d7ff bold"
    }, style_override=False)
    
    if len(grouped) > 1:
        commit_all = inquirer.confirm(
            message="Commit all directories?",
            style=style,
            default=True,
            instruction="(y/n)",
            qmark="❯"
        ).execute()
        
        if commit_all:
            selected_directories = list(grouped.keys())
        else:
            # Let user select which directories to commit
            directory_choices = [
                {"name": f"{directory} ({len(files)} file(s))", "value": directory, "enabled": True}
                for directory, files in grouped.items()
            ]
            
            selected_directories = inquirer.checkbox(
                message="Select directories to commit",
                style=style,
                choices=directory_choices,
                instruction="(↑↓ navigate, Space toggle, Enter confirm)",
                qmark="❯",
                validate=lambda result: len(result) > 0,
                invalid_message="Please select at least one directory (use Space to toggle)"
            ).execute()
            
            # Clear any raw output and show clean summary
            console.print("\033[2K", end="")  # Clear current line
            console.print(f"[bold green]✓ Selected {len(selected_directories)} directory(ies) to commit[/bold green]")
            console.print()
    else:
        selected_directories = list(grouped.keys())
    
    if not selected_directories:
        console.print("\n[bold yellow]⚠️  No directories selected[/bold yellow]\n")
        return False
    
    # Process each selected directory
    for idx, directory in enumerate(selected_directories, 1):
        files = grouped[directory]
        console.print()
        console.print("┌" + "─" * 60 + "┐", style="bold cyan")
        console.print("│" + f"  📂 [{idx}/{len(selected_directories)}] [bold white]{directory}[/bold white]".ljust(69) + "│", style="bold cyan")
        console.print("└" + "─" * 60 + "┘", style="bold cyan")
        console.print()
        
        for file in files:
            console.print(f"  [cyan]▸[/cyan] [white]{file}[/white]")
        
        # Get diff for this directory's files
        with console.status(
            f"[magenta]🤖 Analyzing {directory}...[/magenta]",
            spinner="dots",
            spinner_style="magenta"
        ):
            diff = get_diff_for_files(files, flags["excludeFiles"])
            
            if not diff:
                console.print(f"\n[bold yellow]⚠️  No diff for {directory}, skipping[/bold yellow]\n")
                continue
            
            # Suppress stderr during AI call to hide ALTS warnings
            import sys
            _stderr = sys.stderr
            _devnull = open(os.devnull, 'w')
            sys.stderr = _devnull
            
            try:
                commit_message = generateCommitMessage(diff)
            finally:
                sys.stderr = _stderr
                _devnull.close()
            
            commit_message = sanitize_commit_messages(commit_message)
            
            if not commit_message:
                console.print(f"\n[bold yellow]⚠️  No commit message generated for {directory}, skipping[/bold yellow]\n")
                continue
        
        # Prompt for commit message selection with regenerate option
        while True:
            def regenerate():
                diff = get_diff_for_files(files, flags["excludeFiles"])
                if not diff:
                    return []
                import sys
                _stderr = sys.stderr
                _devnull = open(os.devnull, 'w')
                sys.stderr = _devnull
                try:
                    msg = generateCommitMessage(diff)
                    return sanitize_commit_messages(msg)
                finally:
                    sys.stderr = _stderr
                    _devnull.close()
            
            selected_commit = prompt_commit_message(console, commit_message, regenerate_callback=regenerate)
            
            if selected_commit == "regenerate":
                # Regenerate commit messages
                with console.status(
                    f"[magenta]🤖 Regenerating commit messages for {directory}...[/magenta]",
                    spinner="dots",
                    spinner_style="magenta"
                ):
                    commit_message = regenerate()
                    if not commit_message:
                        console.print(f"\n[bold yellow]⚠️  No commit message generated for {directory}, skipping[/bold yellow]\n")
                        break
                continue
            elif selected_commit:
                # Commit only the files in this directory
                subprocess.run(["git", "commit", "-m", selected_commit, *flags["rawArgv"], "--"] + files)
                console.print(f"\n[bold green]✅ Committed {directory}[/bold green]")
                commits_made = True
                break
            else:
                console.print(f"\n[bold yellow]⊘ Skipped {directory}[/bold yellow]")
                break
    
    return commits_made


def process_per_file_commits(console, staged, flags):
    """Process separate commits for each file when --files is used with directory mode.
    Returns True if at least one commit was made, False otherwise."""
    files = staged["files"]
    commits_made = False
    
    # Filter out files with no diff before processing
    files_with_changes = []
    for file in files:
        diff = get_diff_for_files([file], flags["excludeFiles"])
        if diff:
            files_with_changes.append(file)
    
    if not files_with_changes:
        console.print("\n[bold yellow]⚠️  No files with changes to commit[/bold yellow]\n")
        return False
    
    # If some files were filtered out, show a message
    if len(files_with_changes) < len(files):
        skipped_count = len(files) - len(files_with_changes)
        console.print(f"\n[dim]Skipping {skipped_count} file(s) with no changes[/dim]\n")
    
    console.print()
    console.print("╭" + "─" * 60 + "╮", style="bold magenta")
    console.print("│" + f"  🔮 [bold white]Processing {len(files_with_changes)} file(s)[/bold white]".ljust(71) + "│", style="bold magenta")
    console.print("╰" + "─" * 60 + "╯", style="bold magenta")
    console.print()
    
    # Ask if user wants to commit all or select specific files
    style = get_style({
        "question": "#00d7ff bold",
        "questionmark": "#00d7ff bold",
        "pointer": "#00d7ff bold",
        "instruction": "#7f7f7f",
        "answer": "#00d7ff bold",
        "checkbox": "#00d7ff bold"
    }, style_override=False)
    
    if len(files_with_changes) > 1:
        commit_all = inquirer.confirm(
            message="Commit all files?",
            style=style,
            default=True,
            instruction="(y/n)",
            qmark="❯"
        ).execute()
        
        if commit_all:
            selected_files = files_with_changes
        else:
            # Let user select which files to commit
            file_choices = [
                {"name": file, "value": file, "enabled": True}
                for file in files_with_changes
            ]
            
            selected_files = inquirer.checkbox(
                message="Select files to commit",
                style=style,
                choices=file_choices,
                instruction="(↑↓ navigate, Space toggle, Enter confirm)",
                qmark="❯",
                validate=lambda result: len(result) > 0,
                invalid_message="Please select at least one file (use Space to toggle)"
            ).execute()
            
            # Clear any raw output and show clean summary
            console.print("\033[2K", end="")  # Clear current line
            console.print(f"[bold green]✓ Selected {len(selected_files)} file(s) to commit[/bold green]")
            console.print()
    else:
        selected_files = files_with_changes
    
    if not selected_files:
        console.print("\n[bold yellow]⚠️  No files selected[/bold yellow]\n")
        return False
    
    # Process each selected file (all should have changes since we filtered)
    for idx, file in enumerate(selected_files, 1):
        console.print()
        console.print("┌" + "─" * 60 + "┐", style="bold cyan")
        console.print("│" + f"  📄 [{idx}/{len(selected_files)}] [bold white]{file}[/bold white]".ljust(69) + "│", style="bold cyan")
        console.print("└" + "─" * 60 + "┘", style="bold cyan")
        console.print()
        
        # Get diff for this file (should already have changes, but double-check)
        with console.status(
            f"[magenta]🤖 Analyzing {file}...[/magenta]",
            spinner="dots",
            spinner_style="magenta"
        ):
            diff = get_diff_for_files([file], flags["excludeFiles"])
            
            if not diff:
                console.print(f"\n[bold yellow]⚠️  No diff for {file}, skipping[/bold yellow]\n")
                continue
            
            # Suppress stderr during AI call to hide ALTS warnings
            import sys
            _stderr = sys.stderr
            _devnull = open(os.devnull, 'w')
            sys.stderr = _devnull
            
            try:
                commit_message = generateCommitMessage(diff)
            finally:
                sys.stderr = _stderr
                _devnull.close()
            
            commit_message = sanitize_commit_messages(commit_message)
            
            if not commit_message:
                console.print(f"\n[bold yellow]⚠️  No commit message generated for {file}, skipping[/bold yellow]\n")
                continue
        
        # Prompt for commit message selection with regenerate option
        while True:
            def regenerate():
                diff = get_diff_for_files([file], flags["excludeFiles"])
                if not diff:
                    return []
                import sys
                _stderr = sys.stderr
                _devnull = open(os.devnull, 'w')
                sys.stderr = _devnull
                try:
                    msg = generateCommitMessage(diff)
                    return sanitize_commit_messages(msg)
                finally:
                    sys.stderr = _stderr
                    _devnull.close()
            
            selected_commit = prompt_commit_message(console, commit_message, regenerate_callback=regenerate)
            
            if selected_commit == "regenerate":
                # Regenerate commit messages
                with console.status(
                    f"[magenta]🤖 Regenerating commit messages for {file}...[/magenta]",
                    spinner="dots",
                    spinner_style="magenta"
                ):
                    commit_message = regenerate()
                    if not commit_message:
                        console.print(f"\n[bold yellow]⚠️  No commit message generated for {file}, skipping[/bold yellow]\n")
                        break
                continue
            elif selected_commit:
                # Commit only this file
                subprocess.run(["git", "commit", "-m", selected_commit, *flags["rawArgv"], "--", file])
                console.print(f"\n[bold green]✅ Committed {file}[/bold green]")
                commits_made = True
                break
            else:
                console.print(f"\n[bold yellow]⊘ Skipped {file}[/bold yellow]")
                break
    
    return commits_made


def process_per_directory_commits_from_paths(console, staged, flags, original_paths):
    """Process separate commits for each directory/path when --files is used with directory mode.
    Groups files by the original paths passed (directories or files).
    Returns True if at least one commit was made, False otherwise."""
    repo_root = assert_git_repo()
    commits_made = False
    
    # Group files by the original paths they came from
    path_to_files = {}
    for path in original_paths:
        normalized_path = os.path.normpath(path)
        full_path = os.path.join(repo_root, normalized_path) if not os.path.isabs(path) else path
        
        if os.path.isdir(full_path):
            # It's a directory - find all files that belong to this directory
            dir_files = [f for f in staged["files"] if f.startswith(normalized_path + os.sep) or f == normalized_path]
            if dir_files:
                path_to_files[normalized_path] = dir_files
        else:
            # It's a file - add it directly
            if normalized_path in staged["files"]:
                path_to_files[normalized_path] = [normalized_path]
    
    if not path_to_files:
        console.print("\n[bold yellow]⚠️  No files found for the specified paths[/bold yellow]\n")
        return False
    
    # Filter out paths with no changes
    paths_with_changes = {}
    for path, files in path_to_files.items():
        diff = get_diff_for_files(files, flags["excludeFiles"])
        if diff:
            paths_with_changes[path] = files
    
    if not paths_with_changes:
        console.print("\n[bold yellow]⚠️  No paths with changes to commit[/bold yellow]\n")
        return False
    
    console.print()
    console.print("╭" + "─" * 60 + "╮", style="bold magenta")
    console.print("│" + f"  🔮 [bold white]Processing {len(paths_with_changes)} path(s)[/bold white]".ljust(71) + "│", style="bold magenta")
    console.print("╰" + "─" * 60 + "╯", style="bold magenta")
    console.print()
    
    # Process each path
    for idx, (path, files) in enumerate(paths_with_changes.items(), 1):
        console.print()
        console.print("┌" + "─" * 60 + "┐", style="bold cyan")
        console.print("│" + f"  📂 [{idx}/{len(paths_with_changes)}] [bold white]{path}[/bold white]".ljust(69) + "│", style="bold cyan")
        console.print("└" + "─" * 60 + "┘", style="bold cyan")
        console.print()
        
        for file in files:
            console.print(f"  [cyan]▸[/cyan] [white]{file}[/white]")
        
        # Get diff for this path's files
        with console.status(
            f"[magenta]🤖 Analyzing {path}...[/magenta]",
            spinner="dots",
            spinner_style="magenta"
        ):
            diff = get_diff_for_files(files, flags["excludeFiles"])
            
            if not diff:
                console.print(f"\n[bold yellow]⚠️  No diff for {path}, skipping[/bold yellow]\n")
                continue
            
            # Suppress stderr during AI call to hide ALTS warnings
            import sys
            _stderr = sys.stderr
            _devnull = open(os.devnull, 'w')
            sys.stderr = _devnull
            
            try:
                commit_message = generateCommitMessage(diff)
            finally:
                sys.stderr = _stderr
                _devnull.close()
            
            commit_message = sanitize_commit_messages(commit_message)
            
            if not commit_message:
                console.print(f"\n[bold yellow]⚠️  No commit message generated for {path}, skipping[/bold yellow]\n")
                continue
        
        # Prompt for commit message selection with regenerate option
        while True:
            def regenerate():
                diff = get_diff_for_files(files, flags["excludeFiles"])
                if not diff:
                    return []
                import sys
                _stderr = sys.stderr
                _devnull = open(os.devnull, 'w')
                sys.stderr = _devnull
                try:
                    msg = generateCommitMessage(diff)
                    return sanitize_commit_messages(msg)
                finally:
                    sys.stderr = _stderr
                    _devnull.close()
            
            selected_commit = prompt_commit_message(console, commit_message, regenerate_callback=regenerate)
            
            if selected_commit == "regenerate":
                # Regenerate commit messages
                with console.status(
                    f"[magenta]🤖 Regenerating commit messages for {path}...[/magenta]",
                    spinner="dots",
                    spinner_style="magenta"
                ):
                    commit_message = regenerate()
                    if not commit_message:
                        console.print(f"\n[bold yellow]⚠️  No commit message generated for {path}, skipping[/bold yellow]\n")
                        break
                continue
            elif selected_commit:
                # Commit only the files for this path
                subprocess.run(["git", "commit", "-m", selected_commit, *flags["rawArgv"], "--"] + files)
                console.print(f"\n[bold green]✅ Committed {path}[/bold green]")
                commits_made = True
                break
            else:
                console.print(f"\n[bold yellow]⊘ Skipped {path}[/bold yellow]")
                break
    
    return commits_made


def _analyze_and_group_files(console, files, file_diffs, flags):
    """Helper function to analyze files and group them by relationship.
    Returns the grouped files dictionary."""
    from devcommit.app.ai_providers import get_ai_provider
    
    # Use AI to group related files
    with console.status(
        "[magenta]🤖 AI analyzing relationships between changes...[/magenta]",
        spinner="dots",
        spinner_style="magenta"
    ):
        grouping_prompt = generate_relation_grouping_prompt(list(file_diffs.keys()), file_diffs)
        
        # Suppress stderr during AI call
        import sys
        _stderr = sys.stderr
        _devnull = open(os.devnull, 'w')
        sys.stderr = _devnull
        
        try:
            provider = get_ai_provider(config)
            ai_response = provider.generate_commit_message(
                grouping_prompt,
                "You are an expert software architect. Analyze the code changes and group related files together based on their semantic relationship, shared features, entities, and change intent.",
                8192
            )
        finally:
            sys.stderr = _stderr
            _devnull.close()
        
        # Parse AI response into groups
        related_groups = parse_relation_groups(ai_response, list(file_diffs.keys()))
    
    return related_groups


def process_per_related_commits(console, staged, flags):
    """Process separate commits for groups of related files.
    Uses AI to analyze changes and group files by semantic relationship,
    feature intent, and code dependencies.
    Returns True if at least one commit was made, False otherwise."""
    
    commits_made = False
    files = staged["files"]
    
    console.print()
    console.print("╭" + "─" * 60 + "╮", style="bold magenta")
    console.print("│" + "  🔗 [bold white]Analyzing related changes...[/bold white]".ljust(71) + "│", style="bold magenta")
    console.print("╰" + "─" * 60 + "╯", style="bold magenta")
    console.print()
    console.print("[dim]Grouping files by feature, entity, and semantic relationship...[/dim]")
    console.print()
    
    # Get diffs for all files
    file_diffs = {}
    with console.status(
        "[magenta]🤖 Gathering file diffs...[/magenta]",
        spinner="dots",
        spinner_style="magenta"
    ):
        for file in files:
            diff = get_diff_for_files([file], flags["excludeFiles"])
            if diff:
                file_diffs[file] = diff
    
    if not file_diffs:
        console.print("\n[bold yellow]⚠️  No files with changes to commit[/bold yellow]\n")
        return False
    
    # Group files (with option to regenerate)
    commit_all_mode = True  # Default to auto-commit mode
    while True:
        related_groups = _analyze_and_group_files(console, files, file_diffs, flags)
        
        if not related_groups:
            console.print("\n[bold yellow]⚠️  Could not determine related groups, falling back to directory grouping[/bold yellow]\n")
            return process_per_directory_commits(console, staged, flags)
        
        # Check if groups have pre-generated commit messages
        # If all groups have empty commit_messages, parsing likely failed and we're in fallback mode
        # In that case, generate commit messages for all groups in one batch call
        all_groups_empty = all(
            not group_data.get('commit_messages') or len(group_data.get('commit_messages', [])) == 0
            for group_data in related_groups.values()
        )
        
        if all_groups_empty and len(related_groups) > 0:
            # Fallback mode detected - AI parsing failed, so commit_messages are empty
            # Generate commit messages for all groups (one call per group, but done upfront)
            # This is still extra calls, but at least they're done before user interaction
            # Note: generateCommitMessage is already imported at the top of the file
            
            console.print("[dim]⚠️  AI grouping response had no commit messages. Generating now...[/dim]")
            with console.status(
                "[magenta]🤖 Generating commit messages for all groups...[/magenta]",
                spinner="dots",
                spinner_style="magenta"
            ):
                import sys
                _stderr = sys.stderr
                _devnull = open(os.devnull, 'w')
                sys.stderr = _devnull
                
                try:
                    # Generate commit messages for each group
                    for group_name, group_data in related_groups.items():
                        group_files = group_data['files']
                        diff = get_diff_for_files(group_files, flags["excludeFiles"])
                        if diff:
                            commit_msgs = generateCommitMessage(diff)
                            group_data['commit_messages'] = sanitize_commit_messages(commit_msgs)
                finally:
                    sys.stderr = _stderr
                    _devnull.close()
    
        # Display grouped results with type information
        console.print()
        console.print("╭" + "─" * 60 + "╮", style="bold green")
        console.print("│" + f"  ✅ [bold white]Found {len(related_groups)} logical group(s)[/bold white]".ljust(71) + "│", style="bold green")
        console.print("╰" + "─" * 60 + "╯", style="bold green")
        console.print()
        
        for group_name, group_data in related_groups.items():
            emoji = group_data.get('emoji', '📦')
            change_type = group_data.get('type', 'chore')
            file_count = len(group_data['files'])
            description = group_data.get('description', '')
            
            # Show group header with type badge
            type_colors = {
                "feature": "green",
                "bugfix": "red",
                "refactor": "yellow",
                "config": "blue",
                "docs": "cyan",
                "test": "magenta",
                "chore": "white"
            }
            type_color = type_colors.get(change_type, "white")
            
            console.print(f"  {emoji} [bold white]{group_name}[/bold white] [bold {type_color}][{change_type}][/bold {type_color}] [dim]({file_count} file(s))[/dim]")
            if description:
                console.print(f"     [dim italic]{description}[/dim italic]")
            
            # Show files in this group (indented)
            for file in group_data['files']:
                console.print(f"       [dim]└─[/dim] [cyan]{file}[/cyan]")
            console.print()
        
        # Ask if user wants to commit all groups, select specific ones, or regenerate grouping
        style = get_style({
            "question": "#00d7ff bold",
            "questionmark": "#00d7ff bold",
            "pointer": "#00d7ff bold",
            "instruction": "#7f7f7f",
            "answer": "#00d7ff bold",
            "checkbox": "#00d7ff bold"
        }, style_override=False)
        
        if len(related_groups) > 1:
            action_choice = inquirer.select(
                message="What would you like to do?",
                style=style,
                choices=[
                    {"name": "  ✅ Commit all groups", "value": "all"},
                    {"name": "  📋 Select specific groups", "value": "select"},
                    {"name": "  🔄 Regenerate grouping", "value": "regenerate"}
                ],
                default="all",
                instruction="(Use arrow keys)",
                qmark="❯"
            ).execute()
            
            if action_choice == "regenerate":
                console.print("\n[bold cyan]🔄 Regenerating grouping...[/bold cyan]\n")
                continue  # Loop back to regenerate
            elif action_choice == "all":
                selected_groups = list(related_groups.keys())
                commit_all_mode = True  # Track that we're in "commit all" mode
            else:  # select
                # Let user select which groups to commit (none pre-selected)
                selected_groups = []
                while not selected_groups:
                    group_choices = []
                    for group_name, group_data in related_groups.items():
                        emoji = group_data.get('emoji', '📦')
                        change_type = group_data.get('type', 'chore')
                        file_count = len(group_data['files'])
                        description = group_data.get('description', 'No description')
                        display_name = f"{emoji} {group_name} [{change_type}] ({file_count} files) - {description[:50]}{'...' if len(description) > 50 else ''}"
                        # Don't pre-select - user must explicitly select groups
                        group_choices.append({"name": display_name, "value": group_name, "enabled": False})
                    
                    try:
                        selected_groups = inquirer.checkbox(
                            message="Select groups to commit",
                            style=style,
                            choices=group_choices,
                            instruction="(↑↓ navigate, Space toggle, Enter confirm)",
                            qmark="❯"
                        ).execute() or []
                        
                        if not selected_groups or len(selected_groups) == 0:
                            console.print("\n[bold yellow]⚠️  You need to select at least one group to continue[/bold yellow]")
                            console.print("[dim]Use Space to select groups, then press Enter[/dim]\n")
                            continue
                    except KeyboardInterrupt:
                        raise
                
                # Clear any raw output and show clean summary
                console.print("\033[2K", end="")  # Clear current line
                console.print(f"[bold green]✓ Selected {len(selected_groups)} group(s) to commit[/bold green]")
                console.print()
                commit_all_mode = False  # Track that we're in "select specific" mode
        else:
            # Only one group - ask if they want to commit it or regenerate
            action_choice = inquirer.select(
                message="What would you like to do?",
                style=style,
                choices=[
                    {"name": "  ✅ Commit this group", "value": "commit"},
                    {"name": "  🔄 Regenerate grouping", "value": "regenerate"}
                ],
                default="commit",
                instruction="(Use arrow keys)",
                qmark="❯"
            ).execute()
            
            if action_choice == "regenerate":
                console.print("\n[bold cyan]🔄 Regenerating grouping...[/bold cyan]\n")
                continue  # Loop back to regenerate
            else:
                selected_groups = list(related_groups.keys())
                commit_all_mode = True  # Single group = auto-commit mode
        
        if not selected_groups:
            console.print("\n[bold yellow]⚠️  No groups selected[/bold yellow]\n")
            return False
        
        # Break out of regenerate loop if we have selections
        break
    
    # Process each selected group
    for idx, group_name in enumerate(selected_groups, 1):
        group_data = related_groups[group_name]
        group_files = group_data['files']
        description = group_data.get('description', '')
        emoji = group_data.get('emoji', '📦')
        change_type = group_data.get('type', 'chore')
        pre_generated_messages = group_data.get('commit_messages', [])
        
        console.print()
        console.print("┌" + "─" * 60 + "┐", style="bold cyan")
        console.print("│" + f"  {emoji} [{idx}/{len(selected_groups)}] [bold white]{group_name}[/bold white] [dim][{change_type}][/dim]".ljust(78) + "│", style="bold cyan")
        console.print("└" + "─" * 60 + "┘", style="bold cyan")
        
        if description:
            console.print(f"[dim italic]{description}[/dim italic]")
        console.print()
        
        for file in group_files:
            console.print(f"  [cyan]▸[/cyan] [white]{file}[/white]")
        
        # Verify diff exists for this group
        diff = get_diff_for_files(group_files, flags["excludeFiles"])
        if not diff:
            console.print(f"\n[bold yellow]⚠️  No diff for {group_name}, skipping[/bold yellow]\n")
            continue
        
        # Use pre-generated commit messages from grouping (NO additional AI calls!)
        if pre_generated_messages:
            # Filter out empty messages and ensure we have at least one
            commit_message = [msg.strip() for msg in pre_generated_messages if msg and msg.strip()]
            if not commit_message:
                console.print(f"\n[bold yellow]⚠️  No valid commit messages for {group_name}, skipping[/bold yellow]\n")
                continue
        else:
            # Fallback: generate if not provided (shouldn't happen normally)
            with console.status(
                f"[magenta]🤖 Generating commit message for {group_name}...[/magenta]",
                spinner="dots",
                spinner_style="magenta"
            ):
                import sys
                _stderr = sys.stderr
                _devnull = open(os.devnull, 'w')
                sys.stderr = _devnull
                try:
                    commit_message = generateCommitMessage(diff)
                finally:
                    sys.stderr = _stderr
                    _devnull.close()
                
                commit_message = sanitize_commit_messages(commit_message)
                
                if not commit_message:
                    console.print(f"\n[bold yellow]⚠️  No commit message generated for {group_name}, skipping[/bold yellow]\n")
                    continue
        
        # Prompt for commit message selection with regenerate option
        while True:
            def regenerate():
                diff = get_diff_for_files(group_files, flags["excludeFiles"])
                if not diff:
                    return []
                import sys
                _stderr = sys.stderr
                _devnull = open(os.devnull, 'w')
                sys.stderr = _devnull
                try:
                    msg = generateCommitMessage(diff)
                    return sanitize_commit_messages(msg)
                finally:
                    sys.stderr = _stderr
                    _devnull.close()
            
            selected_commit = prompt_commit_message(console, commit_message, regenerate_callback=regenerate)
            
            if selected_commit == "regenerate":
                # Regenerate commit messages (this is the only time we make an extra AI call)
                with console.status(
                    f"[magenta]🤖 Regenerating commit messages for {group_name}...[/magenta]",
                    spinner="dots",
                    spinner_style="magenta"
                ):
                    commit_message = regenerate()
                    if not commit_message:
                        console.print(f"\n[bold yellow]⚠️  No commit message generated for {group_name}, skipping[/bold yellow]\n")
                        break
                continue
            elif selected_commit:
                # Commit only the files in this group
                subprocess.run(["git", "commit", "-m", selected_commit, *flags["rawArgv"], "--"] + group_files)
                console.print(f"\n[bold green]✅ Committed {group_name}[/bold green]")
                commits_made = True
                break
            else:
                console.print(f"\n[bold yellow]⊘ Skipped {group_name}[/bold yellow]")
                break
        
        # If in "select specific groups" mode and not the last group, ask if user wants to continue
        if not commit_all_mode and idx < len(selected_groups):
            console.print()
            continue_choice = inquirer.confirm(
                message=f"Continue to next group ({len(selected_groups) - idx} remaining)?",
                style=style,
                default=True,
                instruction="(y/n)",
                qmark="❯"
            ).execute()
            
            if not continue_choice:
                console.print("\n[bold yellow]⚠️  Stopped committing remaining groups[/bold yellow]\n")
                break
    
    return commits_made


if __name__ == "__main__":
    main()
