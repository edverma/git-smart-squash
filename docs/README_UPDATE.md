# README Update for Native Git Operations

Add this section to the main README.md:

## 🚀 New: Native Git Operations (Experimental)

Git Smart Squash now supports native Git operations mode which resolves line number shift issues when applying multiple changes to the same file.

### Enable Native Mode

Add to your `.git-smart-squash.yml`:

```yaml
feature_flags:
  use_native_git_operations: true
```

This feature:
- ✅ Handles line number shifts automatically
- ✅ Uses Git's native merge algorithms
- ✅ Provides atomic commit operations
- ✅ Creates automatic backups

See [Native Git Migration Guide](docs/NATIVE_GIT_MIGRATION.md) for details.