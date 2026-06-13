import { api } from "./client";

export type ProposalBlocks = {
  title: string;
  subtitle: string;
  pain: string;
  solution: string;
  advantages: string[];
  terms: string;
  cta: string;
};

export type ProposalPatch = Partial<ProposalBlocks>;

const j = (b: unknown) => JSON.stringify(b);

export const generateProposal = (estimateId: number) =>
  api<ProposalBlocks>(`/estimates/${estimateId}/proposal/generate`, { method: "POST" });

export const patchProposal = (estimateId: number, patch: ProposalPatch) =>
  api<ProposalBlocks>(`/estimates/${estimateId}/proposal`, { method: "PATCH", body: j(patch) });
