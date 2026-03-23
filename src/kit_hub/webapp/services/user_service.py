"""User service for user management.

Placeholder for future user persistence and management.
"""

from fastapi_tools.schemas.auth import GoogleUserInfo
from fastapi_tools.schemas.auth import UserResponse
from loguru import logger as lg


class UserService:
    """Service for user management.

    Currently a placeholder - users are stored only in session.
    Extend this for persistent user storage with a database.
    """

    def __init__(self) -> None:
        """Initialize user service.

        In a real implementation, this would accept a database session.
        """
        # In-memory user store (placeholder for database)
        self._users: dict[str, UserResponse] = {}

    def get_or_create_user(self, google_user_info: GoogleUserInfo) -> UserResponse:
        """Get existing user or create new one from Google info.

        Args:
            google_user_info: User info from Google OAuth.

        Returns:
            UserResponse for the user.
        """
        user_id = google_user_info.sub

        if user_id in self._users:
            lg.debug(f"Found existing user: {google_user_info.email}")
            # Update user info from Google (may have changed)
            self._users[user_id] = UserResponse(
                id=user_id,
                email=google_user_info.email,
                name=google_user_info.name,
                picture=google_user_info.picture,
            )
        else:
            lg.info(f"Creating new user: {google_user_info.email}")
            self._users[user_id] = UserResponse(
                id=user_id,
                email=google_user_info.email,
                name=google_user_info.name,
                picture=google_user_info.picture,
            )

        return self._users[user_id]

    def get_user_by_id(self, user_id: str) -> UserResponse | None:
        """Get user by ID.

        Args:
            user_id: User identifier.

        Returns:
            UserResponse if found, None otherwise.
        """
        return self._users.get(user_id)

    def get_user_by_email(self, email: str) -> UserResponse | None:
        """Get user by email.

        Args:
            email: User email address.

        Returns:
            UserResponse if found, None otherwise.
        """
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    def delete_user(self, user_id: str) -> bool:
        """Delete a user.

        Args:
            user_id: User identifier.

        Returns:
            True if deleted, False if not found.
        """
        if user_id in self._users:
            del self._users[user_id]
            lg.info(f"Deleted user {user_id}")
            return True
        return False
