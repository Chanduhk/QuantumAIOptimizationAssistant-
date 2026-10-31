import * as React from "react";
import { useSearchParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUp, CalendarRange, History, ListOrdered, MessageSquarePlus, PanelLeft, PlusSquare, Sparkles, Trash2, TrendingUp, X } from "lucide-react";
import { useAICommand, useCreateConversation, useDeleteConversation, useJamConversations, useProviderStatus } from "@/api/hooks";
import { api } from "@/api/endpoints";
import { getApiErrorMessage } from "@/api/client";
import { useJamStore } from "@/stores/jamStore";
import { useUserStore } from "@/stores/userStore";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Feedback";
import { toast } from "@/components/ui/Toaster";
import { HelioxMark } from "@/components/brand/HelioxMark";
import { MessageView } from "@/features/assistant/MessageView";
import { providerState } from "@/lib/status";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

const STARTERS = [
  { icon: CalendarRange, title: "Plan my day", prompt: "Plan my day: finish the project report (2 hours, due today), review pull requests (45 minutes) and go to the gym for an hour." },
  { icon: ListOrdered, title: "What first?", prompt: "Which tasks should I complete first?" },
  { icon: PlusSquare, title: "Capture a task", prompt: "Add task: prepare slides for Friday's review, 60 minutes, high priority" },
  { icon: TrendingUp, title: "Use what I have", prompt: "Use my existing tasks and goals. Plan my day." },
];

function Composer({ onSend, disabled }: { onSend: (text: string) => void; disabled: boolean }) {
  const [text, setText] = React.useState("");
  const ref = React.useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const submit = () => {
    if (!text.trim() || disabled) return;
    onSend(text);
    setText("");
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="relative rounded-2xl border border-border bg-surface-1 shadow-lift transition-colors focus-within:border-primary/40"
    >
      <textarea
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        rows={1}
        placeholder="Describe your day, add a task, or refine the current plan…"
        aria-label="Message JAM"
        className="block max-h-[200px] w-full resize-none bg-transparent px-4 pb-12 pt-3.5 text-[14px] leading-relaxed text-content-primary placeholder:text-content-muted focus:outline-none"
      />
      <div className="absolute inset-x-3 bottom-2.5 flex items-center justify-between">
        <span className="text-[11px] text-content-muted"><span className="hidden sm:inline">Enter to send · Shift+Enter for a new line</span></span>
        <Button type="submit" size="icon-sm" className="rounded-lg" disabled={!text.trim() || disabled} aria-label="Send message">
          <ArrowUp />
        </Button>
      </div>
    </form>
  );
}

