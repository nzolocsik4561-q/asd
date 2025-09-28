#!/usr/bin/env python3
"""Automate creating Issues and PRs in the current repository using GitHub CLI."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shlex
import subprocess
import sys
from pathlib import Path


class AutoActivityError(RuntimeError):
    """Raised when the automation cannot proceed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an Issue and an optional PR to simulate real activity.",
    )
    parser.add_argument("--issue-title", type=str, help="Title for the generated Issue.")
    parser.add_argument("--issue-body", type=str, help="Body text for the Issue.")
    parser.add_argument(
        "--create-issue",
        action="store_true",
        help="Create an Issue via gh issue create.",
    )
    parser.add_argument(
        "--create-pr",
        action="store_true",
        help="Create a PR with an auto-generated commit.",
    )
    parser.add_argument(
        "--file",
        type=str,
        default="keep.log",
        help="File to touch when generating the PR commit.",
    )
    parser.add_argument(
        "--branch",
        type=str,
        help="Name of the feature branch for the PR.",
    )
    parser.add_argument(
        "--base",
        type=str,
        default="main",
        help="Target base branch for the PR.",
    )
    parser.add_argument(
        "--commit-message",
        type=str,
        help="Commit message for the auto commit.",
    )
    parser.add_argument(
        "--pr-title",
        type=str,
        help="Title for the generated PR.",
    )
    parser.add_argument(
        "--pr-body",
        type=str,
        help="Body text for the PR description.",
    )
    parser.add_argument(
        "--push/--no-push",
        dest="push",
        action="store_true",
        default=True,
        help="Push the feature branch before creating the PR (default: push).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without executing commands.",
    )
    return parser.parse_args()


def ensure_cli_available(name: str) -> None:
    if shutil.which(name) is None:  # type: ignore[name-defined]
        raise AutoActivityError(f"Required executable '{name}' not found in PATH.")


try:
    import shutil
except ImportError:  # pragma: no cover
    raise SystemExit("Python standard module 'shutil' is required.")


def format_cmd(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def run(cmd: list[str], *, dry_run: bool, capture: bool = False) -> str:
    print(f"$ {format_cmd(cmd)}")
    if dry_run:
        print("[dry-run] command skipped")
        return ""
    if capture:
        return subprocess.check_output(cmd, text=True).strip()
    subprocess.check_call(cmd)
    return ""


def ensure_repo(path: Path) -> None:
    if not (path / ".git").exists():
        raise AutoActivityError("Current directory is not a git repository.")


def ensure_clean_worktree(*, dry_run: bool) -> None:
    status = run(["git", "status", "--porcelain"], dry_run=dry_run, capture=True)
    if status.strip():
        raise AutoActivityError("Working tree is not clean; please commit or stash changes first.")


def create_issue(args: argparse.Namespace, *, dry_run: bool) -> None:
    timestamp = dt.datetime.now().isoformat(timespec="seconds")
    title = args.issue_title or f"auto-activity issue {timestamp}"
    default_body = (
        "这个 Issue 由 auto_activity.py 脚本自动创建，用于维持活跃度。\n\n"
        f"时间戳: {timestamp}"
    )
    body = args.issue_body or default_body
    run(["gh", "issue", "create", "--title", title, "--body", body], dry_run=dry_run)


def append_activity_line(target: Path, timestamp: dt.datetime) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    line = f"{timestamp.date()} auto activity {timestamp.isoformat()}\n"
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line)


def create_pr(args: argparse.Namespace, repo_root: Path, *, dry_run: bool) -> None:
    ensure_clean_worktree(dry_run=dry_run)
    timestamp = dt.datetime.now()
    branch = args.branch or f"activity/{timestamp.strftime('%Y%m%d-%H%M%S')}"
    commit_message = args.commit_message or f"chore: auto activity {timestamp.date()}"
    pr_title = args.pr_title or f"Auto activity update {timestamp.date()}"
    pr_body = args.pr_body or (
        "这个 PR 由 auto_activity.py 自动生成，用于测试活跃度脚本。\n\n"
        f"生成时间: {timestamp.isoformat()}"
    )

    run(["git", "checkout", args.base], dry_run=dry_run)
    run(["git", "pull", "--ff-only", "origin", args.base], dry_run=dry_run)
    run(["git", "checkout", "-b", branch], dry_run=dry_run)

    target = (repo_root / args.file).resolve()
    if dry_run:
        print(f"[dry-run] would append activity line to {target}")
    else:
        append_activity_line(target, timestamp)

    run(["git", "add", str(target)], dry_run=dry_run)
    run(["git", "commit", "-m", commit_message], dry_run=dry_run)

    if args.push:
        run(["git", "push", "-u", "origin", branch], dry_run=dry_run)
    else:
        print("[info] --no-push supplied; skipping git push and PR creation.")
        return

    run(
        [
            "gh",
            "pr",
            "create",
            "--title",
            pr_title,
            "--body",
            pr_body,
            "--base",
            args.base,
            "--head",
            branch,
        ],
        dry_run=dry_run,
    )


def main() -> None:
    args = parse_args()
    if not args.create_issue and not args.create_pr:
        raise AutoActivityError("Nothing to do; pass --create-issue and/or --create-pr.")

    ensure_cli_available("git")
    ensure_cli_available("gh")

    repo_root = Path.cwd()
    ensure_repo(repo_root)

    if args.create_issue:
        create_issue(args, dry_run=args.dry_run)

    if args.create_pr:
        create_pr(args, repo_root, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except AutoActivityError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as error:
        print(f"Command failed: {error}", file=sys.stderr)
        sys.exit(error.returncode)
