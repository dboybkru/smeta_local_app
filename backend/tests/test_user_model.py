from app.auth.models import User


def test_user_defaults(db_session):
    user = User(email="a@b.ru", password_hash="x")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    assert user.id is not None
    assert user.role == "estimator"
    assert user.status == "pending"
    assert user.yandex_id is None
    assert user.created_at is not None
