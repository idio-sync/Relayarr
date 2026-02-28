from bot.web.auth import hash_password, check_password


class TestPasswordHashing:
    def test_hash_and_check_valid(self):
        hashed = hash_password("secret")
        assert check_password("secret", hashed) is True

    def test_check_wrong_password(self):
        hashed = hash_password("secret")
        assert check_password("wrong", hashed) is False

    def test_check_empty_password(self):
        hashed = hash_password("secret")
        assert check_password("", hashed) is False

    def test_hash_produces_bytes(self):
        hashed = hash_password("test")
        assert isinstance(hashed, bytes)

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # different salts
        assert check_password("same", h1) is True
        assert check_password("same", h2) is True
