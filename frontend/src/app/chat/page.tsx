"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppHeader } from "@/components/ui/AppHeader";
import { StatusPill } from "@/components/ui/StatusPill";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatHistorySidebar } from "@/components/chat/ChatHistorySidebar";
import { ChatLayout } from "@/components/chat/ChatLayout";
import { ChatThread } from "@/components/chat/ChatThread";
import { ConstraintsPanel } from "@/components/chat/ConstraintsPanel";
import { EvidencePanel } from "@/components/chat/EvidencePanel";
import { StructuredFormulaPanel } from "@/components/chat/StructuredFormulaPanel";
import { SuggestedActionsPanel } from "@/components/chat/SuggestedActionsPanel";
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

function ChatPageContent() {
  const searchParams = useSearchParams();
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
      .then(() => setBackendStatus("ok"))
      .catch(() => setBackendStatus("down"));

    fetchBackendReadiness()
      .then((ready) => setCorpusStatus(ready.ready ? "ready" : "degraded"))
      .catch(() => setCorpusStatus("degraded"));
  }, []);

  useEffect(() => {
    void refreshThreads();
    void startNewChat();
  }, [refreshThreads, startNewChat]);

  useEffect(() => {
    const prompt = searchParams.get("prompt");
    if (prompt) {
      setMessageInput(prompt);
    }
  }, [searchParams]);

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

  const statusLabel =
    backendStatus === "checking"
      ? t("status.checking")
      : backendStatus === "down"
        ? t("status.backendDown")
        : corpusStatus === "ready"
          ? t("status.corpusReady")
          : corpusStatus === "degraded"
            ? t("status.corpusDegraded")
            : t("status.backendOnline");

  const statusVariant: "checking" | "ok" | "warning" | "error" =
    backendStatus === "checking"
      ? "checking"
      : backendStatus === "down"
        ? "error"
        : corpusStatus === "degraded"
          ? "warning"
          : "ok";

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
          <AppHeader
            active="chat"
            statusSlot={
              <StatusPill
                label={statusLabel}
                variant={statusVariant}
                pulse={backendStatus === "checking"}
              />
            }
          />
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
        <div className="stagger-children flex h-full min-h-0 flex-col gap-4 overflow-y-auto p-4 lg:p-6">
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

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="app-mesh-bg flex min-h-screen items-center justify-center">
          <div className="glass-panel animate-pulse rounded-2xl px-8 py-6 text-sm text-text-secondary">
            Loading chat…
          </div>
        </div>
      }
    >
      <ChatPageContent />
    </Suspense>
  );
}
