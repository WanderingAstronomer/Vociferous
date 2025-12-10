# Quick Start: Creating Batch 1 Issues

This guide provides the fastest way to create all 4 Batch 1 issues for the Vociferous architecture documentation review.

## Prerequisites

- GitHub CLI (`gh`) installed
- Authenticated with GitHub (`gh auth login`)
- Write access to the repository

## Quick Create (3 steps)

### 1. Install and authenticate GitHub CLI (if needed)

```bash
# Install gh CLI (if not already installed)
# macOS
brew install gh

# Linux
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh

# Windows
winget install --id GitHub.cli

# Authenticate
gh auth login
```

### 2. Run the automated script

```bash
./create_batch1_issues.sh
```

That's it! The script will create all 4 issues and display their URLs.

### 3. Verify issues were created

```bash
# List all open issues
gh issue list

# Or view in browser
gh issue list --web
```

## What Gets Created

Running the script creates 4 issues:

1. **Issue #1**: [UPDATE] Rewrite ARCHITECTURE.md to reflect Canary-Qwen dual-pass design
   - Labels: `documentation`, `architecture`, `high-priority`
   - Most comprehensive, includes 10 major changes

2. **Issue #2**: [UPDATE] Add module architecture documentation
   - Labels: `documentation`, `architecture`
   - Documents all 9 modules

3. **Issue #3**: [CREATE] Document user help vs dev help CLI flag structure
   - Labels: `documentation`, `enhancement`, `cli`
   - Two-tier help system

4. **Issue #4**: [UPDATE] README.md - Remove streaming interface references
   - Labels: `documentation`, `bug`, `architecture`
   - Fixes batch vs streaming contradictions

## Manual Alternative

If you prefer to create issues one at a time:

```bash
# Issue #1
gh issue create \
  --title "[UPDATE] Rewrite ARCHITECTURE.md to reflect Canary-Qwen dual-pass design" \
  --body-file .github/ISSUE_TEMPLATE/01-rewrite-architecture-md.md \
  --label "documentation,architecture,high-priority"

# Issue #2
gh issue create \
  --title "[UPDATE] Add module architecture documentation" \
  --body-file .github/ISSUE_TEMPLATE/02-add-module-architecture-docs.md \
  --label "documentation,architecture"

# Issue #3
gh issue create \
  --title "[CREATE] Document user help vs dev help CLI flag structure" \
  --body-file .github/ISSUE_TEMPLATE/03-document-help-flags.md \
  --label "documentation,enhancement,cli"

# Issue #4
gh issue create \
  --title "[UPDATE] README.md - Remove streaming interface references" \
  --body-file .github/ISSUE_TEMPLATE/04-remove-streaming-references.md \
  --label "documentation,bug,architecture"
```

## Troubleshooting

### "command not found: gh"
Install GitHub CLI using the instructions in step 1 above.

### "not authenticated"
Run `gh auth login` and follow the prompts.

### "permission denied"
Make the script executable: `chmod +x create_batch1_issues.sh`

### "rate limit exceeded"
Wait a few minutes and try again, or create issues one at a time with delays between them.

## Next Steps After Creating Issues

1. ✅ Review the created issues in GitHub
2. ✅ Start with Issue #1 (highest priority)
3. ✅ Use `ISSUES_BATCH_1.md` to track progress
4. ✅ Reference `BATCH_1_SUMMARY.md` for detailed information

## Need More Information?

- **Detailed usage guide**: See `.github/ISSUE_TEMPLATE/README.md`
- **Issue tracker**: See `ISSUES_BATCH_1.md`
- **Implementation summary**: See `BATCH_1_SUMMARY.md`
- **Issue templates**: Browse `.github/ISSUE_TEMPLATE/` directory

## File Structure

```
.github/ISSUE_TEMPLATE/
├── 01-rewrite-architecture-md.md          # Issue #1 template
├── 02-add-module-architecture-docs.md     # Issue #2 template
├── 03-document-help-flags.md              # Issue #3 template
├── 04-remove-streaming-references.md      # Issue #4 template
├── config.yml                             # GitHub UI config
└── README.md                              # Detailed usage guide

BATCH_1_SUMMARY.md                         # Implementation summary
ISSUES_BATCH_1.md                          # Issue tracker
create_batch1_issues.sh                    # Automated creation script ⭐
```

---

**Quick tip**: Run `./create_batch1_issues.sh` and you're done! 🚀
