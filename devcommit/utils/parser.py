
from argparse import ArgumentParser, Namespace
from typing import List, Optional, TypedDict


class CommitFlag(TypedDict):
    generate: Optional[int]
    excludeFiles: List[str]
    stageAll: bool
    commitType: Optional[str]
    directory: bool
    files: List[str]
    push: bool
    changelog: bool
    models: bool
    freeModels: bool
    paidModels: bool
    commitAlias: Optional[str]
    version: bool
    rawArgv: List[str]


# Function to parse command-line arguments
def parse_arguments() -> CommitFlag:
    parser = ArgumentParser(
        description="Commit your changes with AI-generated messages.",
        allow_abbrev=False
    )
    parser.add_argument(
        "--generate",
        "-g",
        type=int,
        default=None,
        help="Number of commit messages to generate",
    )
    parser.add_argument(
        "--excludeFiles",
        "-e",
        nargs="*",
        default=[],
        help="Files to exclude from the diff",
    )
    parser.add_argument(
        "--stageAll", "-s", action="store_true", help="Stage all changes"
    )
    parser.add_argument(
        "--commitType", "-t", type=str, default=None, help="Type of commit"
    )
    parser.add_argument(
        "--directory", "-d", action="store_true", 
        help="Generate separate commits per root directory"
    )
    parser.add_argument(
        "--files", "-f", nargs="*", default=[],
        help="Specific files or folders to stage and commit (can specify multiple)"
    )
    parser.add_argument(
        "--push", "-p", action="store_true",
        help="Push commits to remote after committing"
    )
    parser.add_argument(
        "--changelog", "-c", action="store_true",
        help="Generate changelog file from changes"
    )
    parser.add_argument(
        "--models",
        action="store_true",
        help="List models from the configured AI provider and exit",
    )
    model_filter = parser.add_mutually_exclusive_group()
    model_filter.add_argument(
        "--free",
        dest="free_models",
        action="store_true",
        help="Only show free models with --models",
    )
    model_filter.add_argument(
        "--paid",
        dest="paid_models",
        action="store_true",
        help="Only show paid models with --models",
    )
    parser.add_argument(
        "--version", "-v", action="store_true",
        help="Show version information"
    )
    parser.add_argument(
        "--commit-alias",
        type=str,
        default=None,
        help="Git alias to use instead of git commit",
    )
    parser.add_argument(
        "rawArgv", nargs="*", help="Additional arguments for git commit"
    )

    args: Namespace = parser.parse_args()

    return CommitFlag(
        generate=args.generate,
        excludeFiles=args.excludeFiles,
        stageAll=args.stageAll,
        commitType=args.commitType,
        directory=args.directory,
        files=args.files or [],
        push=args.push,
        changelog=args.changelog,
        models=args.models,
        freeModels=args.free_models,
        paidModels=args.paid_models,
        commitAlias=args.commit_alias,
        version=args.version,
        rawArgv=args.rawArgv,
    )
