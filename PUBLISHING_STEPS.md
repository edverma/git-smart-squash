# Publishing Steps for git-smart-squash

This document outlines the steps to publish git-smart-squash to various package managers.

## Table of Contents
- [PyPI (Python Package Index)](#pypi-python-package-index)
- [Homebrew](#homebrew)
- [Prerequisites](#prerequisites)

## Prerequisites

Before publishing to any package manager, ensure:

1. **Version Management**: Update version in `setup.py` and `git_smart_squash/VERSION`
2. **Documentation**: Complete README.md with installation and usage instructions
3. **Testing**: All tests pass (`python -m pytest`)
4. **Git Repository**: Code is pushed to a public GitHub repository
5. **License**: Add a LICENSE file to your repository

## PyPI (Python Package Index)

### 1. Set Up PyPI Account
- Go to [https://pypi.org/account/register/](https://pypi.org/account/register/)
- Create an account and verify your email
- Go to [https://pypi.org/manage/account/#api-tokens](https://pypi.org/manage/account/#api-tokens)
- Create a new API token with "Entire account" scope
- Copy the token (starts with `pypi-`)

### 2. Install Publishing Tools
```bash
pip install --upgrade pip setuptools wheel twine
```

### 3. Configure Credentials
Create a `.pypirc` file in your home directory:
```bash
cat > ~/.pypirc << 'EOF'
[distutils]
index-servers = pypi testpypi

[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR_TESTPYPI_TOKEN_HERE
EOF
```

### 4. Build Distribution Files
```bash
cd /path/to/git-smart-squash
python setup.py sdist bdist_wheel
```

### 5. Test Upload to TestPyPI (Recommended)
```bash
twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ git-smart-squash
```

### 6. Upload to PyPI
```bash
twine upload dist/*
```

### 7. Verify Installation
```bash
pip install git-smart-squash
git-smart-squash --help
```

## Homebrew

Homebrew is a popular package manager for macOS and Linux. There are two ways to publish to Homebrew:

### Option 1: Submit to Homebrew Core (Recommended for Popular Tools)

#### Prerequisites
- Your tool must be stable and have a significant user base
- Must be a command-line tool (✅ git-smart-squash qualifies)
- Must have a tagged release on GitHub
- Must be installable via standard build tools

#### Steps

1. **Create a GitHub Release**
   ```bash
   # Tag and push a release
   git tag v0.1.0
   git push origin v0.1.0
   
   # Create release on GitHub with release notes
   # GitHub will automatically create source archives
   ```

2. **Get Source Archive Information**
   ```bash
   # Download the source archive from GitHub release
   curl -L https://github.com/yourusername/git-smart-squash/archive/v0.1.0.tar.gz -o git-smart-squash-0.1.0.tar.gz
   
   # Calculate SHA256 hash
   shasum -a 256 git-smart-squash-0.1.0.tar.gz
   ```

3. **Fork Homebrew Core Repository**
   - Go to [https://github.com/Homebrew/homebrew-core](https://github.com/Homebrew/homebrew-core)
   - Click "Fork" to create your own copy

4. **Create Formula File**
   ```bash
   # Clone your fork
   git clone https://github.com/yourusername/homebrew-core.git
   cd homebrew-core
   
   # Create new branch
   git checkout -b git-smart-squash
   
   # Create formula file
   touch Formula/git-smart-squash.rb
   ```

5. **Write the Formula**
   Add this content to `Formula/git-smart-squash.rb`:
   ```ruby
   class GitSmartSquash < Formula
     include Language::Python::Virtualenv

     desc "Automatically reorganize messy git commit histories into clean, semantic commits"
     homepage "https://github.com/yourusername/git-smart-squash"
     url "https://github.com/yourusername/git-smart-squash/archive/v0.1.0.tar.gz"
     sha256 "YOUR_SHA256_HASH_HERE"
     license "MIT"

     depends_on "python@3.12"

     resource "pyyaml" do
       url "https://files.pythonhosted.org/packages/cd/e5/af35f7ea75cf72f2cd079c95ee16797de7cd71f29ea7c68ae5ce7be1eda2b/PyYAML-6.0.2.tar.gz"
       sha256 "d584d9ec91ad65861cc08d42e834324ef890a082e591037abe114850ff7bbc3e"
     end

     resource "rich" do
       url "https://files.pythonhosted.org/packages/87/67/a37f6214d0e9fe57f6a3427b2d0b2b6e8d8f87a0b8a62b8a77ad8f6c5ee2/rich-14.0.0.tar.gz"
       sha256 "8260cda28e3db6bf04d2d1ef4dbc03ba80a824c88b0e7668a0f23126a424844a"
     end

     resource "openai" do
       url "https://files.pythonhosted.org/packages/source/o/openai/openai-1.44.0.tar.gz"
       sha256 "68a5fbc86e5c2eed8b93de9e4b9d574a0b4c9b4ae9b21b2d394e9d8e7ebcdf17"
     end

     resource "anthropic" do
       url "https://files.pythonhosted.org/packages/source/a/anthropic/anthropic-0.52.0.tar.gz"
       sha256 "4a5c84d2e7c9ace2c8f6a1c4e7c9a1c9e4d1e7e9e7e9e7e9e7e9e7e9e7e9e7e9"
     end

     resource "requests" do
       url "https://files.pythonhosted.org/packages/source/r/requests/requests-2.31.0.tar.gz"
       sha256 "942c5a758f98d790eaed1a29cb6eefc7ffb0d1cf7af05c3d2791656dbd6ad1e1"
     end

     def install
       virtualenv_install_with_resources
     end

     test do
       assert_match "usage: git-smart-squash", shell_output("#{bin}/git-smart-squash --help")
     end
   end
   ```

6. **Test the Formula Locally**
   ```bash
   # Install from local formula
   brew install --build-from-source ./Formula/git-smart-squash.rb
   
   # Test the installation
   git-smart-squash --help
   
   # Test the formula
   brew test git-smart-squash
   
   # Audit the formula
   brew audit --strict git-smart-squash
   ```

7. **Submit Pull Request**
   ```bash
   git add Formula/git-smart-squash.rb
   git commit -m "git-smart-squash: new formula"
   git push origin git-smart-squash
   ```
   
   - Go to your fork on GitHub
   - Click "New Pull Request"
   - Target the `master` branch of `Homebrew/homebrew-core`
   - Fill out the PR template with required information

### Option 2: Create Your Own Homebrew Tap (Easier for New Tools)

#### Steps

1. **Create a Homebrew Tap Repository**
   ```bash
   # Create repository named homebrew-tap
   # Repository must be named homebrew-SOMETHING
   git clone https://github.com/yourusername/homebrew-tap.git
   cd homebrew-tap
   ```

2. **Create Formula File**
   ```bash
   mkdir -p Formula
   touch Formula/git-smart-squash.rb
   ```

3. **Write the Formula** (same content as above)

4. **Commit and Push**
   ```bash
   git add .
   git commit -m "Add git-smart-squash formula"
   git push origin main
   ```

5. **Users Can Install Via Your Tap**
   ```bash
   # Add your tap
   brew tap yourusername/tap
   
   # Install your formula
   brew install git-smart-squash
   ```

### Formula Development Tips

1. **Resource URLs and Hashes**: Get exact URLs and SHA256 hashes from PyPI:
   ```bash
   # For each dependency, visit PyPI page and get source distribution URL
   # Calculate hash:
   curl -L "PACKAGE_URL" | shasum -a 256
   ```

2. **Test Thoroughly**:
   ```bash
   brew install --build-from-source ./Formula/git-smart-squash.rb
   brew test git-smart-squash
   brew audit --strict git-smart-squash
   brew uninstall git-smart-squash
   ```

3. **Follow Homebrew Guidelines**:
   - Read [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)
   - Follow [Homebrew's Acceptable Formulae](https://docs.brew.sh/Acceptable-Formulae)
   - Use `brew audit` to check for common issues

## Release Checklist

Before publishing to any package manager:

- [ ] Update version numbers in all relevant files
- [ ] Update CHANGELOG.md with release notes
- [ ] All tests passing
- [ ] Documentation is up to date
- [ ] GitHub release is created with proper tags
- [ ] Source code is clean and well-documented
- [ ] License file is included
- [ ] README.md includes installation instructions for all package managers

## Maintenance

After publishing:

1. **Monitor Issues**: Respond to bug reports and feature requests
2. **Update Dependencies**: Keep dependencies up to date
3. **Version Management**: Use semantic versioning for releases
4. **Security**: Monitor for security vulnerabilities in dependencies
5. **Documentation**: Keep documentation current with new features

## Additional Package Managers

Consider publishing to:
- **conda-forge**: For Python scientific community
- **Arch User Repository (AUR)**: For Arch Linux users
- **Snap Store**: Cross-platform Linux packages
- **Chocolatey**: Windows package manager
- **MacPorts**: Alternative macOS package manager

Each has its own submission process and requirements.