import { create } from "zustand";

export interface JamMessage {
  id: string;
  role: "user" | "assistant";
  timestamp: number;
  
  // For user messages
  command?: string;
  
  // For assistant messages (backend response)
  intent?: string;
  result?: Record<string, unknown>;
  
  // For errors
  isError?: boolean;
  errorMessage?: string;
  retryCommand?: string;
  isPending?: boolean;
}

interface JamState {
  activeConversationId: string | null;
  setActiveConversationId: (id: string | null) => void;
  messages: JamMessage[];
  setMessages: (messages: JamMessage[]) => void;
  addMessage: (message: JamMessage) => void;
  updateMessage: (id: string, updates: Partial<JamMessage>) => void;
  clearMessages: () => void;
  isProcessing: boolean;
  setIsProcessing: (isProcessing: boolean) => void;
}

export const useJamStore = create<JamState>((set) => ({
  activeConversationId: null,
  setActiveConversationId: (id) => set({ activeConversationId: id }),
  messages: [],
  setMessages: (messages) => set({ messages }),
  
  addMessage: (message) => 
    set((state) => ({ messages: [...state.messages, message] })),
    
  updateMessage: (id, updates) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, ...updates } : msg
      ),
    })),
    
  clearMessages: () => set({ messages: [], activeConversationId: null, isProcessing: false }),
  
  isProcessing: false,
  setIsProcessing: (isProcessing) => set({ isProcessing }),
}));
