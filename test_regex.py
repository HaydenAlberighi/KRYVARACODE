import re

pattern = re.compile(r"C:\\Windows\\|/etc/passwd|/etc/shadow")
test_str = "with open('C:\\Windows\\System32\\config\\SAM') as f:\n    pass"
print("Test string:", repr(test_str))
match = pattern.search(test_str)
print("Match:", match)
if match:
    print("Matched:", repr(match.group()))
