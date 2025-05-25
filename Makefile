.PHONY: install test lint format clean build docs help

# Default target
help:
	@echo "Git Smart Squash Development Commands"
	@echo "======================================"
	@echo "install     Install package in development mode"
	@echo "test        Run test suite"
	@echo "lint        Run linting checks"
	@echo "format      Format code with black"
	@echo "clean       Clean build artifacts"
	@echo "build       Build distribution packages"
	@echo "docs        Generate documentation"
	@echo "demo        Run demo on current repository"

# Install in development mode
install:
	pip install -e ".[dev]"

# Run tests
test:
	python -m pytest

# Run tests with coverage
test-cov:
	python -m pytest --cov=git_smart_squash --cov-report=html --cov-report=term

# Lint code
lint:
	flake8 git_smart_squash/
	mypy git_smart_squash/

# Format code
format:
	black git_smart_squash/
	black git_smart_squash/tests/

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
	python setup.py sdist bdist_wheel

# Generate documentation
docs:
	@echo "Documentation available in README.md"
	@echo "For API docs, install sphinx and run sphinx-build"

# Demo the tool on current repository
demo:
	python -m git_smart_squash.cli --dry-run --no-ai

# Development setup
dev-setup: install
	pre-commit install

# Run all quality checks
check: lint test

# Install pre-commit hooks
pre-commit:
	pre-commit install
	pre-commit run --all-files