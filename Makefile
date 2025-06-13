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
	@echo "publish         Auto-bump patch version and publish to PyPI"
	@echo "publish-minor   Auto-bump minor version and publish to PyPI"
	@echo "publish-major   Auto-bump major version and publish to PyPI"
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

# Publish to PyPI (includes version bump, git tag, and upload)
publish: clean
	@echo "Publishing to PyPI..."
	@# Bump version
	@NEW_VERSION=$$(python3 scripts/bump_version.py patch | grep "New version:" | cut -d' ' -f3) && \
	echo "Bumped version to $$NEW_VERSION" && \
	git add git_smart_squash/VERSION && \
	git commit -m "chore: bump version to $$NEW_VERSION" && \
	git tag -a "v$$NEW_VERSION" -m "Release v$$NEW_VERSION" && \
	echo "Created git tag v$$NEW_VERSION" && \
	python3 -m build && \
	python3 -m twine upload dist/* && \
	git push origin "v$$NEW_VERSION" && \
	echo "✅ Successfully published version $$NEW_VERSION to PyPI and pushed tag!"

# Publish with minor version bump
publish-minor: clean
	@echo "Publishing with minor version bump..."
	@NEW_VERSION=$$(python3 scripts/bump_version.py minor | grep "New version:" | cut -d' ' -f3) && \
	echo "Bumped version to $$NEW_VERSION" && \
	git add git_smart_squash/VERSION && \
	git commit -m "chore: bump version to $$NEW_VERSION" && \
	git tag -a "v$$NEW_VERSION" -m "Release v$$NEW_VERSION" && \
	echo "Created git tag v$$NEW_VERSION" && \
	python3 -m build && \
	python3 -m twine upload dist/* && \
	git push origin "v$$NEW_VERSION" && \
	echo "✅ Successfully published version $$NEW_VERSION to PyPI and pushed tag!"

# Publish with major version bump
publish-major: clean
	@echo "Publishing with major version bump..."
	@NEW_VERSION=$$(python3 scripts/bump_version.py major | grep "New version:" | cut -d' ' -f3) && \
	echo "Bumped version to $$NEW_VERSION" && \
	git add git_smart_squash/VERSION && \
	git commit -m "chore: bump version to $$NEW_VERSION" && \
	git tag -a "v$$NEW_VERSION" -m "Release v$$NEW_VERSION" && \
	echo "Created git tag v$$NEW_VERSION" && \
	python3 -m build && \
	python3 -m twine upload dist/* && \
	git push origin "v$$NEW_VERSION" && \
	echo "✅ Successfully published version $$NEW_VERSION to PyPI and pushed tag!"

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