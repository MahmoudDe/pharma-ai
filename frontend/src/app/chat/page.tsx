"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatHistorySidebar } from "@/components/chat/ChatHistorySidebar";
import { ChatLayout } from "@/components/chat/ChatLayout";
import { ChatThread } from "@/components/chat/ChatThread";
import { ConstraintsPanel } from "@/components/chat/ConstraintsPanel";
import { EvidencePanel } from "@/components/chat/EvidencePanel";
import { StructuredFormulaPanel } from "@/components/chat/StructuredFormulaPanel";
import { SuggestedActionsPanel } from "@/components/chat/SuggestedActionsPanel";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { fetchBackendHealth, fetchBackendReadiness } from "@/lib/backend";
import {
  createChatThread,
  deleteChatThread,
  fetchChatThread,
  fetchChatThreads,
  sendChatTurn,
  updateChatThreadTitle,
} from "@/lib/chat";
import { t } from "@/lib/i18n";
import type {
  ChatMessage,
  ChatThreadMessage,
  ChatThreadSummary,
  ChatTurnRequest,
  CitedEvidence,
  StructuredBrief,
  StructuredFormulationView,
  SuggestedNextAction,
} from "@/types/chat";

type BackendStatus = "checking" | "ok" | "down";
type CorpusStatus = "unknown" | "ready" | "degraded";

function createMessage(
  role: "user" | "assistant",
  content: string,
  extras?: Partial<ChatMessage>,
): ChatMessage {
  return {
    id: extras?.id ?? `${role}-${crypto.randomUUID()}`,
    role,
    content,
    createdAt: extras?.createdAt ?? new Date().toISOString(),
    citedEvidence: extras?.citedEvidence,
    suggestedActions: extras?.suggestedActions,
  };
}

function mapStoredMessage(message: ChatThreadMessage): ChatMessage {
  const structuredList =
    message.structured_formulations && message.structured_formulations.length > 0
      ? message.structured_formulations
      : message.structured_formulation
        ? [message.structured_formulation]
        : [];
  return createMessage(message.role, message.content, {
    id: message.id,
    createdAt: message.created_at,
    citedEvidence: message.cited_evidence,
    suggestedActions: message.suggested_next_actions,
    structuredFormulation: structuredList[0] ?? null,
    structuredFormulations: structuredList,
  });
}

function latestAssistantPanels(messages: ChatMessage[]): {
  evidence: CitedEvidence[];
  actions: SuggestedNextAction[];
  structured: StructuredFormulationView | null;
  structuredList: StructuredFormulationView[];
} {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.role === "assistant") {
      const structuredList =
        message.structuredFormulations && message.structuredFormulations.length > 0
          ? message.structuredFormulations
          : message.structuredFormulation
            ? [message.structuredFormulation]
            : [];
      return {
        evidence: message.citedEvidence ?? [],
        actions: message.suggestedActions ?? [],
        structured: structuredList[0] ?? null,
        structuredList,
      };
    }
  }
  return { evidence: [], actions: [], structured: null, structuredList: [] };
}

const STATUS_PILL: Record<BackendStatus, { label: string; dot: string; text: string }> = {
  checking: {
    label: "Checking backend…",
    dot: "bg-warning",
    text: "text-warning",
  },
  ok: {
    label: "Backend online",
    dot: "bg-success",
    text: "text-success",
  },
  down: {
    label: "Backend unreachable",
    dot: "bg-error",
    text: "text-error",
  },
};

