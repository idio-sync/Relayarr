# bot/core/auth.py
import fnmatch

ROLE_HIERARCHY = {"admin": 2, "user": 1, "none": 0}


class AuthManager:
    def __init__(self, admins: list[str], users: list[str], default_role: str = "none"):
        self._admins = admins
        self._users = users
        self._default_role = default_role

    def get_role(self, hostmask: str) -> str:
        for pattern in self._admins:
            if fnmatch.fnmatch(hostmask, pattern):
                return "admin"
        for pattern in self._users:
            if fnmatch.fnmatch(hostmask, pattern):
                return "user"
        return self._default_role

    def check_permission(self, hostmask: str, required_role: str) -> bool:
        actual = self.get_role(hostmask)
        return ROLE_HIERARCHY.get(actual, 0) >= ROLE_HIERARCHY.get(required_role, 0)
