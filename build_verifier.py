"""
Gerald Build Verifier — autonomous Flutter build verification.
Full sequence: flutter clean → flutter pub get → flutter build apk.
Supports automatic retry with basic error diagnosis and fix attempts.
"""
import os
import json
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

BASE = r"C:\CommuteCoder"
BUILD_STATUS_FILE = os.path.join(BASE, "build_status.json")

MAX_RETRIES = 2


# ── Low-level command runner ────────────────────────────────────────────────────

def _run_cmd(
    label: str,
    cmd: List[str],
    cwd: str,
    timeout: int = 300,
) -> Dict[str, Any]:
    """Run a command and return a structured step result."""
    started = datetime.now(timezone.utc)
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = (datetime.now(timezone.utc) - started).total_seconds()
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        combined = f"{stdout}\n{stderr}".strip()
        return {
            "step": label,
            "cmd": " ".join(cmd),
            "returncode": result.returncode,
            "success": result.returncode == 0,
            "output": combined[:2000],
            "duration_s": round(duration, 1),
        }
    except subprocess.TimeoutExpired:
        return {
            "step": label,
            "cmd": " ".join(cmd),
            "returncode": -1,
            "success": False,
            "output": f"{label} timed out after {timeout}s",
            "duration_s": float(timeout),
        }
    except Exception as e:
        return {
            "step": label,
            "cmd": " ".join(cmd),
            "returncode": -1,
            "success": False,
            "output": str(e),
            "duration_s": 0.0,
        }


# ── Individual build steps ──────────────────────────────────────────────────────

def run_flutter_clean(project_path: str) -> Dict[str, Any]:
    """Run 'flutter clean' to remove build artifacts."""
    return _run_cmd("flutter clean", ["flutter", "clean"], project_path, timeout=120)


def run_flutter_pub_get(project_path: str) -> Dict[str, Any]:
    """Run 'flutter pub get' to resolve all dependencies."""
    return _run_cmd("flutter pub get", ["flutter", "pub", "get"], project_path, timeout=180)


def run_flutter_build(project_path: str, flavor: str = "debug") -> Dict[str, Any]:
    """Run 'flutter build apk' and return a structured result dict."""
    cmd = ["flutter", "build", "apk", f"--{flavor}"]
    started = datetime.now(timezone.utc)

    try:
        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=600,
        )
        duration = (datetime.now(timezone.utc) - started).total_seconds()

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        combined = f"{stdout}\n{stderr}".strip()

        success = result.returncode == 0
        errors = _extract_errors(combined)
        warnings = _extract_warnings(combined)

        data = {
            "status": "success" if success else "failed",
            "returncode": result.returncode,
            "duration_s": round(duration, 1),
            "output": combined[:4000],
            "errors": errors,
            "warnings": warnings,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_path": project_path,
            "flavor": flavor,
        }
        write_build_status(data)
        return data

    except subprocess.TimeoutExpired:
        data = {
            "status": "timeout",
            "returncode": -1,
            "duration_s": 600.0,
            "output": "Build timed out after 10 minutes.",
            "errors": ["Build timeout after 10 minutes"],
            "warnings": [],
            "error_count": 1,
            "warning_count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_path": project_path,
            "flavor": flavor,
        }
        write_build_status(data)
        return data

    except Exception as e:
        data = {
            "status": "error",
            "returncode": -1,
            "duration_s": 0.0,
            "output": str(e),
            "errors": [str(e)],
            "warnings": [],
            "error_count": 1,
            "warning_count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project_path": project_path,
            "flavor": flavor,
        }
        write_build_status(data)
        return data


# ── Error diagnosis and auto-fix ────────────────────────────────────────────────

def _classify_error(output: str) -> str:
    """Return a short error category for retry strategy selection."""
    lo = output.lower()
    if "could not resolve" in lo or "unresolved" in lo or "dependency" in lo:
        return "dependency"
    if "gradle" in lo and ("failed" in lo or "error" in lo):
        return "gradle"
    if "sdk" in lo and "not found" in lo:
        return "sdk"
    if "out of memory" in lo or "java heap space" in lo:
        return "oom"
    return "generic"


def _attempt_fix(error_category: str, project_path: str) -> Optional[str]:
    """
    Try a targeted fix based on the error category.
    Returns a description of the fix applied, or None if no fix attempted.
    """
    if error_category == "dependency":
        # Re-run pub get; if that's not enough, upgrade
        result = _run_cmd(
            "flutter pub upgrade",
            ["flutter", "pub", "upgrade"],
            project_path,
            timeout=180,
        )
        return f"Ran flutter pub upgrade (rc={result['returncode']})"

    if error_category == "gradle":
        # Clear Gradle wrapper cache to force re-download
        gradle_cache = os.path.join(project_path, "android", ".gradle")
        if os.path.isdir(gradle_cache):
            try:
                shutil.rmtree(gradle_cache)
                return f"Deleted Gradle cache at {gradle_cache}"
            except Exception as e:
                return f"Could not delete Gradle cache: {e}"
        return None

    if error_category == "oom":
        # Bump Gradle JVM heap via gradle.properties
        props_path = os.path.join(project_path, "android", "gradle.properties")
        heap_flag = "org.gradle.jvmargs=-Xmx4g\n"
        if os.path.exists(props_path):
            content = open(props_path, encoding="utf-8").read()
            if "Xmx" not in content:
                with open(props_path, "a", encoding="utf-8") as f:
                    f.write(heap_flag)
                return "Bumped Gradle JVM heap to 4 GB in gradle.properties"
        return None

    return None


# ── Full autonomous verification sequence ───────────────────────────────────────

