import os
import re
import json
from datetime import datetime, timezone
from pathlib import Path
from openai import OpenAI
import gerald_session_state as _gss_session

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

MESSAGE INTENT CLASSIFICATION (classify before every response):
Classify each incoming message as one of:
- implementation_audit: requesting an audit of what is actually implemented in code
- task_status_question: asking about pipeline/technical completion status
- visual_outcome_question: asking about visible appearance, UI look, or user experience
- user_feedback_or_disagreement: Matt correcting Gerald, flagging a repeated answer
- investigation_request: asking Gerald to investigate/find root cause
- new_task_request: requesting implementation, build, or planning

CRITICAL — Visual ≠ Status:
"Is the last task complete?" → task_status_question → report audit verdict only.
"Does the dark mode look right?" → visual_outcome_question → compare visual evidence.
NEVER answer a visual_outcome_question with task pipeline status.

REPETITION BREAKER (activate when Matt flags repetition):
1. Acknowledge: "You're right, I repeated myself."
2. Do NOT reproduce the previous response.
3. Explain the misclassification: what Gerald answered vs what Matt actually asked.
4. Give a fresh, direct answer to what Matt actually asked.

VISUAL OUTCOME RULE:
For visual_outcome_question: base the answer on evidence (screenshots, audit artifacts).
If evidence is missing: acknowledge it and request visual verification.
Do NOT claim the UI looks correct based on task status alone.

IMPLEMENTATION AUDIT RULE (triggered when intent = implementation_audit):
All implementation audits MUST use live shell commands (ls, grep, sed). NEVER answer from memory.
Required proofs for every audited item:
1. FILE EXISTENCE: ls <path> output showing the file exists
2. FUNCTION GREP: grep -n result showing function/class at a line number
3. IMPORT/WIRING: grep -n result showing how the code is imported or registered
4. EXECUTION PATH: grep -n result showing who calls it or what triggers it
If live inspection is impossible for any item: return UNKNOWN.
Route as readonly_investigation; supply explicit grep/ls commands in the task field.

FOUNDATIONAL LESSON:
Task complete (audit=COMPLETE) does NOT mean the user outcome matches the design.
Technical completion is not the same as visual/UX confirmation.
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


def _load_recent_conversation(project: str, limit: int = 5):
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


# ── Message Intent Classification ──────────────────────────────────────────────

_FRUSTRATION_SIGNALS = [
    "repeat",            # repeating, repeat yourself, stop repeating
    "move on",           # can you move on already
    "already know",      # i already know all this
    "said that already", # you said that already
    "recap",             # cut the recap
]

_INVESTIGATION_SIGNALS = [
    "investigate", "find out why", "look into", "why did",
    "why is ", "why does", "examine", "check why", "what caused",
    "root cause", "investigate only", "report back",
]

# If ANY of these are present the task is an implementation request.
# They take priority over investigation signals — classify as new_task_request.
_IMPLEMENTATION_SIGNALS = [
    "code change required",
    "backend code change",
    "modify ",
    "implement ",
    "fix ",
    "return code changes",
]

_VISUAL_SIGNALS = [
    "look", "appear", "visible", "showing", "display", "screen",
    "can you see", "can i see", "see it", "does it show", "screenshot",
    " ui ", "layout", "dark mode", "theme", "color", "font",
    "what does it", "how does it", "shows up", "can't see",
    "where is it", "looks the same",
]

_TASK_STATUS_SIGNALS = [
    "is it done", "is it complete", "did it finish", "what's the status",
    "what is the status", "current status", "still running",
    "is the task", "has it finished", "did it work", "did it complete",
    "what stage",
]

_AUDIT_SIGNALS = [
    "implementation audit",
    "audit implementation",
    "audit the implementation",
    "list every",
    "list all implemented",
    "what's implemented",
    "what is implemented",
    "is it implemented",
    "verify implementation",
    "brain v3 audit",
    "currently implemented",
    "implemented in code",
    "audit of",
    "audit report",
]


def _is_frustration_turn(text: str) -> bool:
    """Return True when the user signals frustration at Gerald repeating itself."""
    p = text.lower()
    return any(s in p for s in _FRUSTRATION_SIGNALS)


