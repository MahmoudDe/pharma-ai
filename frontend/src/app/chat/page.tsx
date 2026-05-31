"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatHistorySidebar } from "@/components/chat/ChatHistorySidebar";
import { ChatLayout } from "@/components/chat/ChatLayout";
import { ChatThread } from "@/components/chat/ChatThread";
import { EvidencePanel } from "@/components/chat/EvidencePanel";
import { StructuredFormulaPanel } from "@/components/chat/StructuredFormulaPanel";
import { SuggestedActionsPanel } from "@/components/chat/SuggestedActionsPanel";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { fetchBackendHealth } from "@/lib/backend";
import {
  createChatThread,
  fetchChatThread,
  fetchChatThreads,
  sendChatTurn,
} from "@/lib/chat";
import type {
  ChatMessage,
  ChatThreadMessage,
  ChatThreadSummary,
  ChatTurnRequest,
  CitedEvidence,
  StructuredFormulationView,
  SuggestedNextAction,
} from "@/types/chat";

type BackendStatus = "checking" | "ok" | "down";

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
  return createMessage(message.role, message.content, {
    id: message.id,
    createdAt: message.created_at,
    citedEvidence: message.cited_evidence,
    suggestedActions: message.suggested_next_actions,
  });
}

function latestAssistantEvidence(messages: ChatMessage[]): {
  evidence: CitedEvidence[];
  actions: SuggestedNextAction[];
} {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.role === "assistant") {
      return {
        evidence: message.citedEvidence ?? [],
        actions: message.suggestedActions ?? [],
      };
    }
  }
  return { evidence: [], actions: [] };
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
      const { evidence, actions } = latestAssistantEvidence(mapped);
      setThreadId(detail.id);
      setMessages(mapped);
      setLatestEvidence(evidence);
      setLatestStructured(null);
      setLatestActions(actions);
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

    const payload: ChatTurnRequest = {
      thread_id: threadId,
      message: rawMessage,
    };

    try {
      const response = await sendChatTurn(payload);
      const assistantMessage = createMessage("assistant", response.assistant_message, {
        citedEvidence: response.cited_evidence ?? [],
        suggestedActions: response.suggested_next_actions ?? [],
      });
      setMessages((previous) => [...previous, assistantMessage]);
      setLatestEvidence(response.cited_evidence ?? []);
      const structuredList =
        response.structured_formulations && response.structured_formulations.length > 0
          ? response.structured_formulations
          : response.structured_formulation
            ? [response.structured_formulation]
            : [];
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

  return (
    <ChatLayout
      historyPanel={
        <ChatHistorySidebar
          threads={threads}
          activeThreadId={threadId}
          isLoadingThreads={isLoadingThreads}
          onSelectThread={(id) => void loadThread(id)}
          onNewChat={() => void startNewChat()}
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
                <h1 className="text-base font-semibold text-text-primary">Pharma AI</h1>
                <p className="text-xs text-text-secondary">Reference-grounded formulation assistant</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-2.5 py-1 text-xs font-medium ${status.text}`}
                title={threadId ? `thread: ${threadId}` : undefined}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${status.dot} ${
                    backendStatus === "checking" ? "animate-pulse" : ""
                  }`}
                />
                {status.label}
              </span>
              <ThemeToggle />
            </div>
          </header>
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
