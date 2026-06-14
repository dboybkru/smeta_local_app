"""Гибкий поиск: учёт раскладки клавиатуры (RU↔EN) и многословность.

Покрывает: ввод в неверной раскладке (rfvthf→камера), частичные слова,
произвольный порядок слов. Полная опечатко-устойчивость (trigram) — позже."""

# Позиционное соответствие раскладок ЙЦУКЕН ↔ QWERTY (нижний регистр).
_EN = "qwertyuiop[]asdfghjkl;'zxcvbnm,.`"
_RU = "йцукенгшщзхъфывапролджэячсмитьбюё"
_EN2RU = {e: r for e, r in zip(_EN, _RU)}
_RU2EN = {r: e for e, r in zip(_EN, _RU)}


def _swap(s: str, mapping: dict[str, str]) -> str:
    return "".join(mapping.get(c, c) for c in s)


def variants(token: str) -> list[str]:
    """Сам токен + его прочтения в другой раскладке (дедуп, без пустых)."""
    t = token.lower()
    out = {t, _swap(t, _EN2RU), _swap(t, _RU2EN)}
    return [v for v in out if v]


def tokens(q: str) -> list[str]:
    return [t for t in q.lower().split() if t]
