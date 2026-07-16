from __future__ import annotations

from app.errors import ValidationFailure
from app.schemas.repositories import ActionPlanStep, PlanStepKind, RepositorySnapshot

_WILDCARD_SENTINELS = frozenset([".", "*", "all", "**", "./", "*.*"])
_KINDS_REQUIRING_PATHS = frozenset([PlanStepKind.STAGE, PlanStepKind.UNSTAGE, PlanStepKind.DISCARD])
_KINDS_REQUIRING_REMOTE = frozenset([PlanStepKind.PUSH, PlanStepKind.PULL, PlanStepKind.SET_UPSTREAM])
_KINDS_REQUIRING_STASH_REF = frozenset([PlanStepKind.STASH_APPLY, PlanStepKind.STASH_DROP])
_KINDS_REQUIRING_TAG = frozenset([
    PlanStepKind.CREATE_TAG,
    PlanStepKind.DELETE_TAG,
    PlanStepKind.PUSH_TAG,
])
_KINDS_REQUIRING_BRANCH = frozenset([
    PlanStepKind.SWITCH,
    PlanStepKind.CREATE_BRANCH,
    PlanStepKind.DELETE_BRANCH,
    PlanStepKind.MERGE,
    PlanStepKind.SET_UPSTREAM,
])


def validate_llm_steps(
    steps: list[dict],
    snapshot: RepositorySnapshot,
) -> list[ActionPlanStep]:
    if not steps:
        raise ValidationFailure("The AI returned an empty plan with no steps.")
    if len(steps) > 8:
        raise ValidationFailure("The AI returned too many steps. Request a new plan.")

    known_changed = {
        item.path
        for item in [*snapshot.staged_changes, *snapshot.modified_changes, *snapshot.untracked_paths]
    }
    known_remotes = set(snapshot.remote_names)

    result: list[ActionPlanStep] = []

    for raw in steps:
        if not isinstance(raw, dict):
            raise ValidationFailure("The AI returned a malformed plan step.")

        kind_str = str(raw.get("kind", ""))
        try:
            kind = PlanStepKind(kind_str)
        except ValueError:
            raise ValidationFailure(
                f"The AI suggested an unsupported Git operation: '{kind_str}'."
            )

        paths: list[str] = raw.get("paths") or []

        for path in paths:
            if path in _WILDCARD_SENTINELS or path.startswith("*."):
                raise ValidationFailure(
                    f"The AI suggested a wildcard path '{path}'. Only explicit file paths are allowed."
                )

        if kind in _KINDS_REQUIRING_PATHS:
            if not paths:
                raise ValidationFailure(
                    f"The AI suggested a '{kind_str}' step with no file paths."
                )
            if known_changed:
                for path in paths:
                    if path not in known_changed:
                        raise ValidationFailure(
                            f"The AI suggested path '{path}' which is not in the repository's changed files."
                        )

        remote = raw.get("remote")
        if kind in _KINDS_REQUIRING_REMOTE and remote and known_remotes and remote not in known_remotes:
            raise ValidationFailure(f"The AI suggested unknown remote '{remote}'.")

        branch = raw.get("branch")
        if kind in _KINDS_REQUIRING_BRANCH and not branch:
            raise ValidationFailure(f"The AI suggested a '{kind_str}' step without a branch.")

        commit_message = raw.get("commit_message")
        if kind is PlanStepKind.COMMIT and not commit_message:
            raise ValidationFailure("The AI suggested a commit step without a commit message.")

        stash_ref = raw.get("stash_ref")
        if kind in _KINDS_REQUIRING_STASH_REF:
            if not stash_ref or not str(stash_ref).startswith("stash@{"):
                raise ValidationFailure(
                    f"The AI suggested a '{kind_str}' step without an explicit stash reference."
                )

        tag_name = raw.get("tag_name")
        if kind in _KINDS_REQUIRING_TAG and not tag_name:
            raise ValidationFailure(f"The AI suggested a '{kind_str}' step without a tag name.")

        if kind is PlanStepKind.CREATE_TAG and not commit_message:
            raise ValidationFailure("The AI suggested a create_tag step without a tag message.")

        result.append(
            ActionPlanStep(
                kind=kind,
                title=str(raw.get("title") or f"Git {kind_str}"),
                detail=str(raw.get("detail") or ""),
                paths=paths,
                commit_message=commit_message,
                remote=remote,
                branch=branch,
                stash_ref=stash_ref,
                tag_name=tag_name,
                set_upstream=bool(raw.get("set_upstream", False)),
                command_preview=raw.get("command_preview"),
            )
        )

    return result
