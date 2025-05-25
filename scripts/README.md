# Publishing Scripts

This directory contains automated scripts for publishing git-smart-squash to various package managers.

## Scripts

### `release.py` (Recommended)
A Python-based release automation script with better error handling and cross-platform compatibility.

**Features:**
- Validates version formats
- Updates all version files automatically
- Runs tests before publishing
- Builds and publishes to PyPI/TestPyPI
- Creates git tags and releases
- Generates Homebrew and conda recipes
- Cross-platform compatible

**Usage:**
```bash
# Full release
./scripts/release.py 1.0.0

# Test release to TestPyPI
./scripts/release.py --test 1.0.0-rc1

# PyPI only (skip package manager files)
./scripts/release.py --pypi-only 1.0.1

# Skip tests (not recommended)
./scripts/release.py --skip-tests 1.0.0

# Dry run (show what would happen)
./scripts/release.py --dry-run 1.0.0
```

### `publish.sh`
A comprehensive bash script for advanced users who want full control over the publishing process.

**Features:**
- Complete automation for all package managers
- Generates Homebrew tap repositories
- Creates AUR PKGBUILD files
- Handles dependency SHA256 calculation
- Advanced git operations

**Usage:**
```bash
# Full release to all package managers
./scripts/publish.sh 1.0.0

# Test release only
./scripts/publish.sh --test 1.0.0-rc1

# PyPI only
./scripts/publish.sh --pypi-only 1.0.1

# Dry run
./scripts/publish.sh --dry-run 1.0.0
```

## Prerequisites

Before running either script, ensure you have:

### Required Tools
- Python 3.8+
- Git
- pip
- twine (`pip install twine`)

### Optional Tools (for full automation)
- GitHub CLI (`gh`) for creating releases
- curl (for downloading and hashing files)
- Homebrew (for testing formulas)

### Authentication Setup

1. **PyPI Authentication**
   Create `~/.pypirc`:
   ```ini
   [distutils]
   index-servers = pypi testpypi

   [pypi]
   username = __token__
   password = pypi-YOUR_TOKEN_HERE

   [testpypi]
   repository = https://test.pypi.org/legacy/
   username = __token__
   password = pypi-YOUR_TESTPYPI_TOKEN_HERE
   ```

2. **GitHub Authentication** (optional)
   ```bash
   # For GitHub CLI
   gh auth login
   
   # Or set environment variable
   export GITHUB_TOKEN=your_token_here
   ```

## Release Process

### 1. Prepare for Release
```bash
# Ensure clean working directory
git status

# Run tests locally
python -m pytest

# Update CHANGELOG.md if needed
```

### 2. Choose Release Type

**Patch Release (1.0.1)**
```bash
./scripts/release.py 1.0.1
```

**Minor Release (1.1.0)**
```bash
./scripts/release.py 1.1.0
```

**Major Release (2.0.0)**
```bash
./scripts/release.py 2.0.0
```

**Pre-release (1.0.0-rc1)**
```bash
./scripts/release.py --test 1.0.0-rc1
```

### 3. Post-Release Tasks

After successful release:

1. **Verify PyPI Package**
   ```bash
   pip install git-smart-squash --upgrade
   git-smart-squash --help
   ```

2. **Submit to Package Managers** (if generated)
   - **Homebrew**: Submit PR to homebrew-core or update your tap
   - **conda-forge**: Fork staged-recipes and submit PR
   - **AUR**: Update your AUR package

3. **Update Documentation**
   - Update installation instructions
   - Announce release on relevant channels

## Generated Files

The scripts generate several files for package managers:

- `Formula/git-smart-squash.rb` - Homebrew formula
- `conda-recipe/meta.yaml` - conda-forge recipe
- `aur/PKGBUILD` - Arch Linux package
- `aur/.SRCINFO` - AUR metadata

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify PyPI tokens in `~/.pypirc`
   - Check GitHub authentication with `gh auth status`

2. **Version Conflicts**
   - Ensure version doesn't already exist on PyPI
   - Use pre-release versions for testing

3. **Test Failures**
   - Fix failing tests before release
   - Use `--skip-tests` only in emergencies

4. **Network Issues**
   - Retry failed uploads
   - Check network connectivity
   - Verify package manager endpoints are accessible

### Manual Recovery

If a script fails mid-process:

1. **Check git status**
   ```bash
   git status
   git log --oneline -5
   ```

2. **Reset if needed**
   ```bash
   git reset --hard HEAD~1  # If version commit was made
   git tag -d v1.0.0        # If tag was created
   ```

3. **Clean build artifacts**
   ```bash
   rm -rf dist/ build/ *.egg-info/
   ```

4. **Retry with manual steps**
   ```bash
   python setup.py sdist bdist_wheel
   twine upload dist/*
   ```

## Script Maintenance

To update the scripts:

1. **Add new package managers**: Extend the generation functions
2. **Update dependencies**: Modify the dependency lists and URLs
3. **Improve error handling**: Add more validation and recovery options
4. **Platform support**: Test on different operating systems

## Security Notes

- Never commit API tokens to version control
- Use environment variables or secure config files
- Regularly rotate API tokens
- Review generated files before submission to package managers