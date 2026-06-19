"""
Verification Layer V1
Smallest implementation: file exists, file changed, service running, one retry.
"""
import os
import time
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


class VerificationResult:
    def __init__(self, passed: bool, message: str, details: Dict = None):
        self.passed = passed
        self.message = message
        self.details = details or {}


class VerificationLayer:
    def __init__(self):
        self.file_hashes = {}  # Track file state for change detection
    
    def verify_file_exists(self, filepath: str) -> VerificationResult:
        """Verify a file exists."""
        if os.path.exists(filepath):
            return VerificationResult(True, f"File exists: {filepath}")
        return VerificationResult(False, f"File not found: {filepath}")
    
    def verify_file_changed(self, filepath: str, before_hash: Optional[str] = None) -> VerificationResult:
        """Verify a file changed from a previous state."""
        if not os.path.exists(filepath):
            return VerificationResult(False, f"File not found: {filepath}")
        
        current_hash = self._hash_file(filepath)
        
        if before_hash is None:
            # First time seeing this file, store hash
            self.file_hashes[filepath] = current_hash
            return VerificationResult(True, f"File state recorded: {filepath}")
        
        if current_hash != before_hash:
            return VerificationResult(True, f"File changed: {filepath}")
        
        return VerificationResult(False, f"File unchanged: {filepath}")
    
    def verify_service_running(self, service_check: str) -> VerificationResult:
        """Verify a service is running via command check."""
        try:
            # Run the check command (e.g., "curl http://localhost:8000/health")
            result = subprocess.run(
                service_check,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return VerificationResult(True, f"Service check passed: {service_check}")
            
            return VerificationResult(
                False, 
                f"Service check failed: {service_check}",
                {"stdout": result.stdout, "stderr": result.stderr}
            )
        except subprocess.TimeoutExpired:
            return VerificationResult(False, f"Service check timeout: {service_check}")
        except Exception as e:
            return VerificationResult(False, f"Service check error: {str(e)}")
    
    def verify_with_retry(self, verification_func, *args, **kwargs) -> VerificationResult:
        """Run verification with one automatic retry on failure."""
        result = verification_func(*args, **kwargs)
        
        if not result.passed:
            time.sleep(1)  # Brief pause before retry
            result = verification_func(*args, **kwargs)
            if result.passed:
                result.message += " (passed on retry)"
        
        return result
    
    def _hash_file(self, filepath: str) -> str:
        """Generate hash of file contents."""
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            hasher.update(f.read())
        return hasher.hexdigest()
    
    def snapshot_file(self, filepath: str) -> Optional[str]:
        """Take snapshot of file state, return hash."""
        if os.path.exists(filepath):
            return self._hash_file(filepath)
        return None
    
    def run_verification_suite(self, checks: List[Dict]) -> Dict:
        """
        Run a suite of verification checks.
        
        checks format:
        [
            {"type": "exists", "file": "/path/to/file"},
            {"type": "changed", "file": "/path/to/file", "before_hash": "abc123"},
            {"type": "service", "command": "curl http://localhost:8000/health"}
        ]
        
        Returns: {"passed": bool, "results": [...], "blocked": bool}
        """
        results = []
        all_passed = True
        
        for check in checks:
            check_type = check.get("type")
            
            if check_type == "exists":
                result = self.verify_with_retry(
                    self.verify_file_exists,
                    check["file"]
                )
            elif check_type == "changed":
                result = self.verify_with_retry(
                    self.verify_file_changed,
                    check["file"],
                    check.get("before_hash")
                )
            elif check_type == "service":
                result = self.verify_with_retry(
                    self.verify_service_running,
                    check["command"]
                )
            else:
                result = VerificationResult(False, f"Unknown check type: {check_type}")
            
            results.append({
                "check": check,
                "passed": result.passed,
                "message": result.message,
                "details": result.details
            })
            
            if not result.passed:
                all_passed = False
        
        return {
            "passed": all_passed,
            "results": results,
            "blocked": not all_passed  # Verification failure blocks completion
        }


# Convenience functions for quick checks
def verify_file_exists(filepath: str, with_retry: bool = True) -> VerificationResult:
    """Quick file existence check."""
    vl = VerificationLayer()
    if with_retry:
        return vl.verify_with_retry(vl.verify_file_exists, filepath)
    return vl.verify_file_exists(filepath)


def verify_file_changed(filepath: str, before_hash: str, with_retry: bool = True) -> VerificationResult:
    """Quick file change check."""
    vl = VerificationLayer()
    if with_retry:
        return vl.verify_with_retry(vl.verify_file_changed, filepath, before_hash)
    return vl.verify_file_changed(filepath, before_hash)


def verify_service_running(command: str, with_retry: bool = True) -> VerificationResult:
    """Quick service check."""
    vl = VerificationLayer()
    if with_retry:
        return vl.verify_with_retry(vl.verify_service_running, command)
    return vl.verify_service_running(command)
