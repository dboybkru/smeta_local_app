import { useState } from "react";

type Tab = "smeta" | "kp" | "share";
const LABELS: Record<Tab, string> = { smeta: "Смета", kp: "КП", share: "Поделиться" };

export default function EstimateTabs({
  smeta, kp, share,
}: {
  smeta: React.ReactNode;
  kp: React.ReactNode;
  share: React.ReactNode;
}) {
  const [tab, setTab] = useState<Tab>("smeta");
  const content: Record<Tab, React.ReactNode> = { smeta, kp, share };
  return (
    <div>
      <div role="tablist" className="mb-4 flex gap-1 border-b border-stone-200">
        {(Object.keys(LABELS) as Tab[]).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={
              "px-4 py-2 text-sm -mb-px border-b-2 " +
              (tab === t ? "border-stone-800 text-stone-900" : "border-transparent text-stone-500 hover:text-stone-800")
            }
          >
            {LABELS[t]}
          </button>
        ))}
      </div>
      <div>{content[tab]}</div>
    </div>
  );
}
