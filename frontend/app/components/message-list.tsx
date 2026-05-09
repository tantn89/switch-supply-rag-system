"use client";
// Auto-scrolling message viewport.
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ChatMessage } from "@/lib/types";
import { useEffect, useRef } from "react";
import { MessageBubble } from "./message-bubble";

interface Props {
  messages: ChatMessage[];
}

export function MessageList({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  return (
    <ScrollArea className="flex-1 px-4 py-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          messages.map((m) => <MessageBubble key={m.id} message={m} />)
        )}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}

function EmptyState() {
  const samples = [
    "What is the contact email for ACME Supply Co?",
    "How many units of SKU-LED-100 are in stock?",
    "Compare the catalog price vs the PO price for SKU-LED-100",
    "Extract the invoice total and tell me which PO it matches",
  ];
  return (
    <div className="text-center py-16 space-y-4">
      <h2 className="text-2xl font-semibold tracking-tight">
        Procurement RAG Assistant
      </h2>
      <p className="text-sm text-muted-foreground max-w-md mx-auto">
        Ask anything about vendors, products, purchase orders, the vendor
        catalog, or the scanned invoice. Sources are cited inline.
      </p>
      <ul className="text-sm text-muted-foreground space-y-1">
        {samples.map((s) => (
          <li key={s} className="italic">
            “{s}”
          </li>
        ))}
      </ul>
    </div>
  );
}
