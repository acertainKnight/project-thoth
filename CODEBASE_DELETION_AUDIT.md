# Codebase File Deletion Audit Report

## Summary
This report documents all file deletion operations found in the Thoth codebase that could potentially affect user files.

## Critical Findings

### 1. **Note Regeneration Deletion** (HIGH RISK)
**Files:** 
- `/workspace/src/thoth/cli/notes.py` (lines 42-44)
- `/workspace/src/thoth/knowledge/graph.py` (lines 1022-1023)

**Operation:**
```python
if old_note_path and old_note_path.exists() and old_note_path != note_path:
    old_note_path.unlink()
    logger.info(f'Deleted old note file: {old_note_path}')
```

**Risk:** When regenerating notes, if the note title changes, the old note file is deleted. This could lead to data loss if:
- The regeneration process fails after deletion
- The user didn't intend to delete the old note
- The path comparison logic has bugs

### 2. **File Movement Operations** (MEDIUM RISK)
**File:** `/workspace/src/thoth/services/note_service.py` (lines 113, 119)

**Operation:**
```python
pdf_path.rename(final_pdf_path)
markdown_path.rename(final_markdown_path)
```

**Risk:** Files are moved/renamed without creating backups. If the target path is incorrect or if the operation fails partway, files could be lost.

### 3. **Cache Cleanup Operations** (LOW RISK)
**File:** `/workspace/src/thoth/services/cache_service.py`

**Operations:**
- Line 209: Removes cache files when hash changes
- Line 413: Removes expired cache files
- Lines 443, 547: Bulk cache cleanup operations

**Risk:** Generally safe as these only affect cache files, but could delete important files if cache directories are misconfigured.

### 4. **Query and Discovery Service Deletions** (LOW RISK)
**Files:**
- `/workspace/src/thoth/services/query_service.py` (line 145)
- `/workspace/src/thoth/services/discovery_service.py` (line 239)

**Risk:** These delete specific JSON files by name, relatively safe but could affect user data.

### 5. **PDF Download Cleanup** (LOW RISK)
**File:** `/workspace/src/thoth/mcp/tools/download_pdf_tool.py`

**Operations:**
- Line 260: Removes empty downloaded files
- Line 333: Cleans up partial downloads on error

**Risk:** Generally safe as it only removes problematic downloads.

## Potential Bug Scenarios

### Scenario 1: Incorrect Path Configuration
If `OBSIDIAN_DIR` or `NOTES_DIR` environment variables point to the wrong location (e.g., a parent directory instead of a subdirectory), file operations could affect unintended files.

### Scenario 2: Note Title Changes
The note regeneration logic deletes old notes when titles change. If multiple notes have similar titles or if the title generation logic changes, this could delete the wrong files.

### Scenario 3: Failed Rename Operations
The `rename()` operations in `note_service.py` don't have proper error handling. If the destination already exists or if there's a permission issue, files could be lost.

## Recommendations

1. **Add Backup Mechanism**: Before any delete/rename operation, create a backup copy
2. **Add Confirmation**: For note regeneration, ask for user confirmation before deleting old notes
3. **Implement Soft Delete**: Move files to a trash directory instead of permanent deletion
4. **Add Transaction Support**: Ensure all file operations can be rolled back on failure
5. **Improve Error Handling**: Add try-catch blocks around all file operations
6. **Add Safety Checks**: Verify paths are within expected directories before operations
7. **Implement File Recovery**: Add a command to recover recently deleted files

## Most Likely Cause of Your Issue

Based on the code analysis, the most likely cause of your Obsidian file deletion is the **note regeneration feature** in:
- `src/thoth/cli/notes.py`
- `src/thoth/knowledge/graph.py`

These functions delete old note files when regenerating notes with new titles. If this was triggered accidentally or if there was a bug in the path comparison logic, it could have deleted your Obsidian files.

## Next Steps

1. Check if the note regeneration command was recently run
2. Look for any logs mentioning "Deleted old note file"
3. Implement the safety recommendations above
4. Consider adding a file recovery mechanism