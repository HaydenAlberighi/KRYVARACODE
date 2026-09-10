import re

# Pattern from invariants
pattern = re.compile(r"C:\\Windows\\|/etc/passwd|/etc/shadow")

# Test string from test_windows.py (with quadruple backslashes in source)
test_str1 = "with open('C:\\\\Windows\\\\System32\\\\config\\\\SAM') as f:\n    pass"
print("Test 1 (quadruple backslashes in source):")
print("  String:", repr(test_str1))
match = pattern.search(test_str1)
print("  Match:", match)

# Test string with double backslashes in source (what we actually want)
test_str2 = "with open('C:\\Windows\\System32\\config\\SAM') as f:\n    pass"
print("Test 2 (double backslashes in source):")
print("  String:", repr(test_str2))
match = pattern.search(test_str2)
print("  Match:", match)

# Test string with single backslashes (raw string)
test_str3 = r"with open('C:\Windows\System32\config\SAM') as f:\n    pass"
print("Test 3 (raw string):")
print("  String:", repr(test_str3))
match = pattern.search(test_str3)
print("  Match:", match)
