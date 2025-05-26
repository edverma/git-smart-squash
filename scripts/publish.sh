#!/bin/bash

# Git Smart Squash - Automated Publishing Script
# This script automates the publishing process to multiple package managers

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PACKAGE_NAME="git-smart-squash"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Helper functions
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is not installed or not in PATH"
        return 1
    fi
}

check_git_status() {
    if [[ -n $(git status --porcelain) ]]; then
        log_error "Git working directory is not clean. Please commit or stash changes."
        git status --short
        return 1
    fi
}

get_current_version() {
    python3 -c "import sys; sys.path.insert(0, '$PROJECT_ROOT'); from git_smart_squash import __version__; print(__version__)"
}

validate_version() {
    local version=$1
    if [[ ! $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_error "Invalid version format. Use semantic versioning (e.g., 1.0.0)"
        return 1
    fi
}

update_version() {
    local new_version=$1
    log_info "Updating version to $new_version"
    
    # Update setup.py
    sed -i.bak "s/version=\"[^\"]*\"/version=\"$new_version\"/" "$PROJECT_ROOT/setup.py"
    
    # Update VERSION file
    echo "$new_version" > "$PROJECT_ROOT/git_smart_squash/VERSION"
    
    # Update __init__.py
    sed -i.bak "s/__version__ = \"[^\"]*\"/__version__ = \"$new_version\"/" "$PROJECT_ROOT/git_smart_squash/__init__.py"
    
    # Clean up backup files
    rm -f "$PROJECT_ROOT/setup.py.bak" "$PROJECT_ROOT/git_smart_squash/__init__.py.bak"
}

run_tests() {
    log_info "Running tests..."
    cd "$PROJECT_ROOT"
    python3 -m pytest -xvs
    log_success "All tests passed"
}

build_package() {
    log_info "Building package..."
    cd "$PROJECT_ROOT"
    
    # Clean previous builds
    rm -rf dist/ build/ *.egg-info/
    
    # Build source and wheel distributions
    python3 setup.py sdist bdist_wheel
    
    log_success "Package built successfully"
}

publish_to_pypi() {
    local test_only=$1
    
    if [[ "$test_only" == "true" ]]; then
        log_info "Publishing to TestPyPI..."
        twine upload --repository testpypi dist/*
        log_success "Published to TestPyPI"
        
        log_info "Testing installation from TestPyPI..."
        pip3 install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "$PACKAGE_NAME" --upgrade --force-reinstall
        log_success "TestPyPI installation successful"
    else
        log_info "Publishing to PyPI..."
        twine upload dist/*
        log_success "Published to PyPI"
    fi
}

create_github_release() {
    local version=$1
    local tag="v$version"
    
    log_info "Creating GitHub release $tag..."
    
    # Create tag
    git tag "$tag"
    git push origin "$tag"
    
    # Create release using GitHub CLI (if available)
    if command -v gh &> /dev/null; then
        gh release create "$tag" \
            --title "Release $tag" \
            --notes "Release $version - See CHANGELOG.md for details" \
            --latest
        log_success "GitHub release created"
    else
        log_warning "GitHub CLI not found. Please create the release manually at:"
        log_warning "https://github.com/yourusername/$PACKAGE_NAME/releases/new?tag=$tag"
    fi
}

generate_homebrew_formula() {
    local version=$1
    local tag="v$version"
    local formula_file="$PROJECT_ROOT/Formula/$PACKAGE_NAME.rb"
    
    log_info "Generating Homebrew formula..."
    
    # Create Formula directory
    mkdir -p "$PROJECT_ROOT/Formula"
    
    # Download and calculate SHA256 of source archive
    local archive_url="https://github.com/yourusername/$PACKAGE_NAME/archive/$tag.tar.gz"
    local temp_file=$(mktemp)
    
    log_info "Downloading source archive to calculate SHA256..."
    curl -L "$archive_url" -o "$temp_file"
    local sha256=$(shasum -a 256 "$temp_file" | cut -d' ' -f1)
    rm -f "$temp_file"
    
    # Get dependency hashes from PyPI
    local pyyaml_sha=$(curl -s https://pypi.org/pypi/PyYAML/json | python3 -c "import sys, json; data=json.load(sys.stdin); print([f for f in data['releases']['6.0.2'] if f['filename'].endswith('.tar.gz')][0]['digests']['sha256'])")
    local rich_sha=$(curl -s https://pypi.org/pypi/rich/json | python3 -c "import sys, json; data=json.load(sys.stdin); print([f for f in data['releases']['14.0.0'] if f['filename'].endswith('.tar.gz')][0]['digests']['sha256'])")
    local openai_sha=$(curl -s https://pypi.org/pypi/openai/json | python3 -c "import sys, json; data=json.load(sys.stdin); print([f for f in data['releases']['1.44.0'] if f['filename'].endswith('.tar.gz')][0]['digests']['sha256'])")
    local anthropic_sha=$(curl -s https://pypi.org/pypi/anthropic/json | python3 -c "import sys, json; data=json.load(sys.stdin); print([f for f in data['releases']['0.52.0'] if f['filename'].endswith('.tar.gz')][0]['digests']['sha256'])")
    local requests_sha=$(curl -s https://pypi.org/pypi/requests/json | python3 -c "import sys, json; data=json.load(sys.stdin); print([f for f in data['releases']['2.31.0'] if f['filename'].endswith('.tar.gz')][0]['digests']['sha256'])")
    
    cat > "$formula_file" << EOF
class GitSmartSquash < Formula
  include Language::Python::Virtualenv

  desc "Automatically reorganize messy git commit histories into clean, semantic commits"
  homepage "https://github.com/yourusername/$PACKAGE_NAME"
  url "$archive_url"
  sha256 "$sha256"
  license "MIT"

  depends_on "python@3.12"

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/cd/e5/af35f7ea75cf72f2cd079c95ee16797de7cd71f29ea7c68ae5ce7be1eda2b/PyYAML-6.0.2.tar.gz"
    sha256 "$pyyaml_sha"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/87/67/a37f6214d0e9fe57f6a3427b2d0b2b6e8d8f87a0b8a62b8a77ad8f6c5ee2/rich-14.0.0.tar.gz"
    sha256 "$rich_sha"
  end

  resource "openai" do
    url "https://files.pythonhosted.org/packages/source/o/openai/openai-1.44.0.tar.gz"
    sha256 "$openai_sha"
  end

  resource "anthropic" do
    url "https://files.pythonhosted.org/packages/source/a/anthropic/anthropic-0.52.0.tar.gz"
    sha256 "$anthropic_sha"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/source/r/requests/requests-2.31.0.tar.gz"
    sha256 "$requests_sha"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "usage: git-smart-squash", shell_output("#{bin}/git-smart-squash --help")
  end
end
EOF

    log_success "Homebrew formula generated at $formula_file"
}

create_homebrew_tap() {
    local version=$1
    local tap_repo="https://github.com/yourusername/homebrew-tap.git"
    local temp_dir=$(mktemp -d)
    
    log_info "Creating/updating Homebrew tap..."
    
    # Clone or create tap repository
    if git clone "$tap_repo" "$temp_dir" 2>/dev/null; then
        log_info "Cloned existing tap repository"
    else
        log_warning "Tap repository not found. Creating local formula only."
        log_warning "Please create a repository at: $tap_repo"
        return 0
    fi
    
    cd "$temp_dir"
    
    # Copy formula
    mkdir -p Formula
    cp "$PROJECT_ROOT/Formula/$PACKAGE_NAME.rb" "Formula/"
    
    # Commit and push
    git add Formula/
    git commit -m "$PACKAGE_NAME: update to $version"
    git push origin main
    
    log_success "Homebrew tap updated"
    
    # Cleanup
    rm -rf "$temp_dir"
}

generate_conda_recipe() {
    local version=$1
    local recipe_dir="$PROJECT_ROOT/conda-recipe"
    
    log_info "Generating conda recipe..."
    
    mkdir -p "$recipe_dir"
    
    cat > "$recipe_dir/meta.yaml" << EOF
{% set name = "$PACKAGE_NAME" %}
{% set version = "$version" %}

package:
  name: {{ name|lower }}
  version: {{ version }}

source:
  url: https://pypi.io/packages/source/{{ name[0] }}/{{ name }}/{{ name }}-{{ version }}.tar.gz
  sha256: # Add SHA256 from PyPI

build:
  number: 0
  script: python -m pip install . -vv
  entry_points:
    - git-smart-squash = git_smart_squash.cli:main

requirements:
  host:
    - python >=3.8
    - pip
  run:
    - python >=3.8
    - pyyaml >=6.0
    - rich >=13.0.0
    - openai >=1.0.0
    - anthropic >=0.3.0
    - requests >=2.28.0

test:
  imports:
    - git_smart_squash
  commands:
    - git-smart-squash --help

about:
  home: https://github.com/yourusername/$PACKAGE_NAME
  license: MIT
  license_family: MIT
  license_file: LICENSE
  summary: Automatically reorganize messy git commit histories into clean, semantic commits
  description: |
    Git Smart Squash uses AI and heuristics to automatically group related commits
    and generate meaningful commit messages following conventional commit standards.
  doc_url: https://github.com/yourusername/$PACKAGE_NAME
  dev_url: https://github.com/yourusername/$PACKAGE_NAME

extra:
  recipe-maintainers:
    - yourusername
EOF

    log_success "Conda recipe generated at $recipe_dir/meta.yaml"
    log_info "To publish to conda-forge:"
    log_info "1. Fork https://github.com/conda-forge/staged-recipes"
    log_info "2. Add recipe to recipes/$PACKAGE_NAME/"
    log_info "3. Submit pull request"
}

generate_aur_pkgbuild() {
    local version=$1
    local pkgbuild_dir="$PROJECT_ROOT/aur"
    
    log_info "Generating AUR PKGBUILD..."
    
    mkdir -p "$pkgbuild_dir"
    
    cat > "$pkgbuild_dir/PKGBUILD" << EOF
# Maintainer: Your Name <your.email@example.com>
pkgname=$PACKAGE_NAME
pkgver=$version
pkgrel=1
pkgdesc="Automatically reorganize messy git commit histories into clean, semantic commits"
arch=('any')
url="https://github.com/yourusername/$PACKAGE_NAME"
license=('MIT')
depends=('python' 'python-pip')
makedepends=('python-build' 'python-installer' 'python-wheel')
source=("https://pypi.org/packages/source/g/\$pkgname/\$pkgname-\$pkgver.tar.gz")
sha256sums=('SKIP')  # Update with actual SHA256

build() {
    cd "\$pkgname-\$pkgver"
    python -m build --wheel --no-isolation
}

package() {
    cd "\$pkgname-\$pkgver"
    python -m installer --destdir="\$pkgdir" dist/*.whl
}
EOF

    cat > "$pkgbuild_dir/.SRCINFO" << EOF
pkgbase = $PACKAGE_NAME
	pkgdesc = Automatically reorganize messy git commit histories into clean, semantic commits
	pkgver = $version
	pkgrel = 1
	url = https://github.com/yourusername/$PACKAGE_NAME
	arch = any
	license = MIT
	makedepends = python-build
	makedepends = python-installer
	makedepends = python-wheel
	depends = python
	depends = python-pip
	source = https://pypi.org/packages/source/g/$PACKAGE_NAME/$PACKAGE_NAME-$version.tar.gz
	sha256sums = SKIP

pkgname = $PACKAGE_NAME
EOF

    log_success "AUR PKGBUILD generated at $pkgbuild_dir/"
    log_info "To publish to AUR:"
    log_info "1. Create account at https://aur.archlinux.org/"
    log_info "2. git clone ssh://aur@aur.archlinux.org/$PACKAGE_NAME.git"
    log_info "3. Copy PKGBUILD and .SRCINFO to the cloned repo"
    log_info "4. Update sha256sums with: updpkgsums"
    log_info "5. git add ., git commit, git push"
}

show_help() {
    cat << EOF
Git Smart Squash Publishing Script

Usage: $0 [OPTIONS] <VERSION>

OPTIONS:
    -h, --help              Show this help message
    -t, --test             Publish to test repositories only
    -p, --pypi-only        Publish to PyPI only
    -s, --skip-tests       Skip running tests
    -n, --dry-run          Show what would be done without executing
    
ARGUMENTS:
    VERSION                New version number (e.g., 1.0.0)

EXAMPLES:
    $0 1.0.0               # Full release to all package managers
    $0 --test 1.0.0-rc1    # Test release only
    $0 --pypi-only 1.0.1   # PyPI release only
    
ENVIRONMENT VARIABLES:
    PYPI_TOKEN            PyPI API token (or use ~/.pypirc)
    GITHUB_TOKEN          GitHub token for creating releases
EOF
}

main() {
    local new_version=""
    local test_only=false
    local pypi_only=false
    local skip_tests=false
    local dry_run=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -t|--test)
                test_only=true
                shift
                ;;
            -p|--pypi-only)
                pypi_only=true
                shift
                ;;
            -s|--skip-tests)
                skip_tests=true
                shift
                ;;
            -n|--dry-run)
                dry_run=true
                shift
                ;;
            -*)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                if [[ -z "$new_version" ]]; then
                    new_version=$1
                else
                    log_error "Multiple versions specified"
                    exit 1
                fi
                shift
                ;;
        esac
    done
    
    # Validate arguments
    if [[ -z "$new_version" ]]; then
        log_error "Version number is required"
        show_help
        exit 1
    fi
    
    validate_version "$new_version"
    
    # Show what will be done
    log_info "Publishing $PACKAGE_NAME version $new_version"
    if [[ "$test_only" == "true" ]]; then
        log_info "Mode: Test repositories only"
    elif [[ "$pypi_only" == "true" ]]; then
        log_info "Mode: PyPI only"
    else
        log_info "Mode: Full release to all package managers"
    fi
    
    if [[ "$dry_run" == "true" ]]; then
        log_warning "DRY RUN MODE - No changes will be made"
        return 0
    fi
    
    # Confirmation
    echo
    read -p "Continue with publication? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Publication cancelled"
        exit 0
    fi
    
    # Prerequisites check
    log_info "Checking prerequisites..."
    check_command python3
    check_command git
    check_command pip3
    
    if [[ "$test_only" == "false" && "$pypi_only" == "false" ]]; then
        check_command curl
    fi
    
    cd "$PROJECT_ROOT"
    
    # Check git status
    check_git_status
    
    # Get current version
    local current_version=$(get_current_version)
    log_info "Current version: $current_version"
    log_info "New version: $new_version"
    
    # Update version numbers
    update_version "$new_version"
    
    # Run tests
    if [[ "$skip_tests" == "false" ]]; then
        run_tests
    else
        log_warning "Skipping tests"
    fi
    
    # Build package
    build_package
    
    # Commit version changes
    git add .
    git commit -m "chore: bump version to $new_version"
    
    # Publish to PyPI
    if [[ "$test_only" == "true" ]]; then
        publish_to_pypi true
        log_success "Test publication complete"
        return 0
    else
        publish_to_pypi false
    fi
    
    # Push changes and create release
    git push origin main
    create_github_release "$new_version"
    
    if [[ "$pypi_only" == "true" ]]; then
        log_success "PyPI publication complete"
        return 0
    fi
    
    # Generate package manager files
    generate_homebrew_formula "$new_version"
    create_homebrew_tap "$new_version"
    generate_conda_recipe "$new_version"
    generate_aur_pkgbuild "$new_version"
    
    # Final instructions
    echo
    log_success "Publication complete!"
    echo
    log_info "Next steps:"
    log_info "1. Homebrew formula created at Formula/$PACKAGE_NAME.rb"
    log_info "2. Conda recipe created at conda-recipe/meta.yaml"
    log_info "3. AUR PKGBUILD created at aur/PKGBUILD"
    echo
    log_info "Manual steps required:"
    log_info "- Submit conda-forge recipe PR"
    log_info "- Publish AUR package"
    log_info "- Consider submitting to Homebrew core"
    echo
    log_info "Installation commands:"
    log_info "  pip install $PACKAGE_NAME"
    log_info "  brew tap yourusername/tap && brew install $PACKAGE_NAME"
}

# Run main function with all arguments
main "$@"