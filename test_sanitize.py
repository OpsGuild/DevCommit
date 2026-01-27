#!/usr/bin/env python3
"""Test script to verify sanitize_commit_messages function works correctly."""

import sys
import os

# Add parent directory to path to import devcommit
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from devcommit.main import sanitize_commit_messages


def test_sanitize_commit_messages():
    """Test the sanitize_commit_messages function."""
    
    print("Testing sanitize_commit_messages function...\n")
    
    # Test 1: Error message should be filtered out
    test1 = "Error generating commit message: API key not found"
    result1 = sanitize_commit_messages(test1)
    assert result1 == [], f"Test 1 failed: Expected [], got {result1}"
    print("✅ Test 1 passed: Error message filtered out")
    
    # Test 2: Valid commit message should pass through
    test2 = "feat: add new feature"
    result2 = sanitize_commit_messages(test2)
    assert result2 == ["feat: add new feature"], f"Test 2 failed: Expected ['feat: add new feature'], got {result2}"
    print("✅ Test 2 passed: Valid commit message passed through")
    
    # Test 3: Multiple messages with one error should filter out error
    test3 = "feat: add feature|Error generating commit message: timeout|fix: bug fix"
    result3 = sanitize_commit_messages(test3)
    assert result3 == ["feat: add feature", "fix: bug fix"], f"Test 3 failed: Expected ['feat: add feature', 'fix: bug fix'], got {result3}"
    print("✅ Test 3 passed: Error message filtered from list")
    
    # Test 4: Empty string should return empty list
    test4 = ""
    result4 = sanitize_commit_messages(test4)
    assert result4 == [], f"Test 4 failed: Expected [], got {result4}"
    print("✅ Test 4 passed: Empty string returns empty list")
    
    # Test 5: List input with error message
    test5 = ["feat: add feature", "Error generating commit message: 402", "fix: bug fix"]
    result5 = sanitize_commit_messages(test5)
    assert result5 == ["feat: add feature", "fix: bug fix"], f"Test 5 failed: Expected ['feat: add feature', 'fix: bug fix'], got {result5}"
    print("✅ Test 5 passed: Error message filtered from list input")
    
    # Test 6: Whitespace handling
    test6 = "  feat: add feature  |  |  fix: bug fix  "
    result6 = sanitize_commit_messages(test6)
    assert result6 == ["feat: add feature", "fix: bug fix"], f"Test 6 failed: Expected ['feat: add feature', 'fix: bug fix'], got {result6}"
    print("✅ Test 6 passed: Whitespace handled correctly")
    
    # Test 7: Error message from the actual error you encountered
    test7 = "Error generating commit message: Error code: 402 - {'error': {'message': 'Provider returned error', 'code': 402, 'metadata': {'raw': '{\"error\":\"API ke"
    result7 = sanitize_commit_messages(test7)
    assert result7 == [], f"Test 7 failed: Expected [], got {result7}"
    print("✅ Test 7 passed: Actual error message filtered out")
    
    print("\n🎉 All tests passed!")


if __name__ == "__main__":
    test_sanitize_commit_messages()
