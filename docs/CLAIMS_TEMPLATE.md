# Task claims (template for any project)

Copy this file into a project as `docs/CLAIMS.md` and point to it from that project's
CLAUDE.md with one line: "Before starting any task, read docs/CLAIMS.md on every working
branch, claim the task there, commit and push at once, and follow its rules."

## Rules

1. Before starting a task, `git fetch origin` and read `docs/CLAIMS.md` on every working
   branch; check nobody else holds the task.
2. Claim it here with your branch name and the date; commit and push at once. Hold one
   task "active" and at most three "next".
3. Take over someone else's claim only with the owner's say-so, or when it hasn't moved for
   a week (note it here).
4. Work on your own branch; merge through pull requests; the owner approves merges to
   `main`.
5. Shared status / to-do files: add only your own dated section or edit only your own
   task's lines.
6. When a task is finished, move it to "Done" and promote your next claim to active.
7. Every pull request runs the project's tests before it is opened.

## Claimed

| Task | What | Status | Branch | Since |
| --- | --- | --- | --- | --- |

## Done
