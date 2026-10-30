"use client";
import katex from "katex";
import { useMemo } from "react";

export function Tex({ children, block = false }: { children: string; block?: boolean }) {
  const html = useMemo(
    () => katex.renderToString(children, { displayMode: block, throwOnError: false, strict: "ignore" }),
    [children, block],
  );
  return block ? (
    <div className="my-3 text-[15px]" dangerouslySetInnerHTML={{ __html: html }} />
  ) : (
    <span dangerouslySetInnerHTML={{ __html: html }} />
  );
}
