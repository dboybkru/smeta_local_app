from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    autoescape=select_autoescape(["html"]),
)


def render_html(context: dict, *, watermark: str = "") -> str:
    template = _env.get_template("proposal.html")
    return template.render(watermark=watermark, **context)


def html_to_pdf(html: str) -> bytes:
    """Рендер HTML → PDF через weasyprint. Импорт ленивый (тяжёлые sys-libs)."""
    from weasyprint import HTML

    return HTML(string=html).write_pdf()
