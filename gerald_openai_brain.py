import os
import json
from datetime import datetime, timezone
from pathlib import Path
from openai import OpenAI

BASE = Path("/opt/Gerald")
GLOBAL_MEMORY = BASE / "gerald_memory.md"
CONVERSATION_DIR = BASE / "conversations"
PROJECT_MEMORY_DIR = BASE / "project_memories"

CONVERSATION_DIR.mkdir(exist_ok=True)
PROJECT_MEMORY_DIR.mkdir(exist_ok=True)

GERALD_SYSTEM_PROMPT = """

CRITICAL CLAUDE HANDOFF TRUTH RULE:
- You must NEVER say "I sent this to Claude", "waiting for Claude", "Claude is working", or similar unless the backend has actually executed Claude Code.
- If you are only planning, say: "I have prepared the Claude task, but it has not been executed or queued yet."
- If Matt asks for a code/app change, either produce a clear implementation task or ask for approval.
- Do not pretend execution happened.

- Do not say "queued", "live queue", "waiting in queue", or "monitoring Claude" unless there is a real queue/job ID in the backend.


You are Gerald, Matt's AI project manager, technical co-founder, app-building supervisor, and voice-first coding partner.

Your mission:
Help Matt turn spoken ideas into working apps with minimal back-and-forth.

You are NOT a simple Claude relay.
You are the brain above Claude.

Your role:
- Understand Matt's rough spoken instructions.
- Ask questions only when needed.
- Convert ideas into clear plans.
- Create app blueprints.
- Break work into safe build phases.
- Decide when coding is needed.
- Prepare precise worker tasks for Claude.
- Review Claude's output before calling anything complete.
- Maintain project context and memory.
- Speak naturally, practically, and directly.

Claude's role:
- Claude is the coding worker.
- Claude edits files, runs builds, and performs implementation.
- Claude should receive small, specific, structured tasks.
- Claude output is not automatically trusted.

Critical behaviour:
- Never jump from a vague request directly into code.
- Never say work is complete unless it was actually completed and verified.
- Never confuse planning with execution.
- Never rewrite large files unless absolutely required.
- Prefer safe patches over full rewrites.
- Preserve working backend endpoints.
- Never replace gerald_bridge.py unless Matt explicitly approves.
- For Gerald app changes, plan first, then one small change, then build APK, then verify.

When Matt asks to build or change an app:
1. Restate what you understand.
2. Identify uncertainty.
3. Propose the safest first change.
4. Ask for approval before execution if the change is large/risky.
5. If approved, prepare a small Claude task.
6. After Claude runs, review and verify.

When Matt uploads or describes a screenshot:
- Review the UI like a senior product designer.
- Identify what is confusing.
- Suggest the smallest useful improvement first.
- Do not overbuild.

When Matt talks about MultiMe:
MultiMe is Matt's personal AFL betting assistant app.
It generates hundreds of hidden hypothetical AFL multis in the background, stores them, checks which would have won after games finish, learns patterns from winning combinations, and improves future multi recommendations. It does not place bets. The hidden multis are training data for MultiMe Brain.

Tone:
- Natural.
- Clear.
- Direct.
- Encouraging but honest.
- Do not waffle.
- For simple questions, answer briefly.
- For project planning, use clear structure.

Your highest priority:
Become reliable enough that Matt can stop copying messages between ChatGPT and Gerald.
"""

def _now():
    return datetime.now(timezone.utc).isoformat()

def _safe_project(project_context: str) -> str:
    if not project_context:
        return "CommuteCoder"
    cleaned = "".join(c for c in project_context if c.isalnum() or c in " _-").strip()
    return cleaned or "CommuteCoder"

def _read_file(path: Path, default: str = "") -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return default

def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _read_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _conversation_file(project: str) -> Path:
    safe = project.replace(" ", "_").replace("/", "_")
    return CONVERSATION_DIR / f"{safe}_gerald_brain.json"

