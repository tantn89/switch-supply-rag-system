// Shared types between frontend components and the RAG backend.

export type SourceType = "sql" | "pdf" | "json" | "image";

export interface Citation {
  source_id: string;
  source_type: SourceType;
  preview: string;
  score?: number | null;
}

export type Confidence = "high" | "medium" | "low" | "none";

export interface RouteInfo {
  sources: string[];
  sql_query?: string | null;
  reasoning: string;
}

export type MessageStatus =
  | "idle"
  | "routing"
  | "retrieving"
  | "streaming"
  | "done"
  | "error";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  route?: RouteInfo;
  status?: MessageStatus;
  confidence?: Confidence;
  error?: string;
}

export type SSEEvent =
  | { event: "route"; data: RouteInfo }
  | { event: "citations"; data: { citations: Citation[] } }
  | { event: "token"; data: { text: string } }
  | { event: "done"; data: { confidence: Confidence } }
  | { event: "error"; data: { message: string } };