export default function ChatPage() {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [threads, setThreads] = useState<ChatThreadSummary[]>([]);
  const [isLoadingThreads, setIsLoadingThreads] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [messageInput, setMessageInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const [latestEvidence, setLatestEvidence] = useState<CitedEvidence[]>([]);
  const [latestStructured, setLatestStructured] = useState<StructuredFormulationView | null>(null);
  const [latestStructuredList, setLatestStructuredList] = useState<StructuredFormulationView[]>([]);
  const [latestActions, setLatestActions] = useState<SuggestedNextAction[]>([]);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [corpusStatus, setCorpusStatus] = useState<CorpusStatus>("unknown");
  const [structuredBrief, setStructuredBrief] = useState<StructuredBrief>({});

  const refreshThreads = useCallback(async () => {
    try {
      const list = await fetchChatThreads();
      setThreads(list);
    } catch {
      setThreads([]);
    } finally {
      setIsLoadingThreads(false);
    }
  }, []);

  const startNewChat = useCallback(async () => {
    setErrorMessage(null);
    setLastFailedMessage(null);
    setMessages([]);
    setLatestEvidence([]);
    setLatestStructured(null);
    setLatestActions([]);
    setMessageInput("");
    try {
      const id = await createChatThread();
      setThreadId(id);
      await refreshThreads();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to create a new chat.";
      setErrorMessage(message);
    }
  }, [refreshThreads]);

  useEffect(() => {
    fetchBackendHealth()
      .then(() => {
        setBackendStatus("ok");
        return fetchBackendReadiness();
      })
      .then((ready) => setCorpusStatus(ready.ready ? "ready" : "degraded"))
      .catch(() => {
        setBackendStatus("down");
        setCorpusStatus("unknown");
      });
  }, []);

  useEffect(() => {
    void refreshThreads();
    void startNewChat();
  }, [refreshThreads, startNewChat]);

  const loadThread = async (id: string) => {
    if (id === threadId || isLoading) {
      return;
    }
    setErrorMessage(null);
    setLastFailedMessage(null);
    setIsLoading(true);
    try {
      const detail = await fetchChatThread(id);
      const mapped = detail.messages.map(mapStoredMessage);
      const panels = latestAssistantPanels(mapped);
      setThreadId(detail.id);
      setMessages(mapped);
      setLatestEvidence(panels.evidence);
      setLatestStructured(panels.structured);
      setLatestStructuredList(panels.structuredList);
      setLatestActions(panels.actions);
      setMessageInput("");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to load chat history.";
      setErrorMessage(message);
    } finally {
      setIsLoading(false);
    }
  };

  const executeTurn = async (rawMessage: string) => {
    if (!threadId) {
      return;
    }
    const userMessage = createMessage("user", rawMessage);
    setMessages((previous) => [...previous, userMessage]);
    setIsLoading(true);
    setErrorMessage(null);
    setLastFailedMessage(null);

    const hasBrief =
      structuredBrief.product_type ||
      (structuredBrief.banned_ingredients?.length ?? 0) > 0 ||
      (structuredBrief.preferred_ingredients?.length ?? 0) > 0;

    const payload: ChatTurnRequest = {
      thread_id: threadId,
      message: rawMessage,
      ...(hasBrief ? { structured_brief: structuredBrief } : {}),
    };

    try {
      const response = await sendChatTurn(payload);
      const structuredList =
        response.structured_formulations && response.structured_formulations.length > 0
          ? response.structured_formulations
          : response.structured_formulation
            ? [response.structured_formulation]
            : [];
      const assistantMessage = createMessage("assistant", response.assistant_message, {
        citedEvidence: response.cited_evidence ?? [],
        suggestedActions: response.suggested_next_actions ?? [],
        structuredFormulation: structuredList[0] ?? null,
        structuredFormulations: structuredList,
        route: response.route,
        llmUsed: response.llm_used,
        searchConfidence: response.search_confidence,
      });
      setMessages((previous) => [...previous, assistantMessage]);
      setLatestEvidence(response.cited_evidence ?? []);
      setLatestStructuredList(structuredList);
      setLatestStructured(structuredList[0] ?? null);
      setLatestActions(response.suggested_next_actions ?? []);
      setMessageInput("");
      await refreshThreads();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to send chat message.";
      setErrorMessage(message);
      setLastFailedMessage(rawMessage);
      setMessages((previous) => previous.filter((m) => m.id !== userMessage.id));
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async () => {
    const trimmed = messageInput.trim();
    if (!trimmed) {
      return;
    }
    await executeTurn(trimmed);
  };

  const handleRetry = async () => {
    if (!lastFailedMessage) {
      return;
    }
    await executeTurn(lastFailedMessage);
  };

  const handleSuggestionClick = (suggestion: string) => {
    setMessageInput(suggestion);
  };

  const handleActionClick = (action: SuggestedNextAction) => {
    setMessageInput(action.label);
  };

  const status = STATUS_PILL[backendStatus];
  const corpusLabel =
    backendStatus !== "ok"
      ? status.label
      : corpusStatus === "ready"
        ? t("status.corpusReady")
        : corpusStatus === "degraded"
          ? t("status.corpusDegraded")
          : status.label;

  const handleDeleteThread = async (id: string) => {
    try {
      await deleteChatThread(id);
      if (id === threadId) {
        await startNewChat();
      }
      await refreshThreads();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Delete failed");
    }
  };

  const handleRenameThread = async (id: string, title: string) => {
    try {
      await updateChatThreadTitle(id, title);
      await refreshThreads();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Rename failed");
    }
  };

  return (
    <ChatLayout
      historyPanel={
        <ChatHistorySidebar
          threads={threads}
          activeThreadId={threadId}
          isLoadingThreads={isLoadingThreads}
          onSelectThread={(id) => void loadThread(id)}
          onNewChat={() => void startNewChat()}
          onDeleteThread={(id) => void handleDeleteThread(id)}
          onRenameThread={(id, title) => void handleRenameThread(id, title)}
        />
      }
      leftPanel={
        <>
          <header className="flex items-center justify-between gap-3 border-b border-border bg-surface px-4 py-3 lg:px-6 lg:py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl">
                <Image
                  src="/logo.png"
                  alt=""
                  width={28}
                  height={28}
                  className="h-7 w-7 object-contain"
                />
              </div>
              <div>
                <h1 className="text-base font-semibold text-text-primary">{t("app.title")}</h1>
                <p className="text-xs text-text-secondary">{t("app.subtitle")}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/warehouse"
                className="rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-text-primary hover:bg-background"
              >
                {t("nav.warehouse")}
              </Link>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-2.5 py-1 text-xs font-medium ${status.text}`}
                title={threadId ? `thread: ${threadId}` : undefined}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    corpusStatus === "ready" ? "bg-success" : status.dot
                  } ${backendStatus === "checking" ? "animate-pulse" : ""}`}
                />
                {corpusLabel}
              </span>
              <ThemeToggle />
            </div>
          </header>
          <ConstraintsPanel brief={structuredBrief} onChange={setStructuredBrief} />
          <ChatThread
            messages={messages}
            isLoading={isLoading}
            onSuggestionClick={handleSuggestionClick}
          />
          <ChatComposer
            value={messageInput}
            onChange={setMessageInput}
            onSubmit={handleSubmit}
            disabled={isLoading || !threadId}
            errorMessage={errorMessage}
            onRetry={lastFailedMessage ? handleRetry : undefined}
          />
        </>
      }
      rightPanel={
        <div className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto p-4 lg:p-6">
          <StructuredFormulaPanel
            formulation={latestStructured}
            formulations={latestStructuredList}
          />
          <EvidencePanel evidence={latestEvidence} />
          <SuggestedActionsPanel
            actions={latestActions}
            onActionClick={handleActionClick}
          />
        </div>
      }
    />
  );
}
