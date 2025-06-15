# Security Policy

## Supported Versions

We release patches for security vulnerabilities. Currently supported versions:

| Version | Supported          |
| ------- | ------------------ |
| 3.x.x   | :white_check_mark: |
| < 3.0   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security vulnerability, please follow these steps:

1. **Do NOT** create a public GitHub issue
2. Send details to: edverma@icloud.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 5 business days
- **Resolution Target**: Within 30 days for critical issues

## Security Best Practices

### For Users

1. **Keep Updated**: Always use the latest version
   ```bash
   pip install --upgrade git-smart-squash
   ```

2. **Verify Package Integrity**: Check PyPI for official releases
   ```bash
   pip show git-smart-squash
   ```

3. **API Key Security**:
   - Never commit API keys to version control
   - Use environment variables or secure config files
   - Rotate keys regularly

### For Contributors

1. **Dependencies**: 
   - Review all dependency updates
   - Check for known vulnerabilities before adding new deps
   - Use `pip audit` to scan for vulnerabilities

2. **Code Review**:
   - All PRs require review before merging
   - Security-sensitive changes need additional review
   - No direct commits to main branch

3. **Secrets Management**:
   - Never hardcode credentials
   - Use GitHub Secrets for CI/CD
   - Document all required environment variables

## Security Features

### Package Publishing
- Automated publishing via GitHub Actions with OIDC
- No long-lived PyPI tokens in CI
- Protected release environments

### Dependency Management
- Automated vulnerability scanning via Dependabot
- Weekly dependency updates
- Grouped updates for dev dependencies

### Branch Protection
- Required PR reviews
- Status checks must pass
- Signed commits recommended
- No force pushes to protected branches

## Known Security Considerations

1. **AI API Keys**: The tool requires API keys for AI services. These should be:
   - Stored securely (never in code)
   - Limited in scope when possible
   - Rotated regularly

2. **Git Operations**: The tool performs git operations that could:
   - Modify commit history
   - Access repository contents
   - Execute git hooks

Users should review operations before confirming.

## Contact

Security Team: edverma@icloud.com
Project Maintainer: Evan Verma (@edverma)