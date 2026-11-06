"""Input validation and sanitization utilities."""
import re
from fastapi import HTTPException, Path, status

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,50}$")


def validate_username_str(username: str) -> str:
    """Validate a username string against LeetCode format constraints.

    Must be 1 to 50 characters, containing only letters, numbers,
    underscores, or hyphens.
    """
    cleaned = username.strip()
    if not USERNAME_REGEX.match(cleaned):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid username '{username}'. Usernames must be 1-50 characters "
                "long and contain only alphanumeric characters, underscores, or hyphens."
            ),
        )
    return cleaned


async def valid_username(
    username: str = Path(..., description="LeetCode username (1-50 alphanumeric characters)")
) -> str:
    """FastAPI path dependency that validates and sanitizes a username parameter."""
    return validate_username_str(username)

