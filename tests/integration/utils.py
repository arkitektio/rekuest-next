"""Integration test utilities."""

import requests
from requests.exceptions import ConnectionError
import time


class RetryExceededError(Exception):
    """Custom exception for retry limit exceeded."""

    pass


def wait_for_http_response(
    url: str, status_code: int = 200, retry: int = 0, max_retries: int = 10
) -> requests.Response:
    """Wait for an HTTP response with a specific status code."""
    if retry > max_retries:
        raise RetryExceededError("Max retries exceeded")
    time.sleep(retry * retry * 0.5)
    try:
        response = requests.get(url)
        assert response.status_code == status_code, "Did not get expected response code"
        return response
    except (ConnectionResetError, AssertionError, ConnectionError):
        return wait_for_http_response(url, status_code, retry + 1, max_retries=max_retries)
