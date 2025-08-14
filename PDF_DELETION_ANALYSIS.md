# PDF Deletion Analysis Report

## Critical Finding: PDF Files Are Being MOVED, Not Deleted

### The Problem

Your PDFs were not deleted - they were **moved and renamed** by the Thoth pipeline. Here's what happened:

1. **Environment Variable Configuration**:
   ```
   PDF_DIR=${OBSIDIAN_DIR}/papers/pdfs
   OBSIDIAN_DIR=/mnt/c/Users/nghal/Documents/Obsidian Vault/thoth
   ```
   This means your PDFs were originally in: `/mnt/c/Users/nghal/Documents/Obsidian Vault/thoth/papers/pdfs/`

2. **The Pipeline Process**:
   When Thoth processes a PDF, it:
   - Reads the PDF from the source location
   - Converts it to markdown
   - Analyzes the content
   - **MOVES the PDF to match the generated note title**

### The Critical Code

In `/workspace/src/thoth/services/note_service.py` (lines 110-113):

```python
# Move and rename PDF and Markdown files to match the note's title
final_pdf_path = self.pdf_dir / f'{note_stem}{pdf_path.suffix}'
if pdf_path.exists():
    pdf_path.rename(final_pdf_path)  # THIS MOVES THE FILE!
```

### What Actually Happened

1. Your PDFs were in your Obsidian vault at: `C:\Users\nghal\Documents\Obsidian Vault\thoth\papers\pdfs\`
2. When the pipeline processed them, it:
   - Generated new filenames based on the paper titles
   - **Moved** (not copied) the PDFs to new names in the same directory
3. If the pipeline ran in the container where `/mnt/c/` is not accessible, the files might have been moved to a local container path

### Why They Appear "Deleted"

1. **Renamed Files**: Your PDFs are likely still there but with different names based on paper titles
2. **Container Issue**: If run in a container without Windows mount access, files might have been moved to a container-local path
3. **Path Confusion**: The environment variable `${OBSIDIAN_DIR}` couldn't be resolved in the container

## Recovery Steps

### 1. Check for Renamed PDFs
Look in your original directory for PDFs with paper title names instead of original names:
```bash
# On Windows
dir "C:\Users\nghal\Documents\Obsidian Vault\thoth\papers\pdfs\*.pdf"
```

### 2. Check Container Storage
If the pipeline ran in a container, check:
```bash
find /workspace -name "*.pdf" -type f
find /data -name "*.pdf" -type f 2>/dev/null
find /home -name "*.pdf" -type f 2>/dev/null
```

### 3. Check Processing Logs
Look for logs showing where files were moved:
```bash
grep -r "Note generation completed" /workspace/logs
grep -r "new_pdf_path" /workspace/logs
```

## Root Cause

The issue is that `pdf_path.rename()` is a **destructive move operation**, not a copy. When combined with:
1. Container environments that can't access Windows paths
2. Environment variables that resolve differently in containers
3. No backup mechanism before moving files

This creates a perfect storm for "losing" files.

## Immediate Fix Needed

The code should be changed from:
```python
pdf_path.rename(final_pdf_path)  # Destructive move
```

To:
```python
import shutil
shutil.copy2(pdf_path, final_pdf_path)  # Non-destructive copy
```

## Prevention Recommendations

1. **Never use rename() on source files** - always copy instead
2. **Add pre-processing backup** - copy files to a backup directory first
3. **Validate paths** - ensure source and destination are accessible
4. **Add transaction support** - be able to rollback operations
5. **Log all file operations** - maintain an audit trail of moves/renames

## Most Likely Location of Your PDFs

Your PDFs are probably:
1. **Renamed in the original directory** with paper title names
2. **In a container-local directory** if run from Cursor's environment
3. **In the workspace** at a path like `/workspace/data/pdf/` with new names

The good news: They're likely not deleted, just moved and renamed!