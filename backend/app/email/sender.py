import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from app.settings import service as settings_service

SMTP_HOST = "smtp_host"
SMTP_PORT = "smtp_port"
SMTP_USER = "smtp_user"
SMTP_PASSWORD = "smtp_password"
SMTP_FROM = "smtp_from"
SMTP_TLS = "smtp_tls"


class EmailNotConfigured(Exception):
    pass


class EmailError(Exception):
    pass


def _config(db: Session) -> dict:
    host = settings_service.get_secret(db, SMTP_HOST)
    if not host:
        raise EmailNotConfigured()
    user = settings_service.get_secret(db, SMTP_USER)
    return {
        "host": host,
        "port": int(settings_service.get_secret(db, SMTP_PORT) or "587"),
        "user": user,
        "password": settings_service.get_secret(db, SMTP_PASSWORD),
        "from": settings_service.get_secret(db, SMTP_FROM) or user,
        "tls": (settings_service.get_secret(db, SMTP_TLS) or "true").lower() != "false",
    }


def send_email(db: Session, to: str, subject: str, html: str, text: str, _transport=None) -> None:
    cfg = _config(db)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = to
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        smtp = _transport or smtplib.SMTP(cfg["host"], cfg["port"], timeout=10)
        with smtp:
            if cfg["tls"]:
                smtp.starttls()
            if cfg["user"]:
                smtp.login(cfg["user"], cfg["password"])
            smtp.sendmail(cfg["from"], [to], msg.as_string())
    except (EmailNotConfigured, EmailError):
        raise
    except Exception as exc:  # noqa: BLE001 — любая ошибка SMTP → EmailError
        raise EmailError(str(exc)) from exc


def send_invite_email(db: Session, to: str, org_name: str, link: str, _transport=None) -> None:
    subject = "Приглашение в SmetaApp"
    text = (
        f"Вас пригласили в организацию «{org_name}» в SmetaApp.\n"
        f"Перейдите по ссылке (действует 7 дней), чтобы задать пароль и войти:\n{link}\n"
    )
    html = (
        f"<p>Вас пригласили в организацию «{org_name}» в SmetaApp.</p>"
        f"<p>Перейдите по ссылке (действует 7 дней), чтобы задать пароль и войти:</p>"
        f'<p><a href="{link}">{link}</a></p>'
    )
    send_email(db, to, subject, html, text, _transport=_transport)
