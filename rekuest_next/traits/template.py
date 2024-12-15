from typing import Callable, Generic, TypeVar, ParamSpec
import typing as t

P = ParamSpec("P")
R = TypeVar("R")


class Remote(Generic[P, R]):

    def __init__(self, func: Callable[P, R]):
        self._UNDERLYING_LOGIC = func

    def __call__(self, *args: P.args, **kwds: P.kwargs) -> R:
        # Here you can inspect args and kwargs
        print(f"Args: {args}")
        print(f"Kwargs: {kwds}")
        return self._UNDERLYING_LOGIC(*args, **kwds)


def register(func: Callable[P, R]) -> TemplateCallable[P, R]:
    def wrapper(*args: P.args, **kwds: P.kwargs) -> R:
        print(f"Args: {args}")
        print(f"Kwargs: {kwds}")
        return func(*args, **kwds)

    return wrapper


def test(func: Callable[P, R]):
    def wrapper(*args: P.args, **kwds: P.kwargs) -> R:
        print(f"Args: {args}")
        print(f"Kwargs: {kwds}")
        return func(*args, **kwds)


@register
def the_function(a: int = 5):
    print(f"the_function: {a}")


class Image:
    pass


def default():
    return from_x_array()


TestImage = t.Annotated[Image, default]


@test(the_function)
def other_function(test_image: TestImage):

    test_image

    assert the_function(a=5) == 5, "Should be 5"
