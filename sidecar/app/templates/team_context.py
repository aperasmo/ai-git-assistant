from __future__ import annotations

DEFAULT_TEAM_CONTEXT_TEMPLATE = """# AI Git Assistant Team Context

Keep this file practical, specific, and free of secrets. AI Git Assistant can use it to guide commit messages, pull request or merge request drafts, release notes, and change summaries for this repository.

## Purpose

Use this context to guide AI-generated commit messages, pull request or merge request drafts, release notes, and change summaries. Prefer guidance that helps reviewers understand intent, risk, and validation.

## Commit Message Style

- Respect the commit-message style selected in the app first: Detailed, Concise, Conventional, or Release.
- Use Conventional Commits when the user selects Conventional, or when no explicit style is selected and there is a clear type: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `build`, or `ci`.
- Keep the subject concise and specific, ideally under 72 characters.
- Use an imperative subject, for example `fix auth token handoff` instead of `fixed auth token handoff`.
- For multi-file changes, write one consolidated subject that describes the outcome, then add body bullets for the main areas changed.
- Do not split a change into multiple commits unless the user asks for that or the changes are truly unrelated.
- Prefer a body when the change affects behavior, data, permissions, release flow, CI, packaging, or user-facing workflows.

## Pull Request / Merge Request Style

- Use a clear title that describes the delivered outcome.
- Include a short Summary section with 2 to 5 bullets.
- Include a Validation section with tests run, manual checks, build results, or a note when validation was not run.
- Call out Risk or Rollback notes when the change touches auth, data, releases, installers, Git write actions, migrations, or provider integrations.
- Mention screenshots only when the change affects UI layout, visual state, or responsive behavior.

## Review Priorities

- Protect user data, credentials, tokens, and local repository state.
- Prefer preview-first and approval-first workflows for actions that write files, change Git history, publish releases, or push to remotes.
- Avoid destructive Git operations unless the user explicitly requests them and the app explains the consequence.
- Keep provider-specific behavior guarded by repository remote detection.
- Make error messages actionable: explain what happened, why it matters, and the safest next step.

## Testing Expectations

- Add or update focused unit tests for planner, parser, API, and Git workflow behavior.
- Add regression tests for every bug that reaches users.
- Run the smallest focused test first, then run the broader sidecar or frontend test/build when the change is shared or release-facing.
- For UI changes, verify small and wide layouts so command bars, panels, buttons, and text do not overlap.
- For release or installer changes, verify metadata version, sidecar build, Tauri build, and installer output on the matching platform.

## Documentation Expectations

- Update `README.md` when a feature changes user workflow, setup, permissions, platform support, or release behavior.
- Update `PROJECT_STATUS.md` with dated phase progress for roadmap-visible work.
- Keep release notes outcome-focused: what changed, why it matters, and what users can now do.

## Branching And Release Guidance

- Use short descriptive branch names, for example `fix/github-token-pull` or `feat/team-context`.
- Prefer tags like `v0.9.0` for app releases.
- Draft releases should include platform assets in the same release when possible.
- Do not publish a release until the tag, release notes, installer assets, and validation notes are reviewed.

## Tone

- Be direct, specific, and calm.
- Prefer practical engineering language over marketing language.
- When the change is broad, explain it as an outcome first, then list the important implementation areas.
"""
