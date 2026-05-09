# CLAUDE.md

Project-specific instructions for Claude Code.

## Git push policy

Pushing to `main` is **allowed** (Claude Code permission rule grants the capability), **but ALWAYS ask the user for confirmation in chat before running** any of the following:

- `git push origin HEAD:main`
- `git push origin <branch>:main`
- Any other push that updates the `main` branch
- Any `--force` or `--force-with-lease` push to a feature branch

Pattern: state what's about to be pushed (commit hash + one-line summary), wait for an explicit "yes" / "go" / "推" in chat, then execute.

Normal pushes to feature branches do not require confirmation.

## Project conventions

- Personal repo (Triprice): omit the `Co-Authored-By: Claude …` trailer in commits.
- Commit messages may be in Chinese; follow existing convention shown in `git log --oneline`.
