"use client";
// Top-level chat container: holds messages state, drives SSE stream, dispatches to UI.
import { Toaster } from "@/components/ui/sonner";
import { streamChat } from "@/lib/api-client";
import type { ChatMessage, Citation, Confidence, RouteInfo } from "@/lib/types";
import { useCallback, useState } from "react";
import { ChatInput } from "./chat-input";
import { MessageList } from "./message-list";

function uid() {
  return Math.random().toString(36).slice(2, 11);
}

export function ChatInterface() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const updateAssistant = useCallback(
    (id: string, patch: Partial<ChatMessage>) => {
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, ...patch } : m)),
      );
    },
    [],
  );

  const append = useCallback((msg: ChatMessage) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;

    const userMsg: ChatMessage = { id: uid(), role: "user", content: text };
    const assistantId = uid();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      status: "routing",
      citations: [],
    };
    append(userMsg);
    append(assistantMsg);
    setInput("");
    setBusy(true);

    try {
      let buffered = "";
      let collectedCitations: Citation[] = [];
      let route: RouteInfo | undefined;

      for await (const ev of streamChat(text)) {
        if (ev.event === "route") {
          route = ev.data as RouteInfo;
          updateAssistant(assistantId, {
            status: "retrieving",
            route,
          });
        } else if (ev.event === "citations") {
          collectedCitations = (ev.data as { citations: Citation[] }).citations;
          updateAssistant(assistantId, {
            citations: collectedCitations,
            status: "streaming",
          });
        } else if (ev.event === "token") {
          buffered += (ev.data as { text: string }).text;
          updateAssistant(assistantId, { content: buffered });
        } else if (ev.event === "done") {
          updateAssistant(assistantId, {
            status: "done",
            confidence: (ev.data as { confidence: Confidence }).confidence,
          });
        } else if (ev.event === "error") {
          updateAssistant(assistantId, {
            status: "error",
            error: (ev.data as { message: string }).message,
          });
        }
      }
    } catch (err) {
      updateAssistant(assistantId, {
        status: "error",
        error: err instanceof Error ? err.message : "Unknown error",
      });
    } finally {
      setBusy(false);
    }
  }, [input, busy, append, updateAssistant]);

  return (
    <div className="flex h-dvh flex-col bg-background">
      <header className="border-b px-4 py-3">
        <div className="mx-auto max-w-3xl flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold tracking-tight">
              Switch Supply RAG
            </h1>
            <p className="text-xs text-muted-foreground">
              Procurement assistant · multi-source retrieval with citations
            </p>
          </div>
        </div>
      </header>

      <MessageList messages={messages} />

      <ChatInput
        value={input}
        onChange={setInput}
        onSend={send}
        disabled={busy}
      />

      <Toaster position="bottom-right" />
    </div>
  );
}
