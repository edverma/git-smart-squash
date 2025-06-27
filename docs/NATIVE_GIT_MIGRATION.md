# Native Git Operations Migration Guide

## Overview

Git Smart Squash now supports a native Git operations mode that resolves the line number shift issues that could occur with the patch-based approach. This new implementation uses Git's built-in commit and merge operations instead of manually applying patches.

## Benefits

1. **Resolves Line Number Shifts**: When multiple hunks modify the same file, Git automatically handles line number adjustments
2. **Better Conflict Handling**: Leverages Git's 20+ years of merge algorithms
3. **Atomic Operations**: All-or-nothing commit application with automatic rollback
4. **Safer**: Automatic backup branches and working directory management

## Enabling Native Git Operations

### Method 1: Configuration File

Create or modify your `.git-smart-squash.yml` file:

```yaml
feature_flags:
  use_native_git_operations: true
```

You can place this file in:
- Your project root (`.git-smart-squash.yml`)
- Your home directory (`~/.git-smart-squash.yml`)

### Method 2: Environment Variable (Coming Soon)

```bash
export GSS_USE_NATIVE_GIT=true
git-smart-squash
```

## How It Works

1. **Backup Creation**: Creates a backup branch before any operations
2. **Clean Working Directory**: Stashes any uncommitted changes
3. **Temporary Branch**: All operations happen on a temporary branch
4. **Atomic Commits**: Each commit group is applied atomically
5. **Cherry-pick**: Successful commits are cherry-picked to your original branch
6. **Cleanup**: Temporary branches are removed, working directory restored

## Migration Checklist

- [ ] Ensure you have Git 2.0.0 or later
- [ ] Create a configuration file with the feature flag enabled
- [ ] Test on a non-critical branch first
- [ ] Report any issues to the GitHub repository

## Rollback

If you encounter issues, you can disable native operations:

```yaml
feature_flags:
  use_native_git_operations: false
```

Your backup branches are preserved with names like `branch-name-backup-timestamp`.

## Example

```bash
# Create config file
cat > .git-smart-squash.yml << EOF
feature_flags:
  use_native_git_operations: true
EOF

# Run git-smart-squash
git-smart-squash --base main

# You'll see:
# [cyan]Using native Git operations (experimental)[/cyan]
```

## Troubleshooting

### Issue: "Not a valid Git repository"
**Solution**: Ensure you're in a Git repository with `git status`

### Issue: "Git version too old"
**Solution**: Update Git to version 2.0.0 or later

### Issue: Commits not appearing
**Solution**: Check if commits were created on the temporary branch. Look for backup branches with `git branch -a`

## Future Enhancements

- Parallel processing for independent commits
- Automatic conflict resolution
- Binary file support
- Large file optimizations