function ConversationList({ activeId, onSelect, onNew, onClose }: { activeId: string | null; onSelect: (id: string) => void; onNew: () => void; onClose?: () => void }) {
  const { data, isLoading } = useJamConversations();
  const remove = useDeleteConversation();
  const conversations = data ?? [];
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 p-3">
        <p className="eyebrow px-1">Conversations</p>
        <div className="flex items-center gap-1">
          <Button size="icon-sm" variant="ghost" onClick={onNew} aria-label="New conversation" title="New conversation"><MessageSquarePlus /></Button>
          {onClose && <Button size="icon-sm" variant="ghost" onClick={onClose} aria-label="Close conversations"><X /></Button>}
        </div>
      </div>
      <div className="scrollbar-thin flex-1 overflow-y-auto px-2 pb-3">
        {isLoading ? (
          <div className="space-y-2 px-1">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
        ) : conversations.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-content-muted">Your conversations will appear here.</p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((c) => (
              <li key={c.id} className="group relative">
                <button
                  type="button"
                  onClick={() => onSelect(c.id)}
                  className={cn("w-full rounded-lg px-3 py-2 pr-9 text-left transition-colors", c.id === activeId ? "bg-surface-2 dark:bg-surface-3/70" : "hover:bg-surface-2/70")}
                >
                  <p className="truncate text-[13px] font-medium text-content-primary">{c.title || "Untitled"}</p>
                  <p className="text-[11px] text-content-muted">{c.message_count} messages · {formatRelative(c.updated_at ?? c.created_at)}</p>
                </button>
                <button
                  type="button"
                  aria-label={`Delete conversation ${c.title}`}
                  onClick={() =>
                    remove.mutate(c.id, {
                      onSuccess: () => {
                        if (c.id === activeId) onNew();
                      },
                      onError: (e) => toast("error", "Couldn't delete conversation", getApiErrorMessage(e)),
                    })
                  }
                  className="absolute right-2 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-content-muted opacity-0 transition-opacity hover:bg-status-error/10 hover:text-status-error focus:opacity-100 group-hover:opacity-100"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function AssistantPage() {
  const { messages, setMessages, addMessage, updateMessage, clearMessages, isProcessing, setIsProcessing, activeConversationId, setActiveConversationId } = useJamStore();
  const userId = useUserStore((s) => s.userId);
  const { mutateAsync: sendCommand } = useAICommand();
  const { mutateAsync: createConversation } = useCreateConversation();
  const provider = useProviderStatus();
  const providerInfo = providerState(provider.data);
  const conversations = useJamConversations();
  const [params, setParams] = useSearchParams();
  const [loadingHistory, setLoadingHistory] = React.useState(false);
  const [mobileListOpen, setMobileListOpen] = React.useState(false);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const inFlight = React.useRef(false);
  const autoLoaded = React.useRef(false);

  const selectConversation = React.useCallback(
    async (conversationId: string) => {
      setMobileListOpen(false);
      try {
        setLoadingHistory(true);
        setActiveConversationId(conversationId);
        const detail = await api.jam.getConversation(conversationId);
        setMessages(
          (detail.messages || []).map((m) => ({
            id: m.id,
            role: m.role,
            timestamp: m.created_at ? new Date(m.created_at.endsWith("Z") || m.created_at.includes("+") ? m.created_at : `${m.created_at}Z`).getTime() : Date.now(),
            command: m.role === "user" ? m.content : undefined,
            intent: m.intent || undefined,
            result: (m.metadata as Record<string, unknown>) || (m.role === "assistant" ? { executive_summary: m.content, answer: m.content } : undefined),
            fromHistory: true,
          }))
        );
      } catch (error) {
        toast("error", "Couldn't open conversation", getApiErrorMessage(error));
      } finally {
        setLoadingHistory(false);
      }
    },
    [setActiveConversationId, setMessages]
  );

  // Open the most recent conversation on first visit.
  React.useEffect(() => {
    if (autoLoaded.current || params.get("q")) return;
    if (!activeConversationId && messages.length === 0 && conversations.data?.length) {
      autoLoaded.current = true;
      void selectConversation(conversations.data[0].id);
    }
  }, [conversations.data, activeConversationId, messages.length, selectConversation, params]);

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = React.useCallback(
    async (text: string, retryId?: string) => {
      const command = text.trim();
      if (!command || inFlight.current || userId === null) return;
      inFlight.current = true;
      const assistantId = retryId ?? crypto.randomUUID();
      if (retryId) updateMessage(assistantId, { isError: false, isPending: true, errorMessage: undefined, result: undefined, timestamp: Date.now() });
      else {
        addMessage({ id: crypto.randomUUID(), role: "user", command, timestamp: Date.now() });
        addMessage({ id: assistantId, role: "assistant", isPending: true, timestamp: Date.now(), retryCommand: command });
      }
      setIsProcessing(true);
      try {
        // Without an id the API appends to the most recent conversation, so a
        // fresh chat gets its own conversation first.
        let conversationId = useJamStore.getState().activeConversationId;
        if (!conversationId) {
          const created = await createConversation(command.length > 60 ? `${command.slice(0, 57)}…` : command);
          conversationId = created.id;
          setActiveConversationId(conversationId);
        }
        const response = await sendCommand({ user_id: userId, command, days_back: 90, conversation_id: conversationId });
        if (useUserStore.getState().userId !== userId) return;
        if (response.conversation_id) setActiveConversationId(response.conversation_id);
        if (response.result?.success === false) {
          const errors = Array.isArray(response.result.errors) ? response.result.errors.filter((e): e is string => typeof e === "string").join("; ") : "";
          throw new Error(errors || String(response.result.executive_summary || "JAM could not complete this command."));
        }
        updateMessage(assistantId, { intent: response.intent, result: response.result, isPending: false, timestamp: Date.now() });
      } catch (error) {
        updateMessage(assistantId, { isPending: false, isError: true, errorMessage: getApiErrorMessage(error), retryCommand: command });
      } finally {
        inFlight.current = false;
        setIsProcessing(false);
      }
    },
    [userId, addMessage, updateMessage, setIsProcessing, sendCommand, createConversation, setActiveConversationId]
  );

  // Commands handed over from other pages (?q=…) start a fresh conversation.
  React.useEffect(() => {
    const q = params.get("q");
    if (!q || userId === null) return;
    autoLoaded.current = true;
    const next = new URLSearchParams(params);
    next.delete("q");
    setParams(next, { replace: true });
    clearMessages();
    void send(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, userId]);

  const newChat = () => {
    autoLoaded.current = true;
    clearMessages();
    setActiveConversationId(null);
    setMobileListOpen(false);
  };

  // Only the newest proposal in a thread can be acted upon.
  const lastProposalIndex = React.useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const s = messages[i].result?.schedule;
      if (messages[i].role === "assistant" && Array.isArray(s) && s.length) return i;
    }
    return -1;
  }, [messages]);

  const activeTitle = conversations.data?.find((c) => c.id === activeConversationId)?.title;

  return (
    <div className="flex h-[calc(100dvh-3.5rem)]">
      <aside className="hidden w-[272px] shrink-0 border-r border-border-subtle bg-surface-1/40 dark:border-border xl:block">
        <ConversationList activeId={activeConversationId} onSelect={(id) => void selectConversation(id)} onNew={newChat} />
      </aside>

      <AnimatePresence>
        {mobileListOpen && (
          <div className="fixed inset-0 z-40 xl:hidden">
            <motion.div className="absolute inset-0 bg-black/40" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setMobileListOpen(false)} />
            <motion.div initial={{ x: -280 }} animate={{ x: 0 }} exit={{ x: -280 }} transition={{ type: "spring", stiffness: 400, damping: 40 }} className="absolute inset-y-0 left-0 w-[288px] border-r border-border bg-surface-1">
              <ConversationList activeId={activeConversationId} onSelect={(id) => void selectConversation(id)} onNew={newChat} onClose={() => setMobileListOpen(false)} />
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border-subtle px-4 dark:border-border sm:px-6">
          <Button size="icon-sm" variant="ghost" className="xl:hidden" onClick={() => setMobileListOpen(true)} aria-label="Show conversations"><PanelLeft /></Button>
          <p className="min-w-0 flex-1 truncate text-sm font-medium">{activeTitle ?? (messages.length ? "New conversation" : "JAM Assistant")}</p>
          <Badge tone={providerInfo.tone} dot title={providerInfo.detail}>{providerInfo.short}</Badge>
          <Button size="sm" variant="ghost" leftIcon={<MessageSquarePlus />} onClick={newChat} className="hidden sm:inline-flex">New</Button>
        </div>

        <div ref={scrollRef} className="scrollbar-thin flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
            {loadingHistory ? (
              <div className="space-y-4">
                <Skeleton className="ml-auto h-12 w-2/3 rounded-2xl" />
                <Skeleton className="h-48 w-full rounded-2xl" />
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center pt-[6vh] text-center">
                <div className="relative mb-6">
                  <div className="absolute inset-0 rounded-full bg-primary/20 blur-2xl" />
                  <HelioxMark className="relative size-14" animated />
                </div>
                <h1 className="text-2xl font-semibold tracking-tight">What should today look like?</h1>
                <p className="mt-2 max-w-md text-[14px] leading-relaxed text-content-tertiary">
                  Describe your tasks, deadlines and available time. JAM extracts them, runs the optimization pipeline and proposes a schedule you can refine, accept or reject.
                </p>
                <div className="mt-8 grid w-full gap-2.5 sm:grid-cols-2">
                  {STARTERS.map((s) => (
                    <button
                      key={s.title}
                      type="button"
                      onClick={() => void send(s.prompt)}
                      disabled={isProcessing}
                      className="group rounded-xl border border-border bg-surface-1 p-3.5 text-left transition-all hover:-translate-y-0.5 hover:border-primary/35 hover:shadow-card disabled:opacity-50"
                    >
                      <p className="flex items-center gap-2 text-[13px] font-medium"><s.icon className="size-4 text-primary" />{s.title}</p>
                      <p className="mt-1 line-clamp-2 text-xs text-content-tertiary">{s.prompt}</p>
                    </button>
                  ))}
                </div>
                {!!conversations.data?.length && (
                  <button type="button" onClick={() => setMobileListOpen(true)} className="mt-6 inline-flex items-center gap-1.5 text-xs text-content-tertiary hover:text-content-primary xl:hidden">
                    <History className="size-3.5" /> {conversations.data.length} previous conversations
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-6">
                {messages.map((m, i) => (
                  <MessageView
                    key={m.id}
                    message={m}
                    fromHistory={m.fromHistory || (i !== lastProposalIndex)}
                    onRetry={m.isError && m.retryCommand ? () => void send(m.retryCommand as string, m.id) : undefined}
                    onRefine={i === lastProposalIndex ? (text) => void send(text) : undefined}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0 bg-gradient-to-t from-background via-background to-background/0 px-4 pb-4 pt-2 sm:px-6">
          <div className="mx-auto max-w-3xl">
            <Composer onSend={(t) => void send(t)} disabled={isProcessing || userId === null} />
            <p className="mt-2 flex items-center justify-center gap-1.5 text-center text-[11px] text-content-muted">
              <Sparkles className="size-3" /> Proposals are only written to your tasks when you accept them.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