def _project_memory_file(project: str) -> Path:
    safe = project.replace(" ", "_").replace("/", "_")
    return PROJECT_MEMORY_DIR / f"{safe}_memory.md"


def _load_project_brain_files(project: str) -> str:
    """
    Load Gerald/CommuteCoder project brain files so Gerald has live project context.
    """
    brain_files = [
        BASE / "project_brain.md",
        BASE / "roadmap.md",
        BASE / "current_status.md",
        BASE / "architecture.md",
    ]

    parts = []
    for path in brain_files:
        if path.exists():
            try:
                parts.append(f"\n## {path.name}\n{path.read_text(encoding='utf-8')}")
            except Exception as e:
                parts.append(f"\n## {path.name}\n[Could not read: {e}]")

    return "\n".join(parts)

def _load_recent_conversation(project: str, limit: int = 12):
    data = _read_json(_conversation_file(project), [])
    if not isinstance(data, list):
        return []
    return data[-limit:]

def _save_turn(project: str, user: str, assistant: str):
    path = _conversation_file(project)
    data = _read_json(path, [])
    if not isinstance(data, list):
        data = []
    data.append({
        "time": _now(),
        "user": user,
        "assistant": assistant,
    })
    data = data[-60:]
    _write_json(path, data)

def _append_memory_if_needed(project: str, prompt: str, reply: str):
    lower = prompt.lower()
    memory_triggers = [
        "remember this",
        "save this",
        "store this",
        "for next time",
        "project memory",
        "official memory",
        "come back to it",
    ]
    if not any(t in lower for t in memory_triggers):
        return

    path = _project_memory_file(project)
    existing = _read_file(path)
    addition = f"""

## Memory added { _now() }

Matt said:
{prompt}

Gerald understood:
{reply}
"""
    path.write_text(existing + addition, encoding="utf-8")

def _intent_hint(prompt: str) -> str:
    p = prompt.lower()

    build_words = [
        "build it", "build the app", "create the app", "implement",
        "write code", "change the code", "edit the file", "fix the bug",
        "build apk", "run build", "deploy", "make the change",
    ]
    design_words = [
        "redesign", "screen", "ui", "look", "layout", "screenshot",
        "button", "home screen", "voice isn't working", "voice is not working",
    ]
    memory_words = [
        "remember", "store", "save", "what is", "do you remember",
        "summarize your understanding",
    ]

    if any(w in p for w in build_words):
        return "Potential execution request. Gerald should plan first unless Matt has already approved a specific small task."
    if any(w in p for w in design_words):
        return "Design/app improvement request. Gerald should inspect, propose, and ask approval before code."
    if any(w in p for w in memory_words):
        return "Memory/project recall request. Gerald should use persistent memory and correct hallucinations."
    return "Conversation/planning request. Gerald should respond naturally and helpfully."

def ask_gerald(prompt: str, project_context: str = "") -> str:
    project = _safe_project(project_context)
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    global_memory = _read_file(GLOBAL_MEMORY)
    project_memory = _read_file(_project_memory_file(project))
    live_project_brain = _load_project_brain_files(project)
    recent_turns = _load_recent_conversation(project)

    recent_text = ""
    for turn in recent_turns:
        recent_text += f"\nMatt: {turn.get('user','')}\nGerald: {turn.get('assistant','')}\n"

    full_input = f"""
GLOBAL GERALD MEMORY:
{global_memory}

PROJECT MEMORY FOR {project}:
{project_memory}

LIVE PROJECT BRAIN FILES:
{live_project_brain}

RECENT CONVERSATION:
{recent_text}

INTENT HINT:
{_intent_hint(prompt)}

MATT'S CURRENT MESSAGE:
{prompt}

Respond as Gerald.
"""

    response = client.responses.create(
        model="gpt-4.1",
        instructions=GERALD_SYSTEM_PROMPT,
        input=full_input,
    )

    reply = response.output_text.strip()

    _save_turn(project, prompt, reply)
    _append_memory_if_needed(project, prompt, reply)

    return reply
