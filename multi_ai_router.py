"""
Gerald Multi-AI Router — routes tasks to different AI provider backends.
Default: Claude Code (via claude.ps1).
OpenAI GPT-4o and Google Gemini 2.0 Flash are integrated (API key required).
"""
import os
import json
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List

BASE = r"C:\CommuteCoder"
CLAUDE_PS1 = r"C:\Users\Matt\AppData\Roaming\npm\claude.ps1"
PROVIDER_CONFIG_FILE = os.path.join(BASE, "ai_provider_config.json")

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/gemini-2.0-flash:generateContent"
)

# ── Registry ───────────────────────────────────────────────────────────────────

PROVIDER_REGISTRY: Dict[str, Dict[str, Any]] = {
    "claude": {
        "id": "claude",
        "name": "Claude Code",
        "vendor": "Anthropic",
        "model": "claude-sonnet-4-6",
        "requires_api_key": False,
        "status": "active",
        "description": "Anthropic Claude — autonomous code editing via CLI",
    },
    "openai": {
        "id": "openai",
        "name": "ChatGPT",
        "vendor": "OpenAI",
        "model": "gpt-4o",
        "requires_api_key": True,
        "status": "needs_api_key",
        "description": "OpenAI GPT-4o — API-based code assistance (set API key in Settings)",
    },
    "gemini": {
        "id": "gemini",
        "name": "Gemini",
        "vendor": "Google",
        "model": "gemini-2.0-flash",
        "requires_api_key": True,
        "status": "needs_api_key",
        "description": "Google Gemini 2.0 Flash — API-based code assistance (set API key in Settings)",
    },
}

# ── Runtime state ──────────────────────────────────────────────────────────────

_active_provider: str = "claude"
_provider_api_keys: Dict[str, str] = {}


def load_config() -> None:
    global _active_provider, _provider_api_keys
    if not os.path.exists(PROVIDER_CONFIG_FILE):
        return
    try:
        with open(PROVIDER_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _active_provider = data.get("active_provider", "claude")
        _provider_api_keys = data.get("api_keys", {})
        # Refresh status badges based on stored keys
        _refresh_provider_statuses()
    except Exception:
        pass


def save_config() -> None:
    with open(PROVIDER_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "active_provider": _active_provider,
                "api_keys": _provider_api_keys,
            },
            f,
            indent=2,
        )


def _refresh_provider_statuses() -> None:
    for pid in ("openai", "gemini"):
        key = _provider_api_keys.get(pid, "")
        PROVIDER_REGISTRY[pid]["status"] = "active" if key else "needs_api_key"


def get_active_provider() -> str:
    return _active_provider


def list_providers() -> List[Dict[str, Any]]:
    _refresh_provider_statuses()
    return list(PROVIDER_REGISTRY.values())


def set_active_provider(provider_id: str) -> None:
    global _active_provider
    if provider_id not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider '{provider_id}'. Valid: {list(PROVIDER_REGISTRY)}")
    _active_provider = provider_id
    save_config()
    print(f"[multi_ai_router] Active provider → {provider_id}")


def set_api_key(provider_id: str, api_key: str) -> None:
    _provider_api_keys[provider_id] = api_key
    save_config()
    _refresh_provider_statuses()
    print(f"[multi_ai_router] API key stored for {provider_id}")


# ── Task dispatch ──────────────────────────────────────────────────────────────

def run_task(task_text: str, project_path: str) -> Dict[str, Any]:
    """Dispatch task to the currently active AI provider."""
    provider = _active_provider
    if provider == "claude":
        return _run_claude(task_text, project_path)
    elif provider == "openai":
        return _run_openai(task_text, project_path)
    elif provider == "gemini":
        return _run_gemini(task_text, project_path)
    else:
        return {
            "status": "error",
            "provider": provider,
            "error": f"Unknown provider: {provider}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _run_claude(task_text: str, project_path: str) -> Dict[str, Any]:
    prompt = (
        f"You are Claude Code working inside:\n\n{project_path}\n\n"
        f"Matt's task:\n{task_text}\n\n"
        "Rules:\n"
        f"- Work only inside {project_path}\n"
        "- Do not edit RentMe or PlantBrain\n"
        "- Do not ask Matt for permission for safe local file edits\n"
        "- Complete the task, then provide a concise summary of what changed"
    )

    ps_command = (
        f"Set-Location '{project_path}';\n"
        f"& '{CLAUDE_PS1}' --dangerously-skip-permissions -p @'\n{prompt}\n'@"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=900,
        )
        return {
            "status": "done" if result.returncode == 0 else "error",
            "provider": "claude",
            "output": (result.stdout or "").strip(),
            "error": (result.stderr or "").strip(),
            "returncode": result.returncode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "provider": "claude",
            "error": "Claude timed out after 15 minutes",
            "output": "",
            "returncode": -1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "status": "error",
            "provider": "claude",
            "error": str(e),
            "output": "",
            "returncode": -1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _run_openai(task_text: str, project_path: str) -> Dict[str, Any]:
    """Call OpenAI GPT-4o via REST API."""
    api_key = _provider_api_keys.get("openai", "")
    if not api_key:
        return {
            "status": "error",
            "provider": "openai",
            "error": "OpenAI API key not configured. Add it in Settings → AI Provider.",
            "output": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    system_prompt = (
        "You are a coding assistant helping Matt with his software projects. "
        f"You are working inside the project directory: {project_path}. "
        "Provide clear, actionable responses with code where needed."
    )

    payload = json.dumps({
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_text},
        ],
        "max_tokens": 2000,
        "temperature": 0.2,
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENAI_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        model_used = data.get("model", "gpt-4o")
        usage = data.get("usage", {})
        return {
            "status": "done",
            "provider": "openai",
            "model": model_used,
            "output": content,
            "tokens_used": usage.get("total_tokens", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            pass
        return {
            "status": "error",
            "provider": "openai",
            "error": f"OpenAI HTTP {e.code}: {body[:300]}",
            "output": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "status": "error",
            "provider": "openai",
            "error": str(e),
            "output": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def _run_gemini(task_text: str, project_path: str) -> Dict[str, Any]:
    """Call Google Gemini 2.0 Flash via REST API."""
    api_key = _provider_api_keys.get("gemini", "")
    if not api_key:
        return {
            "status": "error",
            "provider": "gemini",
            "error": "Gemini API key not configured. Add it in Settings → AI Provider.",
            "output": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    prompt_text = (
        f"You are a coding assistant working in: {project_path}\n\nTask:\n{task_text}"
    )

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2000,
        },
    }).encode("utf-8")

    url = f"{GEMINI_API_URL}?key={api_key}"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["candidates"][0]["content"]["parts"][0]["text"]
        return {
            "status": "done",
            "provider": "gemini",
            "model": "gemini-2.0-flash",
            "output": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            pass
        return {
            "status": "error",
            "provider": "gemini",
            "error": f"Gemini HTTP {e.code}: {body[:300]}",
            "output": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "status": "error",
            "provider": "gemini",
            "error": str(e),
            "output": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Load config on import
load_config()
