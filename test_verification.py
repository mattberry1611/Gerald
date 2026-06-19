#!/usr/bin/env python3
"""
Quick test of Verification Layer V1
"""
import tempfile
import os
from verification_layer import VerificationLayer, verify_file_exists, verify_service_running

def test_verification():
    vl = VerificationLayer()
    
    print("=== Verification Layer V1 Tests ===\n")
    
    # Test 1: File exists
    print("Test 1: File exists")
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name
        tmp.write(b"test content")
    
    result = vl.verify_file_exists(tmp_path)
    print(f"  Result: {result.passed} - {result.message}")
    assert result.passed
    
    # Test 2: File doesn't exist
    print("\nTest 2: File doesn't exist")
    result = vl.verify_file_exists("/nonexistent/file.txt")
    print(f"  Result: {result.passed} - {result.message}")
    assert not result.passed
    
    # Test 3: File changed
    print("\nTest 3: File changed")
    before_hash = vl.snapshot_file(tmp_path)
    with open(tmp_path, 'a') as f:
        f.write("changed!")
    result = vl.verify_file_changed(tmp_path, before_hash)
    print(f"  Result: {result.passed} - {result.message}")
    assert result.passed
    
    # Test 4: File unchanged
    print("\nTest 4: File unchanged")
    after_hash = vl.snapshot_file(tmp_path)
    result = vl.verify_file_changed(tmp_path, after_hash)
    print(f"  Result: {result.passed} - {result.message}")
    assert not result.passed
    
    # Test 5: Service check (simple command)
    print("\nTest 5: Service check - echo command")
    result = vl.verify_service_running("echo 'service ok'")
    print(f"  Result: {result.passed} - {result.message}")
    assert result.passed
    
    # Test 6: Service check failure
    print("\nTest 6: Service check - failing command")
    result = vl.verify_service_running("exit 1")
    print(f"  Result: {result.passed} - {result.message}")
    assert not result.passed
    
    # Test 7: Verification suite
    print("\nTest 7: Verification suite")
    checks = [
        {"type": "exists", "file": tmp_path},
        {"type": "service", "command": "echo 'ok'"}
    ]
    suite_result = vl.run_verification_suite(checks)
    print(f"  Suite passed: {suite_result['passed']}")
    print(f"  Blocked: {suite_result['blocked']}")
    for r in suite_result['results']:
        print(f"    - {r['message']}")
    assert suite_result['passed']
    
    # Test 8: Retry on failure (simulate)
    print("\nTest 8: Retry mechanism")
    result = vl.verify_with_retry(vl.verify_file_exists, "/tmp/probably_exists_or_retry")
    print(f"  Result: {result.passed} - {result.message}")
    
    # Cleanup
    os.unlink(tmp_path)
    
    print("\n✅ All verification tests passed!")

if __name__ == "__main__":
    test_verification()