def classify_message_intent(prompt: str) -> str:
    """
    Classify a user message into one of six intent categories before Gerald replies.

    Returns one of: user_feedback_or_disagreement, implementation_audit,
    investigation_request, visual_outcome_question, task_status_question,
    new_task_request.
    """
    p = prompt.lower()
    if _is_frustration_turn(prompt):
        return "user_feedback_or_disagreement"
    if any(s in p for s in _AUDIT_SIGNALS):
        return "implementation_audit"
    # Implementation intent overrides investigation: "investigate AND fix" is still a code task.
    if any(s in p for s in _IMPLEMENTATION_SIGNALS):
        return "new_task_request"
    if any(s in p for s in _INVESTIGATION_SIGNALS):
        return "investigation_request"
    if any(s in p for s in _VISUAL_SIGNALS):
        return "visual_outcome_question"
    if any(s in p for s in _TASK_STATUS_SIGNALS):
        return "task_status_question"
    return "new_task_request"


# ── Skip-Repeat State ──────────────────────────────────────────────────────────

def _convo_state_file(project: str) -> Path:
    safe = project.replace(" ", "_").replace("/", "_")
    return CONVERSATION_DIR / f"{safe}_convo_state.json"


def _load_convo_state(project: str) -> dict:
    """Load per-project conversation meta-state (skip_repeat flag, etc.)."""
    return _read_json(_convo_state_file(project), {})


def _save_convo_state(project: str, state: dict) -> None:
    _write_json(_convo_state_file(project), state)


def _update_skip_repeat_flag(project: str, prompt: str) -> None:
    """
    Maintain a two-turn skip-repeat window.
    Set on frustration turns; clears after two consecutive non-frustration turns.
    A second frustration turn resets the counter without clearing the flag.
    """
    state = _load_convo_state(project)
    if _is_frustration_turn(prompt):
        state["skip_repeat"] = True
        state["turns_since_set"] = 0
    elif state.get("skip_repeat"):
        turns = state.get("turns_since_set", 0) + 1
        if turns >= 2:
            state["skip_repeat"] = False
            state["turns_since_set"] = 0
        else:
            state["turns_since_set"] = turns
    _save_convo_state(project, state)


def is_skip_repeat_active(project: str) -> bool:
    """Return True when the skip-repeat flag is active for the project."""
    return bool(_load_convo_state(project).get("skip_repeat"))


# ── Visual Evidence ────────────────────────────────────────────────────────────

def _get_visual_evidence_summary(project: str) -> str:
    """Read audit + outbox to surface verification evidence for visual questions."""
    lines = []

    task_file = BASE / "active_task.json"
    try:
        if task_file.exists():
            task = json.loads(task_file.read_text(encoding="utf-8"))
            audit = task.get("audit") or {}
            stage = task.get("stage", "")
            verdict = audit.get("verdict", "")
            if verdict:
                lines.append(f"Last audit verdict: {verdict} (stage: {stage})")
            missing = audit.get("missing", [])
            if missing:
                lines.append(f"Missing evidence: {'; '.join(str(m)[:80] for m in missing[:3])}")
            notes = (audit.get("notes") or "")[:150]
            if notes:
                lines.append(f"Audit notes: {notes}")
    except Exception:
        pass

    safe_proj = project.replace(" ", "_")
    outbox_file = BASE / f"gerald_outbox_{safe_proj}.json"
    if not outbox_file.exists():
        outbox_file = BASE / "gerald_outbox.json"
    try:
        if outbox_file.exists():
            outbox = json.loads(outbox_file.read_text(encoding="utf-8"))
            output = (outbox.get("output") or "")[:200]
            if output:
                lines.append(f"Last output: {output[:150]}")
    except Exception:
        pass

    if not lines:
        return "NO_VISUAL_EVIDENCE: No audit or verification evidence found."
    return "\n".join(lines)


