import type { CraneModel } from "../types/layout";

const CRANE_NAME_BY_ID: Record<string, string> = {
  "5327272_5311976": "QTZ60-1",
  "5327272_5312858": "QTZ60-2",
  "5327272_5312036": "QTZ60-3",
};

const isUsableCraneName = (value?: string | null): value is string =>
  Boolean(value && !value.includes("?") && !value.includes("\uFFFD"));

export const resolveCraneName = (
  craneId?: string | null,
  craneName?: string | null,
  cranes: CraneModel[] = [],
): string | null => {
  const storeName = craneId
    ? cranes.find((crane) => crane.id === craneId)?.name ?? null
    : null;

  for (const candidate of [craneName, storeName, craneId ? CRANE_NAME_BY_ID[craneId] : null]) {
    if (isUsableCraneName(candidate)) {
      return candidate;
    }
  }

  return craneId ? CRANE_NAME_BY_ID[craneId] ?? craneName ?? storeName ?? null : craneName ?? storeName ?? null;
};
