from rekuest_next.api.schema import (
    DependencyInput,
    LogicalCondition,
    EffectInput,
    EffectKind,
)
from typing import Any


def hiddenwhile(key: str, condition: LogicalCondition, value: Any) -> EffectInput:
    return EffectInput(
        dependencies=[DependencyInput(key=key, condition=condition, value=value)],
        kind=EffectKind.HIDDEN,
    )


def hiddenif(key: str) -> EffectInput:
    return EffectInput(
        dependencies=[
            DependencyInput(key=key, condition=LogicalCondition.IS, value=True)
        ],
        kind=EffectKind.HIDDEN,
    )


def showif(key: str) -> EffectInput:
    return EffectInput(
        dependencies=[
            DependencyInput(key=key, condition=LogicalCondition.IS_NOT, value=True)
        ],
        kind=EffectKind.HIDDEN,
    )


def neverdothis(condition: LogicalCondition, value: Any) -> EffectInput:
    """No one should ever do this

    Why are you even reading this?

    Args:
        condition (LogicalCondition): Tell me why you are reading this
        value (Any): This is not a joke

    Returns:
        EffectInput: A stupid effect
    """
    return EffectInput(
        dependencies=[DependencyInput(condition=condition, value=value)],
        kind=EffectKind.CRAZY,
    )