def _build_response_strategy(project: str, prompt: str, intent_class: str) -> str:
    """Return a targeted strategy block that guides Gerald's response."""

    if intent_class == "user_feedback_or_disagreement" and _is_frustration_turn(prompt):
        recent = _load_recent_conversation(project, limit=3)
        prev = (recent[-2].get("assistant") or "")[:300] if len(recent) >= 2 else ""
        return (
            "REPETITION BREAKER — ACTIVE:\n"
            "Matt flagged that Gerald just repeated itself. Rules:\n"
            "1. Open with: 'You're right, I repeated myself.'\n"
            "2. Do NOT reproduce or paraphrase the previous response.\n"
            "3. Explain the misclassification: what Gerald answered vs what Matt asked.\n"
            "4. Give a fresh, direct answer to what Matt actually asked.\n"
            f"Previous Gerald response (DO NOT REPEAT): {prev}"
        )

    if intent_class == "visual_outcome_question":
        evidence = _get_visual_evidence_summary(project)
        if "NO_VISUAL_EVIDENCE" in evidence:
            return (
                "VISUAL OUTCOME QUESTION — NO EVIDENCE:\n"
                "Matt is asking about how the app/UI looks, NOT about task completion status.\n"
                "No visual screenshot or verification evidence is available.\n"
                "Rules:\n"
                "1. Do NOT answer with task pipeline status.\n"
                "2. Acknowledge there is no visual evidence to compare against.\n"
                "3. Request or recommend a screenshot or visual verification run.\n"
                f"Evidence found: {evidence}"
            )
        return (
            "VISUAL OUTCOME QUESTION — COMPARE EVIDENCE:\n"
            "Matt is asking about how the app/UI looks, NOT about task completion status.\n"
            "Compare against this verification evidence:\n"
            f"{evidence}\n"
            "If evidence confirms the visual outcome matches design intent, say so specifically.\n"
            "If evidence is insufficient, request visual verification."
        )

    if intent_class == "task_status_question":
        return (
            "TASK STATUS QUESTION:\n"
            "Report audit verdict, task stage, and what was built — concisely.\n"
            "Do not describe UI appearance unless Matt explicitly asks."
        )

    if intent_class == "implementation_audit":
        return (
            "IMPLEMENTATION AUDIT — MANDATORY LIVE INSPECTION:\n"
            "Matt is requesting an implementation audit. These rules are non-negotiable:\n"
            "1. NEVER answer from memory, session summaries, or prior Claude outputs.\n"
            "2. All evidence MUST come from live shell commands (ls, grep, sed).\n"
            "3. For every audited item provide ALL four proofs:\n"
            "   (a) FILE EXISTENCE: `ls <path>` output confirming the file exists.\n"
            "   (b) FUNCTION GREP: `grep -n 'def <fn>\\|class <cls>' <file>` with line number.\n"
            "   (c) IMPORT/WIRING: `grep -n 'import\\|from\\|register\\|hook' <file>` showing wiring.\n"
            "   (d) EXECUTION PATH: `grep -n '<caller_or_trigger>' <file>` showing who calls it.\n"
            "4. If live inspection is impossible for any item, return: UNKNOWN — never guess.\n"
            "Route as readonly_investigation; provide explicit grep/ls commands in the task field."
        )

    if intent_class == "investigation_request":
        return (
            "INVESTIGATION REQUEST:\n"
            "Matt wants root cause analysis only. Rules:\n"
            "1. Report what you found in session history and logs.\n"
            "2. Identify the specific failure point.\n"
            "3. State the root cause clearly.\n"
            "4. Offer a fix only if Matt asks."
        )

    return (
        "NEW TASK REQUEST:\n"
        "Plan before executing. State understanding, flag uncertainty, "
        "propose the safest first step."
    )


FOUNDATIONAL_LESSON = "Task complete does not mean user outcome matches design."


def _ensure_foundational_lesson(project: str) -> None:
    """Store the foundational lesson once if it is not already in the project lessons."""
    try:
        lessons = _gss_session._read_lessons(project)
        if FOUNDATIONAL_LESSON not in lessons:
            _gss_session.append_lesson(project, FOUNDATIONAL_LESSON)
    except Exception:
        pass


# ── Brain V3 Relevance-Pruned Memory Window ────────────────────────────────────

BRAIN_V3_TOKEN_LIMIT = 2000

