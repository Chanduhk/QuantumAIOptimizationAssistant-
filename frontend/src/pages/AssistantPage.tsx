import React, { Fragment, useEffect, useRef, useState } from 'react';
import { JamEmptyState } from '@/components/assistant/JamEmptyState';
import { JamComposer } from '@/components/assistant/JamComposer';
import { JamMessage } from '@/components/assistant/JamMessage';
import { useJamStore } from '@/stores/jamStore';
import { useAICommand, useProviderStatus, useJamConversations, useDeleteConversation, useCreateConversation } from '@/api/hooks';
import { useUserStore } from '@/stores/userStore';
import { api } from '@/api/endpoints';
import { Link } from 'react-router-dom';
import { MessageSquare, Plus, Trash2, PanelLeftClose, PanelLeft, Clock } from 'lucide-react';
import { Button } from '@/components/ui/Button';

export function AssistantPage() {
  const { messages, setMessages, addMessage, isProcessing, setIsProcessing, activeConversationId, setActiveConversationId } = useJamStore();
  const updateMessage = useJamStore((state) => state.updateMessage);
  const clearMessages = useJamStore((state) => state.clearMessages);
  const { mutateAsync: sendCommand } = useAICommand();
  const { data: providerStatus } = useProviderStatus();
  const { data: conversations, refetch: refetchConversations } = useJamConversations();
  const { mutateAsync: deleteConversation } = useDeleteConversation();
  const { mutateAsync: createNewConversation } = useCreateConversation();
  const userId = useUserStore((state) => state.userId);
  const scrollRef = useRef<HTMLDivElement>(null);
  const requestInFlight = useRef(false);
  const requestGeneration = useRef(0);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Auto-load most recent conversation on mount if none active
  useEffect(() => {
    if (userId && !activeConversationId && conversations && conversations.length > 0) {
      void selectConversation(conversations[0].id);
    }
  }, [userId, conversations, activeConversationId]);

  // Reset when user changes
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

  const selectConversation = async (conversationId: string) => {
    try {
      setLoadingHistory(true);
      setActiveConversationId(conversationId);
      const detail = await api.jam.getConversation(conversationId);
      const loadedMessages = (detail.messages || []).map((m) => ({
        id: m.id,
        role: m.role as "user" | "assistant",
        timestamp: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
        command: m.role === 'user' ? m.content : undefined,
        intent: m.intent || undefined,
        result: (m.metadata as Record<string, unknown>) || (m.role === 'assistant' ? { executive_summary: m.content, answer: m.content } : undefined),
      }));
      setMessages(loadedMessages);
    } catch {
      // If load fails, keep existing state
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleNewChat = () => {
    setActiveConversationId(null);
    clearMessages();
  };

  const handleDeleteConversation = async (e: React.MouseEvent, conversationId: string) => {
    e.stopPropagation();
    try {
      await deleteConversation(conversationId);
      if (activeConversationId === conversationId) {
        handleNewChat();
      }
      void refetchConversations();
    } catch {
      // Ignored
    }
  };

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
        conversation_id: activeConversationId ?? undefined,
      });
      if (generation !== requestGeneration.current || useUserStore.getState().userId !== userId) return;

      if (response.conversation_id && response.conversation_id !== activeConversationId) {
        setActiveConversationId(response.conversation_id);
        void refetchConversations();
      }

      if (response.result.success === false) {
        const backendErrors = response.result.errors;
        const detail = Array.isArray(backendErrors)
          ? backendErrors.filter((item): item is string => typeof item === "string").join("; ")
          : undefined;
        throw new Error(detail || "JAM could not complete this command.");
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

  const renderProviderBadge = () => {
    if (!providerStatus) {
      return (
        <span className="flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full bg-surface-2 text-content-secondary border border-border/60">
          <span className="w-1.5 h-1.5 rounded-full bg-content-muted"></span>
          Checking Engine…
        </span>
      );
    }
    if (providerStatus.status === 'openai_configured_and_available') {
      return (
        <span className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          OpenAI ({providerStatus.model}) Active
        </span>
      );
    }
    if (providerStatus.status === 'openai_rate_limited' || providerStatus.error_category === 'RATE_LIMIT_EXCEEDED') {
      return (
        <span className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30" title="OpenAI quota or rate limit exceeded. Deterministic local assistant is actively handling your workflows.">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
          OpenAI Rate Limited • Fallback Active
        </span>
      );
    }
    if (providerStatus.status === 'openai_authentication_failed' || providerStatus.error_category === 'AUTHENTICATION_ERROR') {
      return (
        <span className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full bg-rose-500/15 text-rose-400 border border-rose-500/30" title="Invalid OpenAI API key. Check Settings.">
          <span className="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
          OpenAI Auth Failed • Fallback Active
        </span>
      );
    }
    if (providerStatus.status === 'openai_timeout' || providerStatus.error_category === 'TIMEOUT') {
      return (
        <span className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full bg-rose-500/15 text-rose-400 border border-rose-500/30">
          <span className="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
          OpenAI Timeout • Fallback Active
        </span>
      );
    }
    if (providerStatus.is_configured) {
      return (
        <span className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full bg-primary/15 text-primary border border-primary/30">
          <span className="w-1.5 h-1.5 rounded-full bg-primary"></span>
          OpenAI Configured ({providerStatus.model})
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full bg-surface-2 text-content-secondary border border-border/60">
        <span className="w-1.5 h-1.5 rounded-full bg-content-muted"></span>
        Deterministic Parser Active (OpenAI Unconfigured)
      </span>
    );
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] rounded-2xl border border-border/70 bg-surface-1/70 backdrop-blur-md shadow-glass overflow-hidden">
      
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-4 sm:px-6 py-4 border-b border-border/60 bg-surface-1/90">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-lg text-content-secondary hover:text-content-primary hover:bg-surface-2/70 transition-colors"
            title={sidebarOpen ? "Hide chat history" : "Show chat history"}
            aria-label="Toggle chat history"
          >
            {sidebarOpen ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeft className="w-4 h-4" />}
          </button>
          <div className="flex items-center justify-center w-2 h-2 rounded-full bg-primary" aria-hidden="true"></div>
          <div>
            <h2 className="text-sm font-semibold tracking-wide uppercase text-content-primary">
              Ask JAM
            </h2>
            <p className="text-xs text-content-tertiary hidden sm:block">
              Workflow commands, planning & chat · OpenAI or deterministic parser
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {renderProviderBadge()}
          <div className="text-xs font-medium text-content-tertiary bg-surface-2/80 px-3 py-1 rounded-full border border-border/60 hidden sm:block">
            {messages.length > 0 ? "Session Active" : "Ready"}
          </div>
        </div>
      </div>

      {/* Main Body with Sidebar + Chat */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        
        {/* Chat History Sidebar */}
        {sidebarOpen && (
          <aside className="w-64 border-r border-border/50 bg-surface-1/50 flex flex-col flex-shrink-0">
            <div className="p-3 border-b border-border/40">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleNewChat}
                className="w-full justify-start text-xs font-medium gap-2 bg-surface-2/80 hover:bg-surface-2"
              >
                <Plus className="w-3.5 h-3.5 text-primary" />
                New Chat
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              <p className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-content-tertiary">
                Recent Conversations
              </p>
              {!conversations || conversations.length === 0 ? (
                <div className="px-3 py-6 text-center text-xs text-content-tertiary">
                  <MessageSquare className="w-6 h-6 mx-auto mb-2 opacity-40 text-content-muted" />
                  No stored chats yet. Start a conversation with JAM!
                </div>
              ) : (
                conversations.map((c) => {
                  const isActive = c.id === activeConversationId;
                  return (
                    <div
                      key={c.id}
                      onClick={() => void selectConversation(c.id)}
                      className={`group flex items-center justify-between gap-2 px-3 py-2 rounded-lg cursor-pointer text-xs transition-colors ${
                        isActive
                          ? 'bg-primary/15 text-primary border border-primary/25 font-medium'
                          : 'text-content-secondary hover:bg-surface-2/70 hover:text-content-primary'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 text-content-muted group-hover:text-primary" />
                        <span className="truncate">{c.title || "Conversation"}</span>
                      </div>
                      <button
                        onClick={(e) => void handleDeleteConversation(e, c.id)}
                        className="opacity-0 group-hover:opacity-100 p-1 text-content-tertiary hover:text-status-error transition-opacity"
                        title="Delete chat"
                        aria-label="Delete chat"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </aside>
        )}

        {/* Main Conversation & Messages Area */}
        <div className="flex flex-col flex-1 min-w-0">
          <div 
            ref={scrollRef}
            className="flex-1 overflow-y-auto px-4 md:px-8 lg:px-12 py-8 scroll-smooth"
          >
            <div className="max-w-4xl mx-auto flex flex-col min-h-full">
              {loadingHistory ? (
                <div className="flex-1 flex items-center justify-center text-xs text-content-tertiary gap-2">
                  <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  Restoring conversation history…
                </div>
              ) : messages.length === 0 ? (
                <div className="flex-1 flex items-center justify-center">
                  <JamEmptyState onSuggestionClick={handleSend} />
                </div>
              ) : (
                <div className="flex-1">
                  <div className="mb-8 text-center text-xs text-content-tertiary opacity-70 flex items-center justify-center gap-1.5">
                    <Clock className="w-3.5 h-3.5" />
                    Conversation history is saved automatically to your personal account.
                  </div>
                  {messages.map((msg) => (
                    <Fragment key={msg.id}>
                    <JamMessage 
                      message={msg} 
                      onRetry={msg.isError && msg.retryCommand ? () => void handleSend(msg.retryCommand!, msg.id) : undefined} 
                      onRefine={handleSend}
                    />
                    {msg.role === 'assistant' && !msg.isPending && !msg.isError && msg.intent && (
                      <div className="-mt-4 mb-6 ml-12 flex flex-wrap gap-2">
                        {msg.intent === 'plan_day' && <Link className="text-xs text-primary underline-offset-4 hover:underline" to="/planning">Open My Schedule</Link>}
                        {msg.intent === 'get_recommendations' && <Link className="text-xs text-primary underline-offset-4 hover:underline" to="/planning">Review recommendations</Link>}
                        {msg.intent === 'optimize_schedule' && <Link className="text-xs text-primary underline-offset-4 hover:underline" to="/optimization">Open Optimization Lab</Link>}
                        {msg.intent === 'analyze_productivity' && <Link className="text-xs text-primary underline-offset-4 hover:underline" to="/intelligence">Open My Insights</Link>}
                        {(msg.intent === 'create_task' || msg.intent === 'list_tasks' || msg.intent === 'prioritize_tasks') && (
                          <Link className="text-xs text-primary underline-offset-4 hover:underline" to="/tasks">Open My Tasks</Link>
                        )}
                        {msg.intent === 'accept_plan' && (
                          <Link className="text-xs text-primary underline-offset-4 hover:underline" to="/tasks">View Updated Tasks</Link>
                        )}
                      </div>
                    )}
                    </Fragment>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Composer Area */}
          <div className="flex-shrink-0 p-4 pb-6 bg-gradient-to-t from-surface-1 via-surface-1/90 to-transparent pt-6 border-t border-border/40">
            <JamComposer onSend={handleSend} isProcessing={isProcessing} />
          </div>
        </div>

      </div>
      
    </div>
  );
}
