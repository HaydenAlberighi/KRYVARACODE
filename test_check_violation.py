from src.agent.aegis.invariants import check_violation, FORBIDDEN_PATTERNS

code = "with open('C:\\Windows\\System32\\config\\SAM') as f:\n    pass"
print("Code:", repr(code))

# Check each pattern manually
for inv in FORBIDDEN_PATTERNS:
    match = inv.pattern.search(code)
    if match:
        print(f'Pattern "{inv.name}" matches: {repr(match.group())}')

violations = check_violation(code)
print("Violations from check_violation:", violations)
