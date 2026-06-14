import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import {
  applyChangeset, chatAssistant, getAssistantHistory,
  type ChatMessage, type Operation,
} from "../../api/assistant";
import type { EstimateDetail } from "../../api/estimates";

function opLabel(o: Operation): string {
  switch (o.op) {
    case "add_section": return `➕ Раздел «${o.name}»`;
    case "add_catalog_line": return `➕ Позиция #${o.catalog_item_id} ×${o.qty} в «${o.section_name}»`;
    case "add_custom_line": return `➕ «${o.name}» ×${o.qty} ${o.unit ?? ""} в «${o.section_name}»`;
    case "set_qty": return `✏️ кол-во строки #${o.line_id} → ${o.qty}`;
    case "set_price": return `✏️ цена строки #${o.line_id}`;
    case "delete_line": return `🗑 удалить строку #${o.line_id}`;
    case "delete_section": return `🗑 удалить раздел #${o.section_id}`;
    case "set_section_markup": return `✏️ наценка раздела #${o.section_id} → ${o.markup_percent}%`;
    case "set_vat": return `✏️ НДС ${o.vat_enabled ? "вкл" : "выкл"}${o.vat_rate ? " " + o.vat_rate + "%" : ""}`;
    default: return o.op;
  }
}

export default function AssistantPanel({
  estimateId, onApplied, onClose,
}: {
  estimateId: number;
  onApplied: (d: EstimateDetail) => void;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<Operation[]>([]);
  const [busy, setBusy] = useState(false);
  const [notConfigured, setNotConfigured] = useState(false);
  const [error, setError] = useState("");

  // загрузить сохранённую историю диалога этой сметы при открытии
  useEffect(() => {
    getAssistantHistory(estimateId)
      .then(setMessages)
      .catch(() => undefined);
  }, [estimateId]);

  async function send() {
    const text = draft.trim();
    if (!text || busy) return;
    setMessages((m) => [...m, { role: "user", content: text }]);
    setDraft(""); setPending([]); setError(""); setNotConfigured(false);
    setBusy(true);
    try {
      const out = await chatAssistant(estimateId, text);
      setMessages((m) => [...m, { role: "assistant", content: out.reply }]);
      setPending(out.operations);
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) setNotConfigured(true);
      else setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    setError("");
    try {
      const detail = await applyChangeset(estimateId, pending);
      setPending([]);
      setMessages((m) => [...m, { role: "assistant", content: "✓ Изменения применены." }]);
      onApplied(detail);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка применения");
    }
  }

  return (
    <aside className="fixed inset-y-0 right-0 z-40 flex w-[420px] flex-col border-l border-stone-200 bg-white shadow-xl">
      <div className="flex items-center justify-between border-b border-stone-200 px-4 py-3">
        <h2 className="font-serif text-lg text-stone-900">✨ Ассистент</h2>
        <button onClick={onClose} aria-label="Закрыть" className="text-stone-500 hover:text-stone-900">✕</button>
      </div>

      <div className="flex-1 space-y-3 overflow-auto p-4 text-sm">
        {messages.length === 0 && (
          <p className="text-stone-400">Опишите, что добавить или изменить в смете — например «добавь видеонаблюдение склада».</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-stone-900" : "text-stone-600"}>
            <span className="mr-1 text-xs text-stone-400">{m.role === "user" ? "Вы:" : "AI:"}</span>{m.content}
          </div>
        ))}
        {busy && <p className="text-stone-400">Думаю…</p>}
        {notConfigured && (
          <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-amber-800">
            ⚠ AI не настроен — попросите администратора подключить провайдера в «AI».
          </div>
        )}
        {error && <p role="alert" className="text-red-600">{error}</p>}

        {pending.length > 0 && (
          <div className="rounded border border-stone-300 bg-stone-50 p-3">
            <p className="mb-2 font-medium text-stone-700">Предложенные изменения:</p>
            <ul className="mb-3 space-y-1">
              {pending.map((o, i) => <li key={i}>{opLabel(o)}</li>)}
            </ul>
            <div className="flex gap-2">
              <button onClick={() => void apply()} className="rounded border border-stone-700 px-3 py-1 text-stone-700">Применить всё</button>
              <button onClick={() => setPending([])} className="text-stone-500">Отклонить</button>
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-stone-200 p-3">
        <textarea
          aria-label="Сообщение ассистенту"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          rows={2}
          placeholder="Сообщение… (Enter — отправить, Shift+Enter — перенос)"
          className="mb-2 w-full rounded border border-stone-300 px-2 py-1"
        />
        <button onClick={() => void send()} disabled={busy}
          className="rounded border border-stone-700 px-4 py-1.5 text-stone-700 disabled:opacity-50">
          Отправить
        </button>
      </div>
    </aside>
  );
}
