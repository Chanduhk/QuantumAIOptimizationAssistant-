import React from 'react';
import { Sparkles, Activity, LayoutList, GitMerge } from 'lucide-react';

interface JamEmptyStateProps {
  onSuggestionClick: (suggestion: string) => void;
}

export function JamEmptyState({ onSuggestionClick }: JamEmptyStateProps) {
  const suggestions = [
    {
      icon: <LayoutList className="w-5 h-5" />,
      text: "Plan my day",
    },
    {
      icon: <Activity className="w-5 h-5" />,
      text: "Get recommendations",
    },
    {
      icon: <Sparkles className="w-5 h-5" />,
      text: "Optimize my schedule",
    },
    {
      icon: <GitMerge className="w-5 h-5" />,
      text: "Analyze my productivity",
    }
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full w-full max-w-2xl mx-auto px-6 py-12 animate-in fade-in duration-700">
      <div className="mb-8 flex flex-col items-center">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center mb-6 shadow-[0_0_30px_rgba(99,102,241,0.1)]">
          <Sparkles className="w-8 h-8 text-indigo-400" />
        </div>
        
        <h1 className="text-3xl font-light tracking-tight text-[var(--color-text)] mb-2">
          JAM
        </h1>
        <p className="text-[var(--color-text-muted)] text-sm uppercase tracking-widest font-medium mb-8 text-center">
          AI Assistant / Companion
        </p>

        <div className="flex flex-wrap justify-center gap-x-4 gap-y-2 text-lg text-[var(--color-text-muted)] font-light mb-12">
          <span>Understand.</span>
          <span className="text-[var(--color-text-secondary)]">•</span>
          <span>Plan.</span>
          <span className="text-[var(--color-text-secondary)]">•</span>
          <span>Analyze.</span>
          <span className="text-[var(--color-text-secondary)]">•</span>
          <span>Optimize.</span>
        </div>

        <p className="text-xl text-[var(--color-text)] font-medium mb-8">
          "How can I help you?"
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
        {suggestions.map((suggestion, idx) => (
          <button
            key={idx}
            onClick={() => onSuggestionClick(suggestion.text)}
            className="flex items-center gap-4 p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] hover:border-indigo-500/50 transition-all duration-300 group text-left"
          >
            <div className="text-[var(--color-text-muted)] group-hover:text-indigo-400 transition-colors">
              {suggestion.icon}
            </div>
            <span className="text-[var(--color-text)] font-medium">
              {suggestion.text}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
