"""Mirror of app/api/v1/endpoints: same paths, parameters and schemas, mock services behind.

tests/test_mock_parity.py fails if the mock and real OpenAPI drift apart.
"""

from collections.abc import Callable


def mirrors[F: Callable](real: Callable) -> Callable[[F], F]:
    """Give a mock endpoint the real one's docs (put it *below* the @router decorator).

    The name must match too: FastAPI derives the operationId / schema names from it.
    """

    def decorate(mock: F) -> F:
        if mock.__name__ != real.__name__:
            raise NameError(f"mock endpoint {mock.__name__} must be named {real.__name__}")
        mock.__doc__ = real.__doc__
        return mock

    return decorate
