from pydantic import BaseModel, ConfigDict


class ProposalBlocks(BaseModel):
    """Маркетинговые блоки КП. Все опциональны (AI или ручной ввод)."""
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    subtitle: str = ""
    pain: str = ""
    solution: str = ""
    advantages: list[str] = []
    terms: str = ""
    cta: str = ""


class ProposalPatch(BaseModel):
    """Частичная ручная правка. None-поля не трогаются."""
    title: str | None = None
    subtitle: str | None = None
    pain: str | None = None
    solution: str | None = None
    advantages: list[str] | None = None
    terms: str | None = None
    cta: str | None = None
