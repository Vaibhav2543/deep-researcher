// frontend/src/components/ResultCard.tsx
import React from "react";
import type { Source } from "../types";

type Props = {
  source: Source;
};

export default function ResultCard({ source }: Props) {
  return (
    <div className="p-3 border border-slate-800 rounded-lg mb-3 bg-gradient-to-b from-[#071225] to-[#071428]">
      <div className="text-xs text-slate-400 mb-1">
        {source.source} • distance: {source.dist.toFixed(3)}
      </div>
      <div className="text-sm text-slate-200 whitespace-pre-wrap">
        {source.text.slice(0, 600)}
        {source.text.length > 600 ? "..." : ""}
      </div>
    </div>
  );
}