def _estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 chars."""
    return max(0, len(text) // 4)


def _extract_project_summary(project: str) -> str:
    """Extract a compact 1-3 line project summary from brain files."""
    lines = []

    brain_path = BASE / "project_brain.md"
    if brain_path.exists():
        try:
            text = brain_path.read_text(encoding="utf-8")
            in_overview = False
            overview = []
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("## Overview"):
                    in_overview = True
                    continue
                if in_overview:
                    if stripped.startswith("## "):
                        break
                    if stripped:
                        overview.append(stripped)
                        if len(overview) >= 2:
                            break
            if overview:
                lines.append("Overview: " + " ".join(overview[:2])[:200])
        except Exception:
            pass

    status_path = BASE / "current_status.md"
    if status_path.exists():
        try:
            text = status_path.read_text(encoding="utf-8")
            in_recent = False
            for line in text.splitlines():
                stripped = line.strip()
                if "Recent Changes" in stripped:
                    in_recent = True
                    continue
                if in_recent:
                    if stripped.startswith("## ") and "Recent Changes" not in stripped:
                        break
                    if stripped.startswith("- ") or stripped.startswith("**"):
                        lines.append("Latest: " + stripped.lstrip("- ").strip()[:120])
                        break
        except Exception:
            pass

    return "\n".join(lines) if lines else ""


def _filter_relevant_lessons(lessons: str, prompt: str, max_entries: int = 3) -> str:
    """Return only lesson entries that share keywords with the prompt."""
    if not lessons or not prompt:
        return ""

    stopwords = {
        "this", "that", "with", "from", "have", "will", "been", "when", "what",
        "your", "which", "there", "their", "about", "make", "each", "just",
        "also", "then", "than", "into", "more", "some", "such", "only",
    }
    prompt_words = {
        w.lower().rstrip(".,!?;:") for w in prompt.split()
        if len(w) > 4 and w.lower().rstrip(".,!?;:") not in stopwords
    }

    raw_entries = lessons.split("## Lesson")
    entries = [("## Lesson" + e) for e in raw_entries if e.strip()]

    if not entries:
        return ""
    if not prompt_words:
        return "\n".join(entries[-2:])

    scored = []
    for entry in entries:
        entry_words = {w.lower().rstrip(".,!?;:") for w in entry.split() if len(w) > 4}
        score = len(prompt_words & entry_words)
        scored.append((score, entry))

    scored.sort(key=lambda x: -x[0])
    top = [e for s, e in scored[:max_entries] if s > 0]
    if not top:
        top = [e for _, e in scored[:1]]

    return "\n".join(top)


def _build_brain_v3_memory_block(
    project: str,
    prompt: str,
    current_task: dict = None,
    token_limit: int = BRAIN_V3_TOKEN_LIMIT,
) -> str:
    """
    Build a relevance-pruned Brain V3 memory block for OpenAI calls.

    Priority order (highest → lowest):
    1. Recent Matt corrections and task failures
    2. Current task contract/audit (compact, if directly relevant)
    3. Last 5 user/Gerald conversation turns
    4. Relevant lessons (keyword-matched to prompt)
    5. Compact project summary

    Hard cap: ~token_limit tokens (estimated at 4 chars/token).
    """
    sections = []
    remaining = token_limit

    def _add(label: str, content: str) -> bool:
        nonlocal remaining
        block = f"{label}:\n{content}" if label else content
        t = _estimate_tokens(block)
        if t <= remaining:
            sections.append(block)
            remaining -= t
            return True
        return False

    # ── 1. Recent Matt corrections and task failures ───────────────────────────
    try:
        session_events = _gss_session._read_log(project)
        recent_events = session_events[-25:]

        correction_lines = []
        failure_lines = []
        for e in recent_events:
            etype = e.get("type", "")
            ts = (e.get("ts") or "")[:16].replace("T", " ")
            if etype == "matt_correction":
                correction_lines.append(f"  [{ts}] {(e.get('text') or '')[:120]}")
            elif etype == "outcome" and e.get("status") in ("contract_failed", "failed"):
                failure_lines.append(f"  [{ts}] {e.get('status')}: {(e.get('detail') or '')[:80]}")

        if correction_lines:
            _add("RECENT CORRECTIONS", "\n".join(correction_lines[-3:]))
        if failure_lines:
            _add("RECENT FAILURES", "\n".join(failure_lines[-2:]))
    except Exception:
        pass

    # ── 2. Current task contract/audit (compact) ──────────────────────────────
    if current_task and isinstance(current_task, dict) and remaining > 80:
        contract = current_task.get("contract") or {}
        audit = current_task.get("audit") or {}
        intent = (contract.get("user_intent") or "")[:150]
        verdict = audit.get("verdict", "")
        stage = current_task.get("stage", "")
        if intent or verdict:
            task_line = f"  Intent: {intent}"
            if stage:
                task_line += f" | Stage: {stage}"
            if verdict:
                task_line += f" | Audit: {verdict}"
                missing = audit.get("missing", [])
                if missing:
                    task_line += f" | Missing: {'; '.join(str(m)[:50] for m in missing[:2])}"
            _add("CURRENT TASK", task_line)

    # ── 3. Last 5 conversation turns ──────────────────────────────────────────
    if remaining > 200:
        recent_turns = _load_recent_conversation(project, limit=5)
        if recent_turns:
            turn_lines = []
            for turn in recent_turns:
                u = (turn.get("user") or "")[:200]
                a = (turn.get("assistant") or "")[:200]
                turn_lines.append(f"Matt: {u}\nGerald: {a}")

            # Trim oldest turns until the block fits
            while turn_lines:
                conv_content = "\n---\n".join(turn_lines)
                if _estimate_tokens(conv_content) <= remaining - 30:
                    _add("RECENT CONVERSATION", conv_content)
                    break
                turn_lines.pop(0)

    # ── 4. Relevant lessons (keyword-matched) ─────────────────────────────────
    if remaining > 100:
        try:
            lessons = _gss_session._read_lessons(project)
            if lessons:
                relevant = _filter_relevant_lessons(lessons, prompt)
                if relevant:
                    lesson_limit = min(remaining - 20, 500)
                    while relevant and _estimate_tokens(relevant) > lesson_limit:
                        relevant = relevant[:int(len(relevant) * 0.75)]
                    if relevant:
                        _add("RELEVANT LESSONS", relevant.strip())
        except Exception:
            pass

    # ── 5. Compact project summary ────────────────────────────────────────────
    if remaining > 60:
        summary = _extract_project_summary(project)
        if summary:
            _add("PROJECT SUMMARY", summary)

    block = "\n\n".join(sections)
    total_tokens = _estimate_tokens(block)
    print(f"[brain-v3] memory_block: ~{total_tokens} tokens, {len(sections)} sections, project={project}")
    return block


# ── Public API ─────────────────────────────────────────────────────────────────

def ask_gerald(prompt: str, project_context: str = "") -> str:
    project = _safe_project(project_context)
    _ensure_foundational_lesson(project)
    _update_skip_repeat_flag(project, prompt)

    intent_class = classify_message_intent(prompt)
    strategy_block = _build_response_strategy(project, prompt, intent_class)

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    memory_block = _build_brain_v3_memory_block(project, prompt)

    full_input = f"""
{memory_block}

