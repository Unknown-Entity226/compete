"""Custom application exceptions."""

class CompeteException(Exception):
    """Base exception for Compete application."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class UserNotFoundError(CompeteException):
    """Raised when a LeetCode user profile is not found."""
    def __init__(self, username: str):
        super().__init__(f"LeetCode user '{username}' was not found.", status_code=404)
        self.username = username


class UpstreamRateLimitError(CompeteException):
    """Raised when LeetCode responds with 429 Too Many Requests."""
    def __init__(self, message: str = "LeetCode upstream rate limit exceeded. Please try again shortly."):
        super().__init__(message, status_code=429)


class UpstreamServiceError(CompeteException):
    """Raised when LeetCode GraphQL service returns 5xx or unparseable errors."""
    def __init__(self, message: str = "LeetCode upstream service error."):
        super().__init__(message, status_code=502)

