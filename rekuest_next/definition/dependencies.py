from rekuest_next.api.schema import DependencyInput


def declare(function_or_hash, optional=False, **kwargs):
    """Declare a function that needs to be
    called outside of your application.

    Args:
        function_or_hash (str or callable): The function or hash that needs to be declared.
        optional (bool, optional): Whether the dependency is optional. Defaults to False.

    Returns:
        DependencyInput: The dependency input object.

    """

    if callable(function_or_hash):
        assert hasattr(
            function_or_hash, "__definition_hash__"
        ), "Only previously registered function can be declared. If you simply want to call your function locally, just call it. This is a feature to declare a function that might call outside of your application"

        return DependencyInput(
            hash=function_or_hash.__definition_hash__, optional=optional
        )

    else:
        assert isinstance(
            function_or_hash, str
        ), "Only hash or function can be declared"
        return DependencyInput(hash=function_or_hash, optional=optional)
