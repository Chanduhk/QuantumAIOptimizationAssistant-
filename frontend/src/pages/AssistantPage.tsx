import React, { useEffect, useRef } from 'react';
import { JamEmptyState } from '@/components/assistant/JamEmptyState';
import { JamComposer } from '@/components/assistant/JamComposer';
import { JamMessage } from '@/components/assistant/JamMessage';
import { useJamStore } from '@/stores/jamStore';
import { useAICommand } from '@/api/hooks';
import { useUserStore } from '@/stores/userStore';

export function AssistantPage() {
  const { messages, addMessage, isProcessing, setIsProcessing } = useJamStore();
  const updateMessage = useJamStore((state) => state.updateMessage);
  const clearMessages = useJamStore((state) => state.clearMessages);
  const { mutateAsync: sendCommand } = useAICommand();
  const userId = useUserStore((state) => state.userId);
  const scrollRef = useRef<HTMLDivElement>(null);
  const requestInFlight = useRef(false);
  const requestGeneration = useRef(0);

  useEffect(() => {
    requestGeneration.current += 1;
    requestInFlight.current = false;
    clearMessages();
  }, [userId, clearMessages]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isProcessing]);

  const handleSend = async (text: string, retryMessageId?: string) => {
    const command = text.trim();
    if (!command || isProcessing || requestInFlight.current || userId === null) return;

    requestInFlight.current = true;
    const generation = requestGeneration.current;
    const assistantMessageId = retryMessageId ?? crypto.randomUUID();
    if (retryMessageId) {
      updateMessage(assistantMessageId, {
        isError: false,
        isPending: true,
        errorMessage: undefined,
        result: undefined,
        timestamp: Date.now(),
      });
    } else {
      addMessage({ id: crypto.randomUUID(), role: 'user', command, timestamp: Date.now() });
      addMessage({ id: assistantMessageId, role: 'assistant', isPending: true, timestamp: Date.now() });
    }
    setIsProcessing(true);

    try {
      const response = await sendCommand({
        user_id: userId,
        command,
        days_back: 90,
      });
      if (generation !== requestGeneration.current || useUserStore.getState().userId !== userId) return;
      if (response.result.success === false) {
        const backendErrors = response.result.errors;
        const detail = Array.isArray(backendErrors)
          ? backendErrors.filter((item): item is string => typeof item === "string").join("; ")
          : undefined;
        throw new Error(detail || "JAM could not complete this supported command.");
      }
      updateMessage(assistantMessageId, {
        intent: response.intent,
        result: response.result,
        isPending: false,
        timestamp: Date.now(),
      });
    } catch (error) {
      if (generation !== requestGeneration.current || useUserStore.getState().userId !== userId) return;
      updateMessage(assistantMessageId, {
        isError: true,
        errorMessage: error instanceof Error ? error.message : "An unknown error occurred.",
        retryCommand: command,
        isPending: false,
        timestamp: Date.now(),
      });
    } finally {
      if (generation === requestGeneration.current) {
        requestInFlight.current = false;
        setIsProcessing(false);
      }
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] bg-transparent">
      
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]"></div>
          <h2 className="text-sm font-semibold tracking-wide uppercase text-[var(--color-text)]">
            JAM Assistant
          </h2>
          <p className="text-xs text-[var(--color-text-muted)]">
            Supported workflow commands only; open-ended chat responses are not configured.
          </p>
        </div>
        <div className="text-xs font-medium text-[var(--color-text-muted)] bg-[var(--color-surface)] px-3 py-1 rounded-full border border-[var(--color-border)]">
          {messages.length > 0 ? "Session Active" : "Ready"}
        </div>
      </div>

      {/* Main Conversation Area */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 md:px-8 lg:px-12 py-8 scroll-smooth"
      >
        <div className="max-w-4xl mx-auto flex flex-col min-h-full">
          {messages.length === 0 ? (
            <div className="flex-1 flex items-center justify-center">
              <JamEmptyState onSuggestionClick={handleSend} />
            </div>
          ) : (
            <div className="flex-1">
              <div className="mb-8 text-center text-xs text-[var(--color-text-muted)] opacity-50">
                Conversation is kept in memory for this signed-in session only; the backend does not restore chat history after refresh.
              </div>
              {messages.map((msg) => (
                <JamMessage key={msg.id} message={msg} onRetry={msg.isError && msg.retryCommand ? () => void handleSend(msg.retryCommand!, msg.id) : undefined} />
              ))}
              
              {/* Optional: clear conversation button at top or bottom if they want, but keeping it clean for now */}
            </div>
          )}
        </div>
      </div>

      {/* Composer Area */}
      <div className="flex-shrink-0 p-4 pb-6 bg-gradient-to-t from-[var(--color-background)] to-transparent pt-8">
        <JamComposer onSend={handleSend} isProcessing={isProcessing} />
      </div>
      
    </div>
  );
}