def run_build_verification_sequence(
    project_path: str,
    flavor: str = "debug",
    max_retries: int = MAX_RETRIES,
) -> Dict[str, Any]:
    """
    Autonomous build verification: clean → pub get → build apk.
    On failure, attempts diagnosis + auto-fix and retries up to max_retries times.
    Writes build_status.json on completion.
    """
    print(f"[build_verifier] Starting verification sequence for {project_path}")
    overall_start = datetime.now(timezone.utc)
    steps_log: List[Dict[str, Any]] = []
    fix_log: List[str] = []

    def _ts() -> str:
        return datetime.now(timezone.utc).isoformat()

    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"[build_verifier] Retry {attempt}/{max_retries}…")

        # Step 1 — flutter clean
        clean_result = run_flutter_clean(project_path)
        steps_log.append(clean_result)
        print(f"[build_verifier] clean → rc={clean_result['returncode']}")
        if not clean_result["success"]:
            # clean failing is unusual; log and continue (don't abort)
            print(f"[build_verifier] WARNING: flutter clean failed: {clean_result['output'][:200]}")

        # Step 2 — flutter pub get
        pub_result = run_flutter_pub_get(project_path)
        steps_log.append(pub_result)
        print(f"[build_verifier] pub get → rc={pub_result['returncode']}")
        if not pub_result["success"]:
            category = _classify_error(pub_result["output"])
            fix_desc = _attempt_fix(category, project_path)
            if fix_desc:
                fix_log.append(f"[attempt {attempt+1}] pub-get fix ({category}): {fix_desc}")
            # Retry from top on pub get failure
            if attempt < max_retries:
                continue
            # Out of retries — report failure at pub get stage
            total_s = round((datetime.now(timezone.utc) - overall_start).total_seconds(), 1)
            data = _make_result(
                status="failed",
                errors=[f"flutter pub get failed: {pub_result['output'][:500]}"],
                warnings=[],
                output=pub_result["output"],
                duration_s=total_s,
                project_path=project_path,
                flavor=flavor,
                attempts=attempt + 1,
                steps=steps_log,
                fixes=fix_log,
            )
            write_build_status(data)
            return data

        # Step 3 — flutter build apk
        build_result = run_flutter_build(project_path, flavor)
        steps_log.append({
            "step": f"flutter build apk --{flavor}",
            "returncode": build_result["returncode"],
            "success": build_result["status"] == "success",
            "output": build_result["output"][:1000],
            "duration_s": build_result["duration_s"],
        })
        print(f"[build_verifier] build → status={build_result['status']}")

        if build_result["status"] == "success":
            total_s = round((datetime.now(timezone.utc) - overall_start).total_seconds(), 1)
            data = _make_result(
                status="success",
                errors=[],
                warnings=build_result.get("warnings", []),
                output=build_result["output"],
                duration_s=total_s,
                project_path=project_path,
                flavor=flavor,
                attempts=attempt + 1,
                steps=steps_log,
                fixes=fix_log,
            )
            write_build_status(data)
            print(f"[build_verifier] Sequence SUCCESS in {total_s}s ({attempt+1} attempt(s))")
            return data

        # Build failed — attempt fix and retry
        category = _classify_error(build_result.get("output", ""))
        fix_desc = _attempt_fix(category, project_path)
        if fix_desc:
            fix_log.append(f"[attempt {attempt+1}] build fix ({category}): {fix_desc}")

        if attempt >= max_retries:
            break

    # All retries exhausted
    last_errors = build_result.get("errors", [f"Build failed after {max_retries+1} attempt(s)"])  # type: ignore[possibly-undefined]
    total_s = round((datetime.now(timezone.utc) - overall_start).total_seconds(), 1)
    data = _make_result(
        status="failed",
        errors=last_errors,
        warnings=build_result.get("warnings", []),  # type: ignore[possibly-undefined]
        output=build_result.get("output", ""),  # type: ignore[possibly-undefined]
        duration_s=total_s,
        project_path=project_path,
        flavor=flavor,
        attempts=max_retries + 1,
        steps=steps_log,
        fixes=fix_log,
    )
    write_build_status(data)
    print(f"[build_verifier] Sequence FAILED after {max_retries+1} attempt(s) ({total_s}s)")
    return data


def _make_result(
    *,
    status: str,
    errors: List[str],
    warnings: List[str],
    output: str,
    duration_s: float,
    project_path: str,
    flavor: str,
    attempts: int,
    steps: List[Dict[str, Any]],
    fixes: List[str],
) -> Dict[str, Any]:
    return {
        "status": status,
        "returncode": 0 if status == "success" else 1,
        "duration_s": duration_s,
        "output": output[:4000],
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_path": project_path,
        "flavor": flavor,
        "attempts": attempts,
        "steps": steps,
        "fixes_applied": fixes,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_errors(output: str) -> List[str]:
    errors = []
    for line in output.splitlines():
        lo = line.lower()
        if "error:" in lo and "warning:" not in lo:
            stripped = line.strip()
            if stripped:
                errors.append(stripped)
    return errors[:20]


def _extract_warnings(output: str) -> List[str]:
    warnings = []
    for line in output.splitlines():
        if "warning:" in line.lower():
            stripped = line.strip()
            if stripped:
                warnings.append(stripped)
    return warnings[:20]


def write_build_status(data: Dict[str, Any]) -> None:
    with open(BUILD_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def read_build_status() -> Dict[str, Any]:
    if not os.path.exists(BUILD_STATUS_FILE):
        return {"status": "never_run", "timestamp": "", "error_count": 0, "warning_count": 0}
    with open(BUILD_STATUS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
