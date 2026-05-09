"use client";
// Inline clickable badge for a [source_id] citation. Click → Popover shows
// the chunk preview so the user can verify the answer's source.
import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { Citation, SourceType } from "@/lib/types";
import { cn } from "@/lib/utils";

const SOURCE_STYLES: Record<SourceType, string> = {
  sql: "bg-blue-100 text-blue-900 dark:bg-blue-900 dark:text-blue-100",
  pdf: "bg-rose-100 text-rose-900 dark:bg-rose-900 dark:text-rose-100",
  json: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900 dark:text-emerald-100",
  image: "bg-purple-100 text-purple-900 dark:bg-purple-900 dark:text-purple-100",
};

const SOURCE_LABELS: Record<SourceType, string> = {
  sql: "DB",
  pdf: "PDF",
  json: "JSON",
  image: "OCR",
};

interface Props {
  sourceId: string;
  citation?: Citation;
}

export function SourceCitationBadge({ sourceId, citation }: Props) {
  const sourceType = (citation?.source_type ??
    (sourceId.split(":")[0] as SourceType)) as SourceType;
  const label = SOURCE_LABELS[sourceType] ?? sourceType.toUpperCase();
  const style = SOURCE_STYLES[sourceType] ?? "bg-muted text-muted-foreground";

  return (
    <Popover>
      <PopoverTrigger
        aria-label={`Citation ${sourceId}`}
        className={cn(
          "mx-0.5 cursor-pointer rounded-md px-1.5 py-0 text-[10px] font-mono font-medium align-baseline leading-tight inline-flex items-center hover:opacity-80 transition-opacity",
          style,
        )}
      >
        {label}
      </PopoverTrigger>
      <PopoverContent className="w-80 text-xs" side="top" align="start">
        <div className="font-mono text-muted-foreground mb-1.5 break-all">
          {sourceId}
        </div>
        {citation ? (
          <p className="whitespace-pre-wrap break-words leading-snug">
            {citation.preview}
          </p>
        ) : (
          <p className="italic text-muted-foreground">
            (preview unavailable)
          </p>
        )}
      </PopoverContent>
    </Popover>
  );
}