INTENT HINT:
{_intent_hint(prompt)}

MESSAGE CLASS: {intent_class}

{strategy_block}

MATT'S CURRENT MESSAGE:
{prompt}

Respond as Gerald.
"""

    total_tokens = _estimate_tokens(GERALD_SYSTEM_PROMPT) + _estimate_tokens(full_input)
    print(f"[brain-v3] ask_gerald: ~{total_tokens} estimated tokens (project={project})")

    response = client.responses.create(
        model="gpt-4.1",
        instructions=GERALD_SYSTEM_PROMPT,
        input=full_input,
    )

    reply = (response.output_text or '').strip()

    _save_turn(project, prompt, reply)
    _append_memory_if_needed(project, prompt, reply)

    return reply


def decide_supervisor_action(user_text: str, project: str, payload: dict, current_task: dict, pending: str, last_outbox: dict) -> dict:
    """
    Gerald Brain V2 supervisor decision.
    OpenAI is the supervisor Matt interacts with.
    Claude is only a coding worker/tool.
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    safe_project = _safe_project(project)
    message_class = classify_message_intent(user_text)
    memory_block = _build_brain_v3_memory_block(safe_project, user_text, current_task=current_task)

    supervisor_brain = _read_file(BASE / "supervisor_brain.md")

    # Compact current_task, pending, last_outbox to prevent oversized payload
    _task_compact = ""
    if current_task:
        _task_compact = json.dumps({
            "stage": current_task.get("stage", ""),
            "detail": (current_task.get("detail") or "")[:150],
            "task": (current_task.get("task") or "")[:120],
        })

    _pending_compact = (pending or "")[:600]

    _outbox_compact = ""
    if last_outbox:
        _outbox_compact = json.dumps({
            "status": last_outbox.get("status", ""),
            "output": (last_outbox.get("output") or "")[:250],
        })

    prompt = f"""
You are Gerald Brain V2.

You are the supervisor Matt interacts with.
Claude Code is only a coding worker/tool.

Your job:
Decide the next action for Matt's current message using memory, project context, recent conversation, current task state, pending approvals, and lessons.

Available actions:
- answer_directly: answer Matt now, no coding worker.
- ask_clarification: ask Matt a short question because the request is genuinely blocked.
- gerald_brain: provide planning/reasoning, no code changes.
- execute_pending_approval: Matt approved an existing pending plan.
- claude_code: send a clear implementation task to Claude Code.
- readonly_investigation: ask Claude Code to inspect/report only.
- status_check: report current task status.
- fallback_router: only if the supervisor cannot decide safely.

Rules:
- IMPLEMENTATION OVERRIDE (highest priority): If the message contains ANY of these keywords — "CODE CHANGE REQUIRED", "modify ", "implement ", "fix ", "backend code change", "return code changes" — ALWAYS choose claude_code. NEVER choose readonly_investigation. This overrides all other rules including investigation_request classification. Presence of words like investigate/find/root cause does NOT change this — implementation keywords win.
- OpenAI/Gerald is the supervisor and conversation brain.
- Claude should only receive small, specific worker tasks.
- Prefer concise, practical responses.
- If Matt clearly approves a small implementation task, choose claude_code.
- If Matt asks a conceptual/system question, answer_directly or gerald_brain.
- If Claude/provider is unavailable, do not pretend work can proceed.
- Do not choose claude_code for vague plans unless Matt clearly approved implementation.
- Use durable root-cause fixes, not one-off phrase patches.
- If MESSAGE CLASS is implementation_audit: choose readonly_investigation; task must include explicit ls/grep/sed commands for each item; require all four proofs (file existence, function grep, import wiring, execution path); return UNKNOWN for any item that cannot be live-inspected. NEVER answer from memory.
- If MESSAGE CLASS is visual_outcome_question: choose answer_directly and base response on evidence, NOT task pipeline status.
- If MESSAGE CLASS is user_feedback_or_disagreement: do not repeat; acknowledge mismatch; report root cause.
- If MESSAGE CLASS is investigation_request AND no implementation keywords present: choose readonly_investigation or answer_directly with root cause.
- Return ONLY valid JSON.

SUPERVISOR BRAIN:
{(supervisor_brain or "")[:500]}

{memory_block}

PROJECT:
{project}

MESSAGE CLASS: {message_class}

CURRENT USER MESSAGE:
{user_text}

PAYLOAD KEYS:
{list(payload.keys())}

CURRENT TASK STATE:
{_task_compact or "(none)"}

PENDING APPROVAL:
{_pending_compact or "(none)"}

LAST OUTBOX:
{_outbox_compact or "(none)"}

Return JSON:
{{
  "action": "answer_directly|ask_clarification|gerald_brain|execute_pending_approval|claude_code|readonly_investigation|status_check|fallback_router",
  "reason": "short reason",
  "task": "exact worker task if applicable",
  "message": "brief direct response to Matt if applicable"
}}
"""

    system_prompt = "Return only valid JSON. You are Gerald Brain V2, the supervisor."
    total_tokens = _estimate_tokens(system_prompt) + _estimate_tokens(prompt)
    print(f"[brain-v3] decide_supervisor_action: ~{total_tokens} estimated tokens (project={project})")

    response = client.responses.create(
        model=os.environ.get("GERALD_SUPERVISOR_MODEL", "gpt-4.1"),
        instructions=system_prompt,
        input=prompt,
    )

    raw = (response.output_text or "").strip()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Supervisor response was not a JSON object")

    data.setdefault("action", "fallback_router")
    data.setdefault("reason", "")
    data.setdefault("task", user_text)
    data.setdefault("message", "")
    return data


