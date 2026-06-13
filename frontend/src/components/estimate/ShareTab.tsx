import ExportButtons from "./ExportButtons";
import PublicLinksManager from "./PublicLinksManager";

export default function ShareTab({ estimateId, canEdit }: { estimateId: number; canEdit: boolean }) {
  return (
    <div className="grid gap-6">
      <ExportButtons estimateId={estimateId} />
      <hr className="border-stone-200" />
      <PublicLinksManager estimateId={estimateId} canEdit={canEdit} />
    </div>
  );
}
