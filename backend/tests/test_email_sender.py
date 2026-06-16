import pytest

from app.email import sender
from app.settings import service as ss


def test_send_email_not_configured_raises(db_session):
    with pytest.raises(sender.EmailNotConfigured):
        sender.send_email(db_session, "to@x.ru", "S", "<b>h</b>", "h")


def test_send_email_uses_transport(db_session):
    ss.set_secret(db_session, sender.SMTP_HOST, "smtp.test")
    ss.set_secret(db_session, sender.SMTP_PORT, "587")
    ss.set_secret(db_session, sender.SMTP_USER, "u@x.ru")
    ss.set_secret(db_session, sender.SMTP_PASSWORD, "pw")
    ss.set_secret(db_session, sender.SMTP_FROM, "from@x.ru")
    ss.set_secret(db_session, sender.SMTP_TLS, "true")
    sent = {}

    class FakeSMTP:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): sent["tls"] = True
        def login(self, u, p): sent["login"] = (u, p)
        def sendmail(self, frm, to, msg): sent["mail"] = (frm, to, msg)

    sender.send_email(db_session, "to@x.ru", "Subj", "<b>h</b>", "h", _transport=FakeSMTP())
    assert sent["login"] == ("u@x.ru", "pw")
    assert sent["mail"][0] == "from@x.ru" and sent["mail"][1] == ["to@x.ru"]
    assert "Subj" in sent["mail"][2]
