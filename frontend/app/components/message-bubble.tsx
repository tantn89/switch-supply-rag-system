"use client";
// Single chat message: user prompt or assistant answer with parsed citations.
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { parseCitations } from "@/lib/citation-parser";
import type { ChatMessage, Confidence } from "@/lib/types";
import { cn } from "@/lib/utils";
import { SourceCitationBadge } from "./source-citation-badge";
import { StatusIndicator } from "./status-indicator";

const CONFIDENCE_COPY: Record<Confidence, { label: string; tone: string }> = {
  high: { label: "High confidence", tone: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900 dark:text-emerald-100" },
  medium: { label: "Medium confidence", tone: "bg-amber-100 text-amber-900 dark:bg-amber-900 dark:text-amber-100" },
  low: { label: "Low confidence", tone: "bg-orange-100 text-orange-900 dark:bg-orange-900 dark:text-orange-100" },
  none: { label: "No data found", tone: "bg-muted text-muted-foreground" },
};

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <Card className="max-w-[80%] bg-primary text-primary-foreground p-3 rounded-2xl rounded-br-sm shadow-sm">
          <p className="text-sm whitespace-pre-wrap break-words">
            {message.content}
          </p>
        </Card>
      </div>
    );
  }

  const segments = parseCitations(message.content, message.citations);
  const confidence = message.confidence;

  return (
    <div className="flex justify-start">
      <Card className="max-w-[88%] bg-card p-3 rounded-2xl rounded-bl-sm shadow-sm border">
        {message.status && message.status !== "done" && message.status !== "error" && (
          <StatusIndicator status={message.status} route={message.route} />
        )}

        <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
          {segments.map((seg, i) =>
            seg.kind === "text" ? (
              <span key={i}>{seg.text}</span>
            ) : (
              <SourceCitationBadge
                key={i}
                sourceId={seg.sourceId}
                citation={seg.citation}
              />
            ),
          )}
        </div>

        {message.error && (
          <p className="mt-2 text-xs text-destructive">{message.error}</p>
        )}

        {(confidence || (message.citations && message.citations.length > 0)) && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {confidence && (
              <Badge
                variant="secondary"
                className={cn("text-[10px] font-medium", CONFIDENCE_COPY[confidence].tone)}
              >
                {CONFIDENCE_COPY[confidence].label}
              </Badge>
            )}
            {message.citations && message.citations.length > 0 && (
              <span className="text-[11px] text-muted-foreground">
                {message.citations.length} source
                {message.citations.length === 1 ? "" : "s"}
              </span>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
