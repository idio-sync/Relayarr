# tests/test_auth.py
from bot.core.auth import AuthManager


class TestHostmaskMatching:
    def test_exact_match(self):
        am = AuthManager(admins=["admin!admin@admin.host"], users=[], default_role="none")
        assert am.get_role("admin!admin@admin.host") == "admin"

    def test_wildcard_nick(self):
        am = AuthManager(admins=["*!*@admin.host"], users=[], default_role="none")
        assert am.get_role("anynick!anyuser@admin.host") == "admin"

    def test_wildcard_host_suffix(self):
        am = AuthManager(admins=[], users=["*!*@*.trusted.net"], default_role="none")
        assert am.get_role("bob!~bob@home.trusted.net") == "user"

    def test_no_match_returns_default(self):
        am = AuthManager(admins=["*!*@admin.host"], users=["*!*@*.trusted.net"], default_role="none")
        assert am.get_role("stranger!~x@unknown.host") == "none"

    def test_default_role_user(self):
        am = AuthManager(admins=[], users=[], default_role="user")
        assert am.get_role("anyone!~x@any.host") == "user"

    def test_admin_takes_priority_over_user(self):
        am = AuthManager(admins=["*!*@special.host"], users=["*!*@special.host"], default_role="none")
        assert am.get_role("nick!user@special.host") == "admin"


class TestRoleCheck:
    def test_admin_can_use_user_commands(self):
        am = AuthManager(admins=["*!*@admin.host"], users=[], default_role="none")
        assert am.check_permission("nick!u@admin.host", "user") is True

    def test_admin_can_use_admin_commands(self):
        am = AuthManager(admins=["*!*@admin.host"], users=[], default_role="none")
        assert am.check_permission("nick!u@admin.host", "admin") is True

    def test_user_cannot_use_admin_commands(self):
        am = AuthManager(admins=[], users=["*!*@user.host"], default_role="none")
        assert am.check_permission("nick!u@user.host", "admin") is False

    def test_user_can_use_user_commands(self):
        am = AuthManager(admins=[], users=["*!*@user.host"], default_role="none")
        assert am.check_permission("nick!u@user.host", "user") is True

    def test_none_role_denied_everything(self):
        am = AuthManager(admins=[], users=[], default_role="none")
        assert am.check_permission("nick!u@any.host", "user") is False
