import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import {
  addLine as apiAddLine,
  addSection as apiAddSection,
  deleteLine as apiDeleteLine,
  deleteSection as apiDeleteSection,
  getEstimate,
  patchEstimate as apiPatchEstimate,
  patchLine as apiPatchLine,
  patchSection as apiPatchSection,
  type EstimateDetail,
  type EstimatePatch,
  type LineCreate,
  type LinePatch,
} from "../api/estimates";

export function useEstimate(id: number) {
  const { user } = useAuth();
  const [estimate, setEstimate] = useState<EstimateDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      setEstimate(await getEstimate(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // Each mutation calls the API then reloads (backend recomputes totals).
  function wrap<A extends unknown[]>(fn: (...a: A) => Promise<unknown>) {
    return async (...a: A) => {
      setError("");
      try {
        await fn(...a);
        await reload();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Ошибка сохранения");
      }
    };
  }

  return {
    estimate,
    totals: estimate?.totals ?? null,
    loading,
    error,
    reload,
    // allowlist (а не «не viewer»): пока user грузится (undefined) — правок нет
    canEdit: user?.role === "estimator" || user?.role === "admin",
    patchEstimate: wrap((patch: EstimatePatch) => apiPatchEstimate(id, patch)),
    addSection: wrap((body: { name?: string; markup_percent?: string }) => apiAddSection(id, body)),
    patchSection: wrap((sid: number, patch: Parameters<typeof apiPatchSection>[1]) =>
      apiPatchSection(sid, patch),
    ),
    deleteSection: wrap((sid: number) => apiDeleteSection(sid)),
    addLine: wrap((sid: number, body: LineCreate) => apiAddLine(sid, body)),
    patchLine: wrap((lid: number, patch: LinePatch) => apiPatchLine(lid, patch)),
    deleteLine: wrap((lid: number) => apiDeleteLine(lid)),
  };
}
