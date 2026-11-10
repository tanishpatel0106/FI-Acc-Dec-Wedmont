import {
  IconActivity, IconArrowsExchange, IconBook2, IconChartDots3, IconFlask2, IconGitCompare, IconHistory, IconLayoutDashboard,
  IconMicroscope, IconScale, IconSquares, IconTable, IconWaveSine,
} from "@tabler/icons-react";

/** Icons referenced by name in lib/research/routes.ts. */
export const PAGE_ICONS = {
  IconActivity, IconArrowsExchange, IconBook2, IconChartDots3, IconFlask2, IconGitCompare, IconHistory, IconLayoutDashboard,
  IconMicroscope, IconScale, IconSquares, IconTable, IconWaveSine,
} as const;

export function pageIcon(name: string) {
  return PAGE_ICONS[name as keyof typeof PAGE_ICONS] ?? IconLayoutDashboard;
}
