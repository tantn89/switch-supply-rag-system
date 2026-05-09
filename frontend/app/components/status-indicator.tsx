"use client";
// Spinner + phase label that progresses through routing → retrieving → streaming.
import { Skeleton } from "@/components/ui/skeleton";
import type { MessageStatus, RouteInfo } from "@/lib/types";

const STATUS_LABEL: Record<Exclude<MessageStatus, "idle" | "done" | "error">, string> = {
  routing: "Routing query…",
  retrieving: "Retrieving relevant chunks…",
  streaming: "Generating answer…",
};

interface Props {
  status: MessageStatus;
  route?: RouteInfo;
}

export function StatusIndicator({ status, route }: Props) {
  if (status === "idle" || status === "done" || status === "error") return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="inline-block size-2 rounded-full bg-blue-500 animate-pulse" />
        {STATUS_LABEL[status]}
      </div>
      {route && (
        <div className="text-[11px] text-muted-foreground/80 space-y-1">
          <div>
            <span className="font-medium">Sources:</span>{" "}
            {route.sources.length > 0 ? route.sources.join(", ") : "(none)"}
          </div>
          {route.sql_query && (
            <pre className="text-[10px] font-mono bg-muted/50 p-1.5 rounded whitespace-pre-wrap break-all">
              {route.sql_query}
            </pre>
          )}
          <div className="italic">{route.reasoning}</div>
        </div>
      )}
      {status === "streaming" && <Skeleton className="h-3 w-3/4" />}
    </div>
  );
}
