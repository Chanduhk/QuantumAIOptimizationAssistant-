import React, { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface JamComposerProps {
  onSend: (message: string) => void;
  isProcessing: boolean;
}

export function JamComposer({ onSend, isProcessing }: JamComposerProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      // Auto-resize textarea
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [value]);

  const handleSend = () => {
    const trimmed = value.trim();
    if (trimmed && !isProcessing) {
      onSend(trimmed);
      setValue('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="relative w-full max-w-4xl mx-auto rounded-2xl bg-[var(--color-surface)] border border-[var(--color-border)] shadow-sm focus-within:border-indigo-500/50 focus-within:ring-1 focus-within:ring-indigo-500/50 transition-all duration-300 flex items-end p-2 overflow-hidden">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Try: plan my day, get recommendations, analyze my productivity..."
        className="w-full max-h-[200px] bg-transparent text-[var(--color-text)] placeholder-[var(--color-text-muted)] border-none focus:outline-none focus:ring-0 resize-none py-3 px-4 min-h-[48px]"
        rows={1}
        disabled={isProcessing}
        aria-label="Message JAM"
      />
      <div className="flex-shrink-0 mb-1 mr-1">
        <button
          onClick={handleSend}
          disabled={!value.trim() || isProcessing}
          className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50 disabled:bg-[var(--color-surface-hover)] disabled:text-[var(--color-text-muted)] transition-colors"
          aria-label="Send command"
        >
          {isProcessing ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Send className="w-5 h-5 ml-1" />
          )}
        </button>
      </div>
    </div>
  );
}
