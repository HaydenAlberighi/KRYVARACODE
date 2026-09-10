from src.agent.aegis.invariants import check_violation

# Use double backslashes in source (becomes single in string)
code = "with open('C:\\Windows\\System32\\config\\SAM') as f:\n    pass"
print("Code:", repr(code))
violations = check_violation(code)
print("Violations:", violations)
for v in violations:
    print(f"  {v.name}: {v.risk_level}")
