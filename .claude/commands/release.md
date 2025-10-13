---
name: Release
description: Create and manage GitHub releases for OEVK data
category: Release
tags: [release, github, workflow]
---

Create and manage GitHub releases with packaged OEVK data.

**Prerequisites**
- GitHub token set: `export GITHUB_TOKEN="ghp_your_token_here"`
- Data pipeline completed (staging and exports directories populated)
- GitHub CLI authenticated: `gh auth status`

**Common Release Commands**

1. **Validate data before release**:
   ```bash
   python -m src.cli release validate --staging-dir data/staging --exports-dir exports
   ```

2. **Create release with auto-generated tag**:
   ```bash
   python -m src.cli release create --repo-owner OWNER --repo-name REPO --auto
   ```

3. **Create release with specific tag**:
   ```bash
   python -m src.cli release create --repo-owner OWNER --repo-name REPO --tag 20250113-1200
   ```

4. **Create draft release for review**:
   ```bash
   python -m src.cli release create --repo-owner OWNER --repo-name REPO --auto --draft
   ```

5. **Create packages without upload** (for testing):
   ```bash
   python -m src.cli release create --repo-owner OWNER --repo-name REPO --auto --skip-upload
   ```

6. **Check release status**:
   ```bash
   python -m src.cli release status --repo-owner OWNER --repo-name REPO --tag TAG
   ```

7. **List recent releases**:
   ```bash
   python -m src.cli release history --repo-owner OWNER --repo-name REPO --limit 10
   ```

**Troubleshooting**

If GitHub authentication fails:
```bash
gh auth status
gh auth login --with-token <<< "$GITHUB_TOKEN"
```

For organization repositories, use **classic tokens** (not fine-grained):
- Go to GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)
- Create token with "repo" scope
- Token should start with "gho_" (classic) not "github_pat_" (fine-grained)

**Guidelines**
- Always validate data before creating a release
- Use `--draft` flag for testing releases
- Use `--skip-upload` for local testing without GitHub upload
- Release artifacts include CSV archive and database archive
- Tags format: YYYYMMDD-HHMM (auto-generated from current timestamp)
