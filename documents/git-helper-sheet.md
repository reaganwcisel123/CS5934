# Git Quickstart

We use a shared-repo model: no personal forks. You push feature branches
directly to the shared repo (`origin`).

## Daily workflow

```bash
# 1. Start from an up-to-date develop
git checkout develop
git pull origin develop

# 2. Branch for your work
git checkout -b feature/TICKET-123

# 3. Work, then commit
git add .
git commit -m "TICKET-123 short description of the change"

# 4. Push to the shared repo
git push -u origin feature/TICKET-123

```

## Branch names

`feature/TICKET-123`, `bug/TICKET-123` (prefix + ticket number).

## Rules of thumb

- One `origin` remote, no forks. Check with `git remote -v`.
- Keep branches small and focused on one ticket.
- Rebase or pull `develop` before opening a branch to stay current.
- Never commit straight to `main`; work lands in `develop` via feature branches.
