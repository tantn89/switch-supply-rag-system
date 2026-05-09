"use client";
// File upload trigger that POSTs to /upload and surfaces feedback via toast.
import { Button } from "@/components/ui/button";
import { uploadFile } from "@/lib/api-client";
import { useRef, useState } from "react";
import { toast } from "sonner";

const ACCEPT = ".pdf,.json,.jpg,.jpeg,.png";

export function FileUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  const onSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting same file
    if (!file) return;
    setBusy(true);
    try {
      const result = await uploadFile(file);
      toast.success(
        `Indexed ${result.chunks_added} chunks from ${result.filename}`,
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={onSelect}
      />
      <Button
        type="button"
        variant="outline"
        size="icon"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
        aria-label="Upload file (PDF, JSON, image)"
        title="Upload PDF / JSON / image"
      >
        {busy ? "…" : "📎"}
      </Button>
    </>
  );
}