# ── Risk Review Layer ──────────────────────────────────────────────────────────

def generate_risk_review(contract: dict, project_name: str) -> dict:
    """
    Pre-execution risk analysis. Reads past lessons + current contract to identify
    likely failure points before Claude runs. Result is attached to the task contract.
    """
    lessons_file = PROJECT_MEMORY_DIR / f"{project_name.replace(' ', '_')}_lessons.md"
    lessons_text = _read_file(lessons_file) or "No lessons recorded yet."
    if len(lessons_text) > 3000:
        lessons_text = lessons_text[-3000:]

    _sess_ctx = ""
    try:
        _sess_ctx = _gss_session.load_session_context(project_name, limit=4)
    except Exception:
        pass

    requirements = contract.get("requirements_checklist", [])
    likely_files = contract.get("likely_files", [])
    forbidden_files = contract.get("forbidden_files", [])
    verification = contract.get("verification_checklist", [])
    evidence_required = contract.get("evidence_required", [])

    req_text = "\n".join(f"- {r}" for r in requirements) or "(none)"
    verify_text = "\n".join(f"- {v}" for v in verification) or "(none)"
    evidence_text = (
        "\n".join(f"- [{e.get('evidence_type','?')}] {e.get('check','?')}" for e in evidence_required)
        if evidence_required else "None"
    )

    prompt = f"""You are Gerald's Risk Analyst. Before Claude executes a task, identify likely failure points.

TASK INTENT: {contract.get("user_intent", "(unknown)")}

REQUIREMENTS ({len(requirements)} items):
{req_text}

LIKELY FILES TO MODIFY: {", ".join(likely_files) or "unknown"}
FORBIDDEN FILES: {", ".join(forbidden_files) or "none"}

VERIFICATION STEPS:
{verify_text}

EVIDENCE REQUIRED (items that must have real captured output — not simulated):
{evidence_text}

PAST LESSONS (recurring failure patterns for this project):
{lessons_text}

RECENT SESSION CONTEXT (recent corrections and failures):
{_sess_ctx or "None"}

Identify concrete failure risks based on:
1. Past lessons — recurring patterns where similar tasks previously failed
2. Evidence gaps — verification steps that require real command output Claude often simulates
3. Scope risk — requirements that could cause Claude to overbuild or touch forbidden files
4. Audit/parse risk — JSON output, build steps, or audit checks that historically fail

Return ONLY valid JSON (no markdown fences):
{{
  "risks": [
    {{
      "risk": "brief specific risk description",
      "likelihood": "high | medium | low",
      "lesson_source": "which past lesson or pattern this comes from (or 'analysis' if inferred)",
      "mitigation": "one-sentence mitigation instruction"
    }}
  ],
  "high_risk_items": ["risk descriptions with high likelihood only"],
  "recommendation": "one-sentence overall pre-execution recommendation"
}}

List at most 6 risks. Be specific and actionable — not generic advice."""

    try:
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=900,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw.rstrip())
        result = json.loads(raw)
        result["generated_at"] = _now()
        n_risks = len(result.get("risks", []))
        n_high = len(result.get("high_risk_items", []))
        print(f"[risk] Risk review OK: {n_risks} risks, {n_high} high-risk — {result.get('recommendation','')[:100]}")
        return result
    except Exception as e:
        print(f"[risk] Risk review failed: {e}")
        return {
            "risks": [],
            "high_risk_items": [],
            "recommendation": f"Risk review unavailable: {e}",
            "generated_at": _now(),
        }
