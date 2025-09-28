#!/usr/bin/env python3
"""
Backfill Git commits to light up the GitHub contributions calendar.

Examples:
  python3 backfill_commits.py
  python3 backfill_commits.py --start 2023-01-01 --end 2024-12-31 --push
  python3 backfill_commits.py --dry-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore


class BackfillError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Git commits for each day in a date range.")
    parser.add_argument("--per-day-min", type=int, default=1, help="Minimum commits per day (inclusive).")
    parser.add_argument("--per-day-max", type=int, default=2, help="Maximum commits per day (inclusive).")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD (inclusive).")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD (inclusive).")
    parser.add_argument("--work-hours", type=str, default="10-19", help="Working hour window H0-H1 (0-23).")
    parser.add_argument("--file", type=str, default="keep.log", help="File to modify for each commit.")
    parser.add_argument("--branch", type=str, help="Target branch name.")
    parser.add_argument("--push", action="store_true", help="Push to origin after committing.")
    parser.add_argument("--dry-run", action="store_true", help="Preview commits without making changes.")
    parser.add_argument("--timezone", type=str, help="IANA timezone name (e.g. Asia/Tokyo).")
    return parser.parse_args()


def ensure_git_available() -> None:
    if shutil.which("git") is None:
        raise BackfillError("git executable not found in PATH.")


def ensure_git_repo(path: Path) -> None:
    if not (path / ".git").exists():
        raise BackfillError("Current directory is not a Git repository (missing .git).")


def parse_date(value: str) -> dt.date:
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise BackfillError(f"Invalid date '{value}': {exc}") from exc


def parse_work_hours(spec: str) -> tuple[int, int]:
    parts = spec.split("-")
    if len(parts) != 2:
        raise BackfillError(f"Invalid work-hours '{spec}'; expected H0-H1.")
    try:
        start = int(parts[0])
        end = int(parts[1])
    except ValueError as exc:
        raise BackfillError(f"Invalid work-hours '{spec}'; hours must be integers.") from exc
    if not (0 <= start <= 23 and 0 <= end <= 23 and end >= start):
        raise BackfillError(f"Invalid work-hours '{spec}'; ensure 0 <= H0 <= H1 <= 23.")
    return start, end


def resolve_timezone(name: str | None) -> dt.tzinfo:
    if name:
        if ZoneInfo is None:
            raise BackfillError("zoneinfo module not available; cannot use --timezone.")
        try:
            return ZoneInfo(name)
        except Exception as exc:  # pragma: no cover
            raise BackfillError(f"Invalid timezone '{name}': {exc}") from exc
    auto = dt.datetime.now().astimezone().tzinfo
    if auto is None:
        raise BackfillError("Could not determine local timezone.")
    return auto


def compute_date_range(args: argparse.Namespace, tz: dt.tzinfo) -> tuple[dt.date, dt.date]:
    today = dt.datetime.now(tz=tz).date()
    if args.start:
        start = parse_date(args.start)
    else:
        start = today - dt.timedelta(days=730)
    if args.end:
        end = parse_date(args.end)
    else:
        end = today - dt.timedelta(days=1)
    if end >= today:
        raise BackfillError("End date must be earlier than today.")
    if start > end:
        raise BackfillError("Start date must not be later than end date.")
    return start, end


def date_iter(start: dt.date, end: dt.date):
    current = start
    while current <= end:
        yield current
        current += dt.timedelta(days=1)


def git_check_output(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def git_branch_exists(branch: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def git_has_commits() -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "HEAD"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def get_current_branch() -> str | None:
    try:
        branch = git_check_output(["git", "symbolic-ref", "--quiet", "--short", "HEAD"])
        if branch:
            return branch
    except subprocess.CalledProcessError:
        pass
    try:
        branch = git_check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        if branch and branch != "HEAD":
            return branch
    except subprocess.CalledProcessError:
        pass
    return None


def checkout_branch(branch: str, allow_create: bool, dry_run: bool) -> None:
    if dry_run:
        print(f"[dry-run] Would checkout branch '{branch}' (create={allow_create}).")
        return
    if allow_create:
        subprocess.check_call(["git", "checkout", "-B", branch])
    else:
        subprocess.check_call(["git", "checkout", branch])


def ensure_seed_commit(file_path: Path, tz: dt.tzinfo) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write("seed\n")
    now = dt.datetime.now(tz=tz).replace(microsecond=0)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S%z")
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = timestamp
    env["GIT_COMMITTER_DATE"] = timestamp
    subprocess.check_call(["git", "add", str(file_path)])
    subprocess.check_call(["git", "commit", "-m", "chore: seed backfill history"], env=env)


def ensure_origin_exists() -> None:
    remotes = git_check_output(["git", "remote"])
    names = {line.strip() for line in remotes.splitlines() if line.strip()}
    if "origin" not in names:
        raise BackfillError("Remote 'origin' not configured; cannot push.")


def plan_commits_per_day(date_list: list[dt.date], min_commits: int, max_commits: int) -> dict[dt.date, int]:
    rng = random.Random()
    plan = {}
    for day in date_list:
        plan[day] = rng.randint(min_commits, max_commits)
    return plan


def format_local_iso(local_dt: dt.datetime) -> str:
    return local_dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def append_line(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(content)


def perform_commits(
    plan: dict[dt.date, int],
    file_path: Path,
    tz: dt.tzinfo,
    work_hours: tuple[int, int],
    dry_run: bool,
) -> int:
    rng = random.Random()
    total_commits = 0
    start_hour, end_hour = work_hours
    for day in sorted(plan):
        count = plan[day]
        date_str = day.isoformat()
        print(f"{date_str}: planned {count} commit(s).")
        for index in range(1, count + 1):
            hour = rng.randint(start_hour, end_hour)
            minute = rng.randint(0, 59)
            second = rng.randint(0, 59)
            local_time = dt.time(hour=hour, minute=minute, second=second)
            local_dt = dt.datetime.combine(day, local_time, tzinfo=tz)
            iso_timestamp = format_local_iso(local_dt)
            message = f"backfill: {date_str} ({index}/{count})"
            line = f"{date_str} {index}/{count} {iso_timestamp}\n"
            if dry_run:
                print(f"  [dry-run] {message} at {iso_timestamp}")
                continue
            append_line(file_path, line)
            subprocess.check_call(["git", "add", str(file_path)])
            env = os.environ.copy()
            env["GIT_AUTHOR_DATE"] = iso_timestamp
            env["GIT_COMMITTER_DATE"] = iso_timestamp
            subprocess.check_call(["git", "commit", "-m", message], env=env)
            print(f"  committed {index}/{count} at {iso_timestamp}")
            total_commits += 1
        if dry_run:
            total_commits += count
    return total_commits


def main() -> None:
    args = parse_args()
    ensure_git_available()
    repo_root = Path.cwd()
    ensure_git_repo(repo_root)

    if args.per_day_min <= 0 or args.per_day_max <= 0:
        raise BackfillError("per-day values must be positive integers.")
    if args.per_day_min > args.per_day_max:
        raise BackfillError("--per-day-min must not exceed --per-day-max.")

    tz = resolve_timezone(args.timezone)
    start_date, end_date = compute_date_range(args, tz)
    dates = list(date_iter(start_date, end_date))
    if not dates:
        print("No dates to process.")
        return

    work_hours = parse_work_hours(args.work_hours)
    target_branch = args.branch
    current_branch = get_current_branch()

    if target_branch:
        branch_exists = git_branch_exists(target_branch)
    else:
        if current_branch:
            target_branch = current_branch
        else:
            target_branch = "main"
        branch_exists = git_branch_exists(target_branch)

    has_commits = git_has_commits()

    if args.dry_run:
        if not has_commits:
            print(f"[dry-run] Repository has no commits; would create seed commit on branch '{target_branch}'.")
        if args.branch and args.branch != current_branch:
            action = "create and checkout" if not branch_exists else "checkout"
            print(f"[dry-run] Would {action} branch '{args.branch}'.")
    else:
        if args.branch:
            checkout_branch(target_branch, allow_create=not branch_exists, dry_run=False)
        elif current_branch != target_branch:
            checkout_branch(target_branch, allow_create=not branch_exists, dry_run=False)

    file_path = (repo_root / args.file).resolve()

    if not has_commits and not args.dry_run:
        checkout_branch(target_branch, allow_create=True, dry_run=False)
        ensure_seed_commit(file_path, tz)
        print(f"Created seed commit on branch '{target_branch}'.")

    plan = plan_commits_per_day(dates, args.per_day_min, args.per_day_max)
    total = perform_commits(plan, file_path, tz, work_hours, args.dry_run)

    if args.dry_run:
        print(f"[dry-run] Planned total commits: {total}")
    else:
        print(f"Completed {total} commit(s) from {start_date} to {end_date}.")

    if args.push:
        if args.dry_run:
            print(f"[dry-run] Would push branch '{target_branch}' to origin.")
        else:
            ensure_origin_exists()
            subprocess.check_call(["git", "push", "-u", "origin", target_branch])
            print(f"Pushed branch '{target_branch}' to origin.")


if __name__ == "__main__":
    try:
        main()
    except BackfillError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as error:
        print(f"Git command failed: {error}", file=sys.stderr)
        sys.exit(error.returncode)
