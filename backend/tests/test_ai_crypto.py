from app.ai import crypto


def test_encrypt_decrypt_round_trip():
    token = crypto.encrypt("sk-secret-123")
    assert token != "sk-secret-123"  # хранится зашифрованным
    assert crypto.decrypt(token) == "sk-secret-123"


def test_encrypt_is_nondeterministic_but_decryptable():
    a = crypto.encrypt("same")
    b = crypto.encrypt("same")
    assert a != b  # Fernet добавляет IV/timestamp
    assert crypto.decrypt(a) == crypto.decrypt(b) == "same"
