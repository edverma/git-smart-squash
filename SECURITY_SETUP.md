# Security Setup Instructions

This guide contains manual steps required to complete the security setup for git-smart-squash.

## ✅ Already Implemented

The following security measures have been implemented via code changes:

1. **GitHub Actions PyPI Publishing** (`.github/workflows/publish.yml`)
   - OIDC-based authentication (no long-lived tokens)
   - Test PyPI integration
   - Build verification

2. **Branch Protection Rules** (`.github/branch-protection.json`)
   - Configuration ready for main and develop branches
   - Requires PR reviews and status checks

3. **Dependabot** (`.github/dependabot.yml`)
   - Weekly dependency updates
   - Automated security patches

4. **Security Policy** (`SECURITY.md`)
   - Vulnerability reporting process
   - Security best practices

5. **Release Checklist** (`.github/workflows/release-checklist.yml`)
   - Automated PR verification for releases

## 🔧 Manual Setup Required

### 1. PyPI Account Security

#### Enable 2FA on PyPI
1. Log in to https://pypi.org
2. Go to Account Settings → Security
3. Enable Two-Factor Authentication
4. Use an authenticator app (recommended) or SMS

#### Configure Publishing with OIDC
1. Go to your project page: https://pypi.org/project/git-smart-squash/
2. Click "Manage" → "Publishing"
3. Add a new trusted publisher:
   - Owner: `edverma`
   - Repository: `git-smart-squash`
   - Workflow name: `publish.yml`
   - Environment: `pypi`
4. Repeat for Test PyPI at https://test.pypi.org

#### Create Project-Specific API Tokens
1. Go to Account Settings → API tokens
2. Create a new token:
   - Name: `git-smart-squash-local`
   - Scope: Project `git-smart-squash`
3. Store securely (password manager recommended)
4. Update your `~/.pypirc`:
   ```ini
   [pypi]
   username = __token__
   password = pypi-...your-token-here...
   ```

### 2. GitHub Repository Settings

#### Enable Branch Protection
1. Go to Settings → Branches
2. Add rule for `main`:
   ```bash
   # Use the GitHub CLI to apply the configuration
   gh api repos/edverma/git-smart-squash/branches/main/protection \
     --method PUT \
     --input .github/branch-protection.json
   ```
   Or manually configure:
   - Require PR before merging
   - Require status checks (add when CI is set up)
   - Require conversation resolution
   - Require signed commits
   - Include administrators

#### Set Up Environments
1. Go to Settings → Environments
2. Create `pypi` environment:
   - Add protection rules
   - Restrict to `main` branch only
   - Add yourself as required reviewer
3. Create `test-pypi` environment:
   - Less restrictive for testing

#### Enable Dependabot
1. Go to Settings → Security & analysis
2. Enable:
   - Dependency graph
   - Dependabot alerts
   - Dependabot security updates

#### Configure Secrets (if needed for other workflows)
1. Go to Settings → Secrets and variables → Actions
2. Add any required secrets (NOT PyPI tokens with OIDC)

### 3. Local Development Security

#### Git Configuration
```bash
# Enable commit signing
git config --global user.signingkey YOUR_GPG_KEY_ID
git config --global commit.gpgsign true

# For this repository specifically
cd /Users/edverma/Development/git-smart-squash
git config commit.gpgsign true
```

#### Pre-commit Hooks (Optional but Recommended)
```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-case-conflict
      - id: check-merge-conflict
      - id: detect-private-key
  
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
EOF

# Install the git hook scripts
pre-commit install
```

### 4. Release Process

#### New Secure Release Process
1. Create a release PR with version bump
2. Ensure PR checklist is complete
3. Merge PR after approval
4. Create GitHub Release:
   ```bash
   # Tag the release
   git tag -s v3.4.7 -m "Release v3.4.7"
   git push origin v3.4.7
   
   # Create release on GitHub
   gh release create v3.4.7 --generate-notes
   ```
5. GitHub Actions will automatically:
   - Build the package
   - Publish to PyPI using OIDC
   - No manual PyPI upload needed!

### 5. Monitoring and Maintenance

#### Regular Security Tasks
- [ ] Review Dependabot PRs weekly
- [ ] Check for security alerts in GitHub
- [ ] Rotate local API tokens quarterly
- [ ] Review collaborator access
- [ ] Audit third-party actions used

#### Security Monitoring
1. Enable GitHub security alerts
2. Subscribe to PyPI security notifications
3. Monitor for typosquatting:
   ```bash
   # Check for similar package names
   pip search "git smart squash" "gitsmartsquash" "git-smart-sqash"
   ```

### 6. Additional Recommendations

#### Code Signing Certificate
Consider getting a code signing certificate for releases:
1. Use `sigstore` for keyless signing
2. Or GPG sign your commits and tags

#### Security Audit
Run periodic security audits:
```bash
# Check for known vulnerabilities
pip audit

# Scan for secrets
pip install truffleHog
truffleHog filesystem . --no-entropy
```

## 🚨 Important Notes

1. **Never commit**:
   - API tokens or passwords
   - `.pypirc` file
   - Private keys
   - `.env` files with secrets

2. **Always verify**:
   - Package contents before releasing
   - Dependencies are from trusted sources
   - GitHub Actions are from verified creators

3. **Emergency Response**:
   - If credentials are compromised, immediately:
     - Revoke tokens on PyPI
     - Rotate all secrets
     - Review recent releases
     - Notify users if necessary

## Need Help?

- PyPI Security: https://pypi.org/security/
- GitHub Security: https://docs.github.com/en/code-security
- Report issues: edverma@icloud.com