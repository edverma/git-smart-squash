.PHONY: install test lint format clean build bump-patch bump-minor bump-major publish publish-minor publish-major docs help

# Default target
help:
	@echo "Git Smart Squash Development Commands"
	@echo "======================================"
	@echo "install         Install package in development mode"
	@echo "test            Run test suite"
	@echo "lint            Run linting checks"
	@echo "format          Format code with black"
	@echo "clean           Clean build artifacts"
	@echo "build           Build distribution packages"
	@echo "bump-patch      Bump patch version (x.x.N)"
	@echo "bump-minor      Bump minor version (x.N.0)"
	@echo "bump-major      Bump major version (N.0.0)"
	@echo "release         Create GitHub release (auto-publishes to PyPI)"
	@echo "release-minor   Create minor release (auto-publishes to PyPI)"
	@echo "release-major   Create major release (auto-publishes to PyPI)"
	@echo "publish-local   Manually publish to PyPI (requires credentials)"
	@echo "publish-test    Publish to TestPyPI for testing"
	@echo "docs            Generate documentation"
	@echo "demo            Run demo on current repository"

# Install in development mode
install:
	pip install -e ".[dev]"

# Run tests
test:
	python3 -m pytest

# Run tests with coverage
test-cov:
	python3 -m pytest --cov=git_smart_squash --cov-report=html --cov-report=term

# Lint code
lint:
	flake8 git_smart_squash/ tests/
	mypy git_smart_squash/ tests/

# Format code
format:
	black git_smart_squash/
	black tests/

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

# Build distribution packages
build: clean
	python3 -m build

# Bump version (default: patch)
bump-patch:
	@python3 scripts/bump_version.py patch

bump-minor:
	@python3 scripts/bump_version.py minor

bump-major:
	@python3 scripts/bump_version.py major

# Create a new release (GitHub Actions will handle PyPI publishing)
release: clean
	@echo "Creating new release..."
	@# Bump version
	@NEW_VERSION=$$(python3 scripts/bump_version.py patch | grep "New version:" | cut -d' ' -f3) && \
	echo "Bumped version to $$NEW_VERSION" && \
	git add git_smart_squash/VERSION && \
	git commit -m "chore: bump version to $$NEW_VERSION" && \
	git push origin main && \
	echo "Creating GitHub release..." && \
	gh release create "v$$NEW_VERSION" --generate-notes && \
	echo "✅ Release v$$NEW_VERSION created! GitHub Actions will publish to PyPI."

# Create minor release
release-minor: clean
	@echo "Creating minor release..."
	@NEW_VERSION=$$(python3 scripts/bump_version.py minor | grep "New version:" | cut -d' ' -f3) && \
	echo "Bumped version to $$NEW_VERSION" && \
	git add git_smart_squash/VERSION && \
	git commit -m "chore: bump version to $$NEW_VERSION" && \
	git push origin main && \
	gh release create "v$$NEW_VERSION" --generate-notes && \
	echo "✅ Release v$$NEW_VERSION created! GitHub Actions will publish to PyPI."

# Create major release
release-major: clean
	@echo "Creating major release..."
	@NEW_VERSION=$$(python3 scripts/bump_version.py major | grep "New version:" | cut -d' ' -f3) && \
	echo "Bumped version to $$NEW_VERSION" && \
	git add git_smart_squash/VERSION && \
	git commit -m "chore: bump version to $$NEW_VERSION" && \
	git push origin main && \
	gh release create "v$$NEW_VERSION" --generate-notes && \
	echo "✅ Release v$$NEW_VERSION created! GitHub Actions will publish to PyPI."

# Local publish for testing (requires PyPI credentials)
publish-local: clean build
	@echo "Publishing to PyPI using local credentials..."
	@echo "⚠️  WARNING: Consider using 'make release' for secure OIDC-based publishing instead!"
	@python3 -m twine upload dist/*

# Publish to TestPyPI for testing
publish-test: clean build
	@echo "Publishing to TestPyPI..."
	@python3 -m twine upload --repository testpypi dist/*

# Generate documentation
docs:
	@echo "Documentation available in README.md"
	@echo "For API docs, install sphinx and run sphinx-build"

# Demo the tool on current repository
demo:
	python3 -m git_smart_squash.cli --no-ai

# Development setup
dev-setup: install
	pre-commit install

# Run all quality checks
check: lint test

# Install pre-commit hooks
pre-commit:
	pre-commit install
	pre-commit run --all-files