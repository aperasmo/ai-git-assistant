# AI Git Assistant Command Reference

Native Git syntax is the default parsing path. Supported commands such as `git status --short --branch`, `git remote -v`, `git diff --stat`, and `git add <paths>` resolve deterministically before natural-language matching. Write operations always create a reviewed plan before anything changes, and arbitrary shell execution remains disabled.

Provider awareness is per selected repository. The app reads configured remotes and labels GitHub, GitLab, Bitbucket, Azure DevOps, unknown, local-only, and mixed-provider repositories in the right panel. Standard Git commands work across providers; platform-specific actions explain when the selected provider is not supported yet.

## Read Commands

Read commands run immediately and never modify the repository.

| Request examples | Git command family | Notes |
|---|---|---|
| `status`, `git status`, `git status --short --branch`, `what changed?` | `git status --porcelain=v2 --branch` | Shows staged, modified, untracked, conflicts, ahead/behind. |
| `show diff`, `show me the diff`, `diff` | `git diff HEAD --patch` | Full patch diff with local line highlighting. |
| `show staged diff` | `git diff --cached --patch` | Shows staged patch only. |
| `show unstaged diff` | `git diff --patch` | Shows working-tree patch only. |
| `log`, `show commits`, `last 10 commits` | `git log -n<N>` | Bounded to 50 commits. |
| `show commit graph`, `graph`, `history graph` | `git log --graph --decorate --oneline --all` | Visual commit graph across refs. |
| `show branches`, `list branches` | `git branch --format=...` | Shows current local branch and upstream. |
| `show stashes`, `stash list` | `git stash list` | Lists saved stash entries. |
| `inspect stash@{0}`, `show stash@{1}` | `git stash show --patch --stat` | Shows one stash without applying it. |
| `show remotes`, `list remotes` | `git remote -v` | Shows configured fetch/push URLs. |
| `show tags`, `list tags` | `git tag --list` | Lists local release tags. |
| `show tag v0.3.0`, `inspect tag v0.3.0` | `git show --stat v0.3.0` | Shows one tag without changing the repo. |
| `history README.md`, `file history src/App.tsx` | `git log --follow -- <path>` | File-specific commit history. |
| `blame README.md`, `who touched src/App.tsx` | `git blame -- <path>` | Line authorship for one file. |
| `show conflicts`, `merge conflicts` | status plus file snippets | Shows conflicted files, marker snippets, and next steps. |
| `fetch`, `refresh remote status` | `git fetch --prune` | Refreshes remote tracking metadata only. |

## Write Commands

Write commands show an approval plan first.

### Stage Files

```text
stage src/login.py
stage src/login.py and src/auth.py
add frontend/src/Login.tsx
```

Runs `git add -- <file> ...`. Wildcards, `.`, and vague `all files` staging are blocked.

### Commit

```text
commit src/login.py with message "Add login validation"
commit my changes with message "Fix layout"
commit staged changes with message "Fix edge case"
```

Selected-file commits resolve paths against the current changed-file snapshot. `commit my changes` stages all modified and untracked files after showing every path in the plan.

### Push

```text
push
push current branch
push to main
```

Runs a non-force push for the current branch only. New branches use `--set-upstream` when a safe remote can be chosen.

### Commit Then Push

```text
commit src/login.py with message "Add login validation", then push
commit my changes with message "Deploy hotfix", then push
```

Creates one reviewed plan: stage, commit, then push.

### Pull

```text
pull
git pull
sync with remote
```

Runs `git pull --ff-only`. Diverged branches are blocked instead of creating a merge commit.

### Unstage

```text
unstage src/login.py
remove login.py from staging
```

Runs `git restore --staged -- <file> ...`.

### Revert Commit

```text
revert a1b2c3d
git revert a1b2c3d
```

Creates a new commit that reverses one regular commit after approval. The working tree must be clean. Merge commits are rejected because they require choosing a mainline parent, and a conflict-producing revert is automatically aborted without leaving a partial revert in progress.

### Discard

```text
discard login.py
discard changes in login.py
```

Runs `git restore -- <file> ...` and is marked DESTRUCTIVE in the plan.

### Branches

```text
switch to main
checkout feature/auth
create branch feature/auth
delete branch old-feature
```

Switch is blocked when uncommitted changes would be at risk. Delete uses safe `git branch -d`, never force delete.

### Stash

```text
stash
stash with message "WIP login form"
stash pop
apply stash stash@{0}
drop stash stash@{0}
```

`stash pop` restores and removes the most recent stash. `apply stash stash@{0}` restores a specific stash and keeps it. `drop stash stash@{0}` is marked DESTRUCTIVE before approval.

### Merge And Conflicts

```text
merge feature/auth
show conflicts
stage README.md
continue merge
abort merge
```

Merge requires a clean working tree and runs `git merge --no-edit <branch>`. If conflicts occur, the app reports the conflicted files, shows conflict marker snippets, allows staging resolved conflicted files, and then completes the merge with `git commit --no-edit`. `abort merge` runs `git merge --abort`.

### Release Tags

```text
show tags
show tag v0.3.0
create tag v0.3.0 with message "Release v0.3.0"
push tag v0.3.0
delete tag v0.3.0
```

Creates annotated local tags with `git tag -a <tag> -m <message>`. `push tag` publishes one explicit tag only, never every local tag. `delete tag` removes the local tag and is marked DESTRUCTIVE before approval.

## Always Blocked

| Command family | Why |
|---|---|
| `git push --force` | Can destroy remote history. |
| `git reset --hard` | Irreversible local destruction. |
| `git clean -f` | Permanently deletes untracked files. |
| `git add .` / `git add *` | Hides accidental inclusions. |
| Cross-branch push | The app never silently pushes one local branch to a differently named remote branch. |
| Submodule operations | Submodule repositories are not supported yet. |
