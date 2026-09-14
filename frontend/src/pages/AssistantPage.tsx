import React, { useEffect, useRef } from 'react';
import { JamEmptyState } from '@/components/assistant/JamEmptyState';
import { JamComposer } from '@/components/assistant/JamComposer';
import { JamMessage } from '@/components/assistant/JamMessage';
import { useJamStore } from '@/stores/jamStore';
import { useAICommand } from '@/api/hooks';
import { useUserStore } from '@/stores/userStore';

export function AssistantPage() {
  const { messages, addMessage, isProcessing, setIsProcessing } = useJamStore();
  const { mutateAsync: sendCommand } = useAICommand();
  const user_id = useUserStore((state) => state.userId);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isProcessing]);

  const handleSend = async (text: string) => {
    if (!text.trim() || isProcessing || !user_id) return;

    const userMsgId = crypto.randomUUID();
    const asstMsgId = crypto.randomUUID();

    // 1. Add User Message
    addMessage({
      id: userMsgId,
      role: 'user',
      command: text,
      timestamp: Date.now(),
    });

    // 2. Set Processing State (UI will show indicator on composer)
    setIsProcessing(true);

    try {
      // 3. Send Command
      const response = await sendCommand({
        user_id,
        command: text,
        days_back: 90,
      });

      // 4. Add Assistant Message on Success
      addMessage({
        id: asstMsgId,
        role: 'assistant',
        intent: response.intent,
        result: response.result,
        timestamp: Date.now(),
      });
    } catch (error) {
      // 5. Add Error Message on Failure
      addMessage({
        id: asstMsgId,
        role: 'assistant',
        isError: true,
        errorMessage: error instanceof Error ? error.message : "An unknown error occurred.",
        timestamp: Date.now(),
      });
    } finally {
      setIsProcessing(false);
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
                Conversation history is available for this session only.
              </div>
              {messages.map((msg) => (
                <JamMessage key={msg.id} message={msg} />
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
