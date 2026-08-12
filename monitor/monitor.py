#!/usr/bin/env python3
"""Deterministic health/dashboard monitor for the two Hilbert-XVI Argus seats.

This process never transfers mathematical content between seats and never calls a
model. It polls durable Argus state, verifies immutable launch controls, renders a
bilingual status page, records milestone event metadata, and publishes changed
status at milestone boundaries or every three hours.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

BASE = Path("/data/chenxi/difficlut/math")
REPO = BASE / "Waiting to solve"
RUNTIME = BASE / "talk" / "monitor" / "runtime"
STOP_FILE = RUNTIME / "STOP"
STATE_FILE = RUNTIME / "monitor-state.json"
LOCK_FILE = RUNTIME / "monitor.lock"
LOG_FILE = RUNTIME / "monitor.log"
LIVE_MD = REPO / "status" / "live.md"
RUNTIME_JSON = REPO / "status" / "runtime.json"
AUTO_TIMELINE = REPO / "timeline" / "auto-events.md"
INTERVAL_SECONDS = 300
ROUTINE_PUSH_SECONDS = 3 * 60 * 60
STALE_WARNING_SECONDS = 30 * 60

SEATS: dict[str, dict[str, Any]] = {
    "A": {
        "sid": "s-54f17ee7",
        "workdir": BASE / "math1",
        "life": Path.home() / ".argus-skill" / "projects" / "s-54f17ee7",
        "inbox": BASE / "talk" / "A-inbox",
        "outbox": BASE / "talk" / "A-outbox",
        "models": "Engineer/Planner gpt-5.6-sol · Reviewer Gemini 3.1 Pro",
        "route": "theory / upper constraints",
    },
    "B": {
        "sid": "s-2fd8729b",
        "workdir": BASE / "math2",
        "life": Path.home() / ".argus-skill" / "projects" / "s-2fd8729b",
        "inbox": BASE / "talk" / "B-inbox",
        "outbox": BASE / "talk" / "B-outbox",
        "models": "Engineer/Planner Gemini 3.1 Pro · Reviewer gpt-5.6-sol",
        "route": "construction / lower bounds",
    },
}

IMMUTABLE_HASHES = {
    str(BASE / "math1" / "PROBLEM.md"): "03679f5f6a65703115715c610a5264aff7b7d5c6b29d73be0fedf9533dc9aad7",
    str(BASE / "math2" / "PROBLEM.md"): "03679f5f6a65703115715c610a5264aff7b7d5c6b29d73be0fedf9533dc9aad7",
    str(BASE / "talk" / "protocol" / "bin" / "pi-argus-a"): "9847cd80c08d9787ff230236cbab4ebedd3c92dc65b3da8228e4cb8c18332b45",
    str(BASE / "talk" / "protocol" / "bin" / "pi-argus-b"): "0c591e15be886d7508a8332d32d3fdf20c59dcdac639d3d89926ef2a9fd6d352",
}

MAJOR_TYPES = {
    "life.mission.completed",
    "life.mission.failed",
    "life.manager.stage_decision",
    "life.lifecycle.transition",
    "life.plan.revision.committed",
    "life.planner.stall_escalation",
    "life.planner.error",
    "round.stall",
    "round.escalated",
    "round.reviewer_backend_failure",
    "budget.reservation.denied",
    "budget.unpriced.blocked",
    "project.completed",
    "project.completion_refused",
    "research.achievement.certified",
    "operator_alert",
}

_stop = False


def utc_text(ts: float | None = None) -> str:
    value = dt.datetime.fromtimestamp(ts or time.time(), tz=dt.timezone.utc)
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


def log(message: str) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    line = f"[{utc_text()}] {message}"
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line, flush=True)


def read_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default
    return value


def atomic_write(path: Path, text: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = ""
    try:
        old = path.read_text(encoding="utf-8")
    except OSError:
        pass
    if old == text:
        return False
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)
    return True


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def immutable_issues() -> list[str]:
    issues: list[str] = []
    for raw, expected in IMMUTABLE_HASHES.items():
        path = Path(raw)
        try:
            actual = file_sha256(path)
        except OSError as exc:
            issues.append(f"missing/unreadable immutable control `{path}`: {exc}")
            continue
        if actual != expected:
            issues.append(f"immutable control hash drift: `{path}`")
    return issues


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(
            errors="replace"
        )
    except OSError:
        return False
    return "argus" in cmd and ("--daemon" in cmd or "spawn_helper" in cmd)


def git_fact(workdir: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(workdir), *args],
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return result.stdout.strip()

    dirty = run("status", "--porcelain")
    return {
        "head": run("rev-parse", "--short", "HEAD") or "none",
        "last_commit": run("log", "-1", "--pretty=%s") or "none",
        "dirty_paths": len([line for line in dirty.splitlines() if line.strip()]),
    }


def research_artifacts(workdir: Path) -> list[str]:
    root = workdir / "research"
    if not root.is_dir():
        return []
    names: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            names.append(str(path.relative_to(workdir)))
    return names[-20:]


def mailbox_count(path: Path) -> int:
    try:
        return len([p for p in path.iterdir() if p.is_file() and not p.name.startswith(".")])
    except OSError:
        return 0


def seat_snapshot(label: str, cfg: dict[str, Any], now: float) -> dict[str, Any]:
    life = Path(cfg["life"])
    daemon = read_json(life / "daemon.status.json", {})
    health = read_json(life / "daemon.health.json", {})
    view = read_json(life / "mission-view.json", {})
    pipeline = read_json(Path(cfg["workdir"]) / "research" / "PIPELINE_STATE.json", {})
    mission = view.get("mission") if isinstance(view.get("mission"), dict) else {}
    stage = view.get("stage") if isinstance(view.get("stage"), dict) else {}
    round_info = view.get("round") if isinstance(view.get("round"), dict) else {}
    review = view.get("review") if isinstance(view.get("review"), dict) else {}
    frontier = view.get("frontier") if isinstance(view.get("frontier"), dict) else {}
    pid = int(daemon.get("pid") or 0)
    last_progress = float(health.get("last_progress_at") or view.get("updated_at") or 0.0)
    progress_age = max(0.0, now - last_progress) if last_progress else None
    alive = pid_alive(pid)
    state = "running" if alive else "offline"
    if alive and progress_age is not None and progress_age > STALE_WARNING_SECONDS:
        state = "stale-warning"
    return {
        "label": label,
        "sid": cfg["sid"],
        "pid": pid,
        "alive": alive,
        "state": state,
        "health": str(health.get("phase") or "unknown"),
        "last_event": str(health.get("last_event") or "unknown"),
        "last_progress_at": last_progress,
        "progress_age_seconds": progress_age,
        "stage": str(stage.get("id") or pipeline.get("current_stage") or "unknown"),
        "mission_id": str(mission.get("id") or ""),
        "mission_title": str(mission.get("title") or "idle"),
        "mission_status": str(mission.get("status") or "idle"),
        "active_role": str(view.get("active_role") or "idle"),
        "round": int(round_info.get("current") or 0),
        "max_rounds": int(round_info.get("max") or 0),
        "review_status": str(review.get("status") or "none"),
        "review_reason": str(review.get("reason") or ""),
        "rejected_attempts": int(review.get("rejected_attempts") or 0),
        "frontier_change": str(frontier.get("change") or ""),
        "frontier_summary": str(frontier.get("summary") or ""),
        "models": cfg["models"],
        "route": cfg["route"],
        "git": git_fact(Path(cfg["workdir"])),
        "artifacts": research_artifacts(Path(cfg["workdir"])),
        "inbox_files": mailbox_count(Path(cfg["inbox"])),
        "outbox_files": mailbox_count(Path(cfg["outbox"])),
    }


def one_line(text: str, limit: int = 110) -> str:
    clean = " ".join(str(text or "").split()).replace("|", "\\|")
    return clean if len(clean) <= limit else clean[: limit - 1] + "…"


def age_text(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    return f"{seconds / 3600:.1f}h"


def render_live(snapshots: dict[str, dict[str, Any]], issues: list[str], now: float) -> str:
    rows = []
    for label in ("A", "B"):
        s = snapshots[label]
        rows.append(
            "| {label} | {state} | `{stage}` | {role} | {round}/{max_rounds} | "
            "{mission} | {review} | {age} |".format(
                label=label,
                state=s["state"],
                stage=s["stage"],
                role=s["active_role"],
                round=s["round"],
                max_rounds=s["max_rounds"],
                mission=one_line(s["mission_title"], 72),
                review=one_line(s["review_status"], 24),
                age=age_text(s["progress_age_seconds"]),
            )
        )
    details: list[str] = []
    for label in ("A", "B"):
        s = snapshots[label]
        artifacts = ", ".join(f"`{x}`" for x in s["artifacts"]) or "none yet"
        details.extend(
            [
                f"### Argus {label}",
                "",
                f"- **Session / PID:** `{s['sid']}` / `{s['pid']}`",
                f"- **Route:** {s['route']}",
                f"- **Models:** {s['models']}",
                f"- **Mission:** {one_line(s['mission_title'], 180)}",
                f"- **Reviewer state:** `{s['review_status']}`; rejected attempts: {s['rejected_attempts']}",
                f"- **Frontier signal:** {one_line(s['frontier_summary'] or s['frontier_change'] or 'not yet classified', 220)}",
                f"- **Research artifacts present:** {artifacts}",
                f"- **Git:** `{s['git']['head']}` · {s['git']['dirty_paths']} changed path(s) · {one_line(s['git']['last_commit'], 120)}",
                f"- **Broker mailboxes:** inbox {s['inbox_files']} · outbox {s['outbox_files']}",
                "",
            ]
        )
    integrity = "✅ immutable controls match" if not issues else "🚨 " + "; ".join(issues)
    return "\n".join(
        [
            "# Live Runtime Dashboard / 实时运行仪表板",
            "",
            "> Generated deterministically from Argus durable state. No model writes this page, and it carries no cross-process solution transfer.",
            "> 本页面由确定性监控器根据 Argus 持久状态生成，不由模型写入，也不承担跨进程解题内容传递。",
            "",
            f"**Updated / 更新时间:** {utc_text(now)}",
            "",
            "| Seat | State | Stage | Active role | Round | Current mission | Review | Since semantic progress |",
            "|---|---|---|---|---:|---|---|---:|",
            *rows,
            "",
            f"**Isolation integrity / 隔离完整性:** {integrity}",
            "",
            *details,
            "## Interpretation / 判读",
            "",
            "A running round is activity, not proof. Only Reviewer-confirmed proposition changes count as mathematical progress. A stale warning means no semantic Argus progress event for 30 minutes and requires coordinator inspection; it does not automatically mean the model is idle.",
            "",
            "运行中的回合只代表活动，不代表证明。只有经过 Reviewer 确认的命题状态变化才算数学进展。超过 30 分钟没有语义进展事件会显示停滞警告，需要协调者检查，但不自动等于模型偷懒。",
            "",
        ]
    )


def iter_events(path: Path, offset: int) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = []
    try:
        size = path.stat().st_size
        if offset > size:
            offset = 0
        with path.open("rb") as handle:
            handle.seek(offset)
            for raw in handle:
                try:
                    value = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                if isinstance(value, dict):
                    events.append(value)
            new_offset = handle.tell()
    except OSError:
        return events, offset
    return events, new_offset


def append_auto_events(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return False
    try:
        old = AUTO_TIMELINE.read_text(encoding="utf-8")
    except OSError:
        old = (
            "# Automatic Milestone Metadata\n\n"
            "This page records event metadata only; it is not a solution exchange.\n\n"
            "| UTC time | Seat | Event | Mission/status |\n"
            "|---|---|---|---|\n"
        )
    lines = [old.rstrip()]
    for row in rows:
        when = utc_text(float(row.get("ts") or time.time()))
        lines.append(
            f"| {when} | {row['seat']} | `{one_line(row.get('type', ''), 60)}` | "
            f"{one_line(row.get('title') or row.get('status') or row.get('reason') or '', 120)} |"
        )
    return atomic_write(AUTO_TIMELINE, "\n".join(lines) + "\n")


def load_state() -> dict[str, Any]:
    state = read_json(STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}
    state.setdefault("offsets", {})
    state.setdefault("last_push_at", time.time())
    return state


def save_state(state: dict[str, Any]) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    atomic_write(STATE_FILE, json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def git_publish(reason: str) -> bool:
    with LOCK_FILE.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("git publish skipped: another coordinator operation holds the lock")
            return False
        commands = [
            ["git", "add", "status/live.md", "status/runtime.json", "timeline/auto-events.md"],
            ["git", "diff", "--cached", "--quiet"],
        ]
        subprocess.run(commands[0], cwd=REPO, check=False, timeout=30)
        diff = subprocess.run(commands[1], cwd=REPO, check=False, timeout=30)
        if diff.returncode == 0:
            return False
        safe_reason = one_line(reason, 60)
        commit = subprocess.run(
            ["git", "commit", "-m", f"status: {safe_reason}"],
            cwd=REPO,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if commit.returncode != 0:
            log(f"git commit failed: {one_line(commit.stderr or commit.stdout, 200)}")
            return False
        push = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=REPO,
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        if push.returncode != 0:
            log(f"git push failed: {one_line(push.stderr or push.stdout, 200)}")
            return False
        log(f"published dashboard update: {safe_reason}")
        return True


def poll(*, publish: bool) -> None:
    now = time.time()
    state = load_state()
    issues = immutable_issues()
    snapshots = {label: seat_snapshot(label, cfg, now) for label, cfg in SEATS.items()}
    major: list[dict[str, Any]] = []
    for label, cfg in SEATS.items():
        path = Path(cfg["life"]) / "events.jsonl"
        raw_offset = state["offsets"].get(label)
        if raw_offset is None:
            # First observation establishes the baseline; launch events are already
            # represented by the manually reviewed initialization commit.
            try:
                state["offsets"][label] = path.stat().st_size
            except OSError:
                state["offsets"][label] = 0
            continue
        events, new_offset = iter_events(path, int(raw_offset))
        state["offsets"][label] = new_offset
        for event in events:
            if str(event.get("type") or "") in MAJOR_TYPES:
                major.append({**event, "seat": label})

    if issues:
        major.append(
            {
                "seat": "coordinator",
                "type": "isolation.integrity.failed",
                "ts": now,
                "title": "; ".join(issues),
            }
        )
    for label, snapshot in snapshots.items():
        if not snapshot["alive"]:
            major.append(
                {
                    "seat": label,
                    "type": "daemon.offline",
                    "ts": now,
                    "title": f"{snapshot['sid']} is not alive",
                }
            )

    atomic_write(LIVE_MD, render_live(snapshots, issues, now))
    atomic_write(
        RUNTIME_JSON,
        json.dumps(
            {
                "generated_at_utc": utc_text(now),
                "isolation_issues": issues,
                "seats": snapshots,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    append_auto_events(major)

    if publish:
        due = now - float(state.get("last_push_at") or 0.0) >= ROUTINE_PUSH_SECONDS
        reason = "routine three-hour runtime checkpoint"
        if major:
            kinds = sorted({str(row.get("type") or "event") for row in major})
            reason = "milestone " + ", ".join(kinds[:3])
        if major or due:
            if git_publish(reason):
                state["last_push_at"] = now
    save_state(state)


def handle_stop(_signum: int, _frame: Any) -> None:
    global _stop
    _stop = True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)
    if args.once:
        poll(publish=not args.no_push)
        return 0
    STOP_FILE.unlink(missing_ok=True)
    log("deterministic dual-Argus monitor started")
    while not _stop and not STOP_FILE.exists():
        try:
            poll(publish=not args.no_push)
        except Exception as exc:  # noqa: BLE001 - monitor must survive bad snapshots
            log(f"poll error: {type(exc).__name__}: {exc}")
        for _ in range(INTERVAL_SECONDS):
            if _stop or STOP_FILE.exists():
                break
            time.sleep(1)
    log("deterministic dual-Argus monitor stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
