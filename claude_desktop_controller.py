import re
import time
import ctypes
from ctypes import wintypes

import psutil
import pyautogui
import pyperclip

# ── Windows API ───────────────────────────────────────────────────────────────

_user32   = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

# ── Scoring rules ─────────────────────────────────────────────────────────────

_EXCLUDE = frozenset([
    "- google chrome", "- microsoft edge", "- firefox",
    "notepad", "settings",
    "program manager", "windows explorer", "file explorer",
    "task manager", "control panel", "microsoft store",
    "paint", "calculator", "photos",
])

_GENERIC_TERMINALS = frozenset([
    "windows powershell",
    "command prompt",
    "powershell",
    "administrator: windows powershell",
    "administrator: command prompt",
    "administrator: powershell",
])


# ── System queries ────────────────────────────────────────────────────────────

def _enum_visible_windows():
    """Return list of (hwnd, title, pid) for all visible, titled windows."""
    results = []

    def _cb(hwnd, _):
        if not _user32.IsWindowVisible(hwnd):
            return True
        length = _user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title:
            return True
        pid = wintypes.DWORD(0)
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        results.append((hwnd, title, pid.value))
        return True

    _user32.EnumWindows(_WNDENUMPROC(_cb), 0)
    return results


def _pid_to_process_name() -> dict:
    """Return {pid: process_name_lower} via psutil."""
    try:
        return {
            p.pid: p.info["name"].lower()
            for p in psutil.process_iter(["pid", "name"])
            if p.info.get("name")
        }
    except Exception:
        return {}


def _node_parent_pids() -> set:
    """
    Return the set of PIDs that are *parents* of node.exe processes.
    Uses psutil — no wmic, no pipe errors.
    Includes grandparents to handle Windows Terminal tab containers.
    """
    try:
        parents = set()
        for proc in psutil.process_iter(["pid", "ppid", "name"]):
            if proc.info.get("name", "").lower() != "node.exe":
                continue
            ppid = proc.info.get("ppid")
            if not ppid:
                continue
            parents.add(ppid)
            try:
                gp = psutil.Process(ppid)
                gp_ppid = gp.ppid()
                if gp_ppid:
                    parents.add(gp_ppid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return parents
    except Exception:
        return set()


# ── Scoring ───────────────────────────────────────────────────────────────────

def _score(title: str, pid: int, pid_names: dict, claude_terminal_pids: set) -> int:
    lower = title.lower()

    for frag in _EXCLUDE:
        if frag in lower:
            return -9999

    s = 0

    if pid in claude_terminal_pids:
        s += 500

    if "claude" in lower:
        s += 200

    if "windows terminal" in lower:
        s += 25

    if re.match(r"^[A-Z][A-Za-z0-9]{2,24}$", title):
        s += 80

    if re.match(r"^[A-Za-z]:\\", title):
        s += 50

    proc = pid_names.get(pid, "")
    if proc in ("cmd.exe", "powershell.exe", "pwsh.exe", "wt.exe"):
        s += 15

    if lower in _GENERIC_TERMINALS:
        s += 5

    return s


# ── Focus helper ──────────────────────────────────────────────────────────────

def _focus_window(hwnd: int) -> bool:
    """
    Bring hwnd to the foreground using the AttachThreadInput trick.
    Falls back to a click on the window centre if SetForegroundWindow is denied.
    Returns True if hwnd is the foreground window afterwards.
    """
    _user32.ShowWindow(hwnd, 9)   # SW_RESTORE — un-minimise
    time.sleep(0.25)

    fg_hwnd = _user32.GetForegroundWindow()
    fg_tid  = _user32.GetWindowThreadProcessId(fg_hwnd, None)
    my_tid  = _kernel32.GetCurrentThreadId()

    attached = False
    if fg_tid and fg_tid != my_tid:
        _user32.AttachThreadInput(my_tid, fg_tid, True)
        attached = True

    _user32.BringWindowToTop(hwnd)
    _user32.SetForegroundWindow(hwnd)

    if attached:
        _user32.AttachThreadInput(my_tid, fg_tid, False)

    time.sleep(0.4)

    if _user32.GetForegroundWindow() == hwnd:
        return True

    # Fallback: physically click the window centre to steal focus
    rect = wintypes.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(rect))
    cx = (rect.left + rect.right) // 2
    cy = (rect.top  + rect.bottom) // 2
    pyautogui.click(cx, cy)
    time.sleep(0.35)

    return _user32.GetForegroundWindow() == hwnd


# ── Public API ────────────────────────────────────────────────────────────────

def find_claude_window() -> tuple | None:
    """
    Return (hwnd, title, pid, score) for the best Claude Code window,
    or None if nothing scores above zero.
    """
    windows          = _enum_visible_windows()
    pid_names        = _pid_to_process_name()
    claude_term_pids = _node_parent_pids()

    if claude_term_pids:
        print(f"\nnode.exe parent PIDs (Claude terminals): {claude_term_pids}")
    else:
        print("\nNo node.exe processes found — falling back to title scoring only.")

    print(f"\n{'SCORE':>6}  {'PID':>7}  {'PROCESS':<22}  TITLE")
    print("-" * 75)

    candidates = []
    for hwnd, title, pid in windows:
        proc  = pid_names.get(pid, "unknown")
        score = _score(title, pid, pid_names, claude_term_pids)
        try:
            print(f"{score:>6}  {pid:>7}  {proc:<22}  {title!r}")
        except UnicodeEncodeError:
            print(f"{score:>6}  {pid:>7}  {proc:<22}  <non-ascii title>")
        if score > 0:
            candidates.append((score, hwnd, title, pid, proc))

    candidates.sort(key=lambda x: -x[0])

    print("-" * 75)
    if not candidates:
        print("\nNo Claude Code window found.")
        return None

    best_score, best_hwnd, best_title, best_pid, best_proc = candidates[0]
    print(f"\nSelected: {best_title!r}")
    print(f"          hwnd={best_hwnd}  pid={best_pid}  proc={best_proc}  score={best_score}")

    if len(candidates) > 1:
        print("Runners-up:")
        for sc, _, tt, pid_, proc_ in candidates[1:4]:
            try:
                print(f"  [{sc:4d}] pid={pid_}  {tt!r}")
            except UnicodeEncodeError:
                pass

    return best_hwnd, best_title, best_pid, best_score


def send_to_claude_code(message: str) -> dict:
    found = find_claude_window()

    if not found:
        return {"ok": False, "error": "No Claude Code window found."}

    hwnd, title, pid, score = found

    if not _focus_window(hwnd):
        fg = _user32.GetForegroundWindow()
        return {
            "ok":    False,
            "error": (
                f"Could not focus Claude Code window '{title}' "
                f"(hwnd={hwnd}, pid={pid}). "
                f"Foreground hwnd after attempt: {fg}"
            ),
        }

    pyperclip.copy(message)

    # ctrl+c  — cancel / interrupt any in-progress input
    # ctrl+u  — kill line (PSReadLine / bash readline clears the prompt)
    # ctrl+v  — paste message
    # enter   — submit
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "u")
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.4)
    pyautogui.press("enter")

    return {
        "ok":           True,
        "window":       title,
        "pid":          pid,
        "score":        score,
        "message_sent": message[:120] + ("..." if len(message) > 120 else ""),
    }


if __name__ == "__main__":
    result = send_to_claude_code(
        "Say only: Gerald session discovery successful"
    )

    print("\nRESULT:")
    print(result)
