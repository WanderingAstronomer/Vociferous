#!/bin/bash
# Script to create GitHub issues from templates in .github/ISSUE_TEMPLATE/
# Usage: ./create_batch1_issues.sh

set -e

echo "Creating Batch 1 GitHub Issues for Vociferous..."
echo ""

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is not installed."
    echo "Please install it from https://cli.github.com/"
    exit 1
fi

# Check if we're authenticated
if ! gh auth status &> /dev/null; then
    echo "Error: Not authenticated with GitHub CLI."
    echo "Please run: gh auth login"
    exit 1
fi

echo "Creating Issue #1: Rewrite ARCHITECTURE.md to reflect Canary-Qwen dual-pass design"
ISSUE1=$(gh issue create \
    --title "[UPDATE] Rewrite ARCHITECTURE.md to reflect Canary-Qwen dual-pass design" \
    --body-file .github/ISSUE_TEMPLATE/01-rewrite-architecture-md.md \
    --label "documentation,architecture,high-priority" | grep -oP 'https://.*')
echo "✓ Created: $ISSUE1"
echo ""

echo "Creating Issue #2: Add module architecture documentation"
ISSUE2=$(gh issue create \
    --title "[UPDATE] Add module architecture documentation" \
    --body-file .github/ISSUE_TEMPLATE/02-add-module-architecture-docs.md \
    --label "documentation,architecture" | grep -oP 'https://.*')
echo "✓ Created: $ISSUE2"
echo ""

echo "Creating Issue #3: Document user help vs dev help CLI flag structure"
ISSUE3=$(gh issue create \
    --title "[CREATE] Document user help vs dev help CLI flag structure" \
    --body-file .github/ISSUE_TEMPLATE/03-document-help-flags.md \
    --label "documentation,enhancement,cli" | grep -oP 'https://.*')
echo "✓ Created: $ISSUE3"
echo ""

echo "Creating Issue #4: README.md - Remove streaming interface references"
ISSUE4=$(gh issue create \
    --title "[UPDATE] README.md - Remove streaming interface references" \
    --body-file .github/ISSUE_TEMPLATE/04-remove-streaming-references.md \
    --label "documentation,bug,architecture" | grep -oP 'https://.*')
echo "✓ Created: $ISSUE4"
echo ""

echo "=========================================="
echo "All 4 Batch 1 issues created successfully!"
echo "=========================================="
echo ""
echo "Issue #1: $ISSUE1"
echo "Issue #2: $ISSUE2"
echo "Issue #3: $ISSUE3"
echo "Issue #4: $ISSUE4"
echo ""
echo "Next steps:"
echo "1. Review the created issues"
echo "2. Start with Issue #1 (highest priority)"
echo "3. Reference ISSUES_BATCH_1.md for tracking"
