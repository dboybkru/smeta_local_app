import { useEffect, useState } from "react";
import { createLink, listLinks, revokeLink, type PublicLink } from "../../api/publicLinks";

const LEVELS = [
  { value: "full", label: "Полное КП" },
  { value: "cover", label: "Титул + смета" },
  { value: "estimate", label: "Только смета" },
];
const EXPIRY = [
  { value: "", label: "Без срока" },
  { value: "7", label: "7 дней" },
  { value: "30", label: "30 дней" },
];

function expiryToIso(days: string): string | null {
  if (!days) return null;
  const d = new Date();
  d.setDate(d.getDate() + Number(days));
  return d.toISOString();
}

export default function PublicLinksManager({ estimateId, canEdit }: { estimateId: number; canEdit: boolean }) {
  const [links, setLinks] = useState<PublicLink[]>([]);
  const [level, setLevel] = useState("full");
  const [expiry, setExpiry] = useState("");
  const [wm, setWm] = useState(false);
  const [wmText, setWmText] = useState("ОБРАЗЕЦ");
  const [error, setError] = useState("");

  useEffect(() => {
    listLinks(estimateId).then(setLinks).catch(() => setLinks([]));
  }, [estimateId]);

  async function create() {
    setError("");
    try {
      const link = await createLink(estimateId, {
        level, expires_at: expiryToIso(expiry),
        watermark_enabled: wm, watermark_text: wm ? wmText : "",
      });
      setLinks((ls) => {
        const exists = ls.some((x) => x.id === link.id);
        return exists ? ls.map((x) => (x.id === link.id ? link : x)) : [link, ...ls];
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка создания");
    }
  }

  async function revoke(id: number) {
    setError("");
    try {
      await revokeLink(id);
      setLinks((ls) => ls.map((l) => (l.id === id ? { ...l, revoked: true } : l)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка отзыва");
    }
  }

  const publicUrl = (token: string) => `${window.location.origin}/p/${token}`;

  return (
    <div className="grid gap-3 text-sm">
      <h3 className="font-serif text-stone-800">Публичные ссылки</h3>
      {error && <p role="alert" className="text-red-600">{error}</p>}
      {canEdit && (
        <div className="flex flex-wrap items-center gap-2">
          <select aria-label="Уровень ссылки" value={level} onChange={(e) => setLevel(e.target.value)}
            className="rounded border border-stone-300 px-2 py-1">
            {LEVELS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>
          <select aria-label="Срок" value={expiry} onChange={(e) => setExpiry(e.target.value)}
            className="rounded border border-stone-300 px-2 py-1">
            {EXPIRY.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
          </select>
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={wm} onChange={(e) => setWm(e.target.checked)} /> водяной знак
          </label>
          {wm && (
            <input aria-label="Текст водяного знака" value={wmText} onChange={(e) => setWmText(e.target.value)}
              className="rounded border border-stone-300 px-2 py-1" />
          )}
          <button onClick={create} className="rounded border border-stone-700 px-3 py-1 text-stone-700">Создать ссылку</button>
        </div>
      )}
      <ul className="grid gap-1">
        {links.map((l) => (
          <li key={l.id} className="flex flex-wrap items-center gap-2">
            <span className={l.revoked ? "text-stone-400 line-through" : "text-stone-700"}>{publicUrl(l.token)}</span>
            <span className="text-stone-400">· {l.level}{l.expires_at ? ` · до ${new Date(l.expires_at).toLocaleDateString()}` : ""}</span>
            {!l.revoked && (
              <button onClick={() => navigator.clipboard?.writeText(publicUrl(l.token)).catch(() => undefined)} className="text-stone-600 underline">копировать</button>
            )}
            {canEdit && !l.revoked && (
              <button onClick={() => revoke(l.id)} className="text-red-700">Отозвать</button>
            )}
            {l.revoked && <span className="text-stone-400">отозвана</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
