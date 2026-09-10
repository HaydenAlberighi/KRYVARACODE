# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability in KRYVARACODE, please report it responsibly. **Do not open a public GitHub issue for security vulnerabilities.**

### How to Report

1. Email **haydenalberighi@gmail.com** with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Any suggested fixes (optional)

2. You should receive an initial response within **48 hours**.

3. We will work with you to understand and address the issue before any public disclosure.

### What to Expect

- **Acknowledgment** within 48 hours of your report
- **Status update** within 7 days with our assessment
- **Resolution timeline** once the issue is confirmed
- **Credit** in the release notes (unless you prefer to remain anonymous)

## Security Considerations

KRYVARACODE is an autonomous AI system that executes code and system operations. The following areas require particular attention:

### Aegis Safety System

The `src/agent/aegis/` module enforces behavioral invariants against all agent outputs. Key protections include:

- **Recursive delete prevention** — Blocks `shutil.rmtree()` and `rm -rf` patterns
- **System file access prevention** — Restricts writes outside allowed directories
- **Arbitrary shell command prevention** — Flags unvalidated shell execution
- **Unauthorized network access prevention** — Blocks socket operations without authorization
- **Memory manipulation prevention** — Blocks `ctypes` memory access patterns
- **Process termination prevention** — Restricts `os.kill()` calls

If you find a way to bypass these invariants, that is a critical security vulnerability.

### Authentication

- JWT tokens with configurable expiration
- Password hashing with bcrypt
- Account lockout after failed attempts
- Password reset tokens with expiration

### API Security

- Rate limiting on all endpoints
- CORS configuration
- Request validation via Pydantic models
- Audit logging of all tool executions

## Scope

The following are in scope for security reports:

- Vulnerabilities in the agent system that allow unauthorized actions
- Bypasses of the Aegis safety system
- Authentication/authorization bypass
- Remote code execution beyond intended tool surfaces
- Data exposure or injection vulnerabilities
- Denial of service vulnerabilities

## Out of Scope

- Issues requiring physical access to the host machine
- Vulnerabilities in third-party dependencies (report these upstream)
- Social engineering attacks
- Issues in development/testing configurations

## Dependencies

We use `bandit` for static security analysis and `pip-audit` for dependency scanning. Run these locally:

```bash
bandit -r src/
pip-audit
```

## Configuration Security

Never commit secrets to the repository. The `.env.example` file contains placeholder values. Always generate unique secrets for production:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Key security-related environment variables:

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Application-level secret |
| `JWT_SECRET_KEY` | JWT signing key |
| `JWT_ALGORITHM` | JWT algorithm (default: HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime |

## License

This security policy is part of the KRYVARACODE project and is subject to the MIT License.
