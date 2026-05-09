"use client";
// Auto-grow textarea + send button + file upload.
import { Button } from "@/components/ui/button";
import { useEffect, useRef } from "react";
import { FileUpload } from "./file-upload";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled?: boolean;
}

export function ChatInput({ value, onChange, onSend, disabled }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  // Auto-grow textarea height up to ~6 lines.
  useEffect(() => {
    const ta = ref.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [value]);

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) onSend();
    }
  };

  return (
    <div className="border-t bg-background">
      <div className="mx-auto max-w-3xl flex items-end gap-2 p-3">
        <FileUpload />
        <textarea
          ref={ref}
          rows={1}
          placeholder="Ask about vendors, stock, catalog prices, invoices…"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKey}
          disabled={disabled}
          className="flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50 leading-relaxed max-h-40"
        />
        <Button
          type="button"
          onClick={onSend}
          disabled={disabled || !value.trim()}
          aria-label="Send message"
        >
          Send
        </Button>
      </div>
    </div>
  );
}
