import React from 'react';
import { AlertCircle, Sparkles } from 'lucide-react';
import { JamMessage as JamMessageType } from '@/stores/jamStore';

interface JamMessageProps {
  message: JamMessageType;
}

export function JamMessage({ message }: JamMessageProps) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="w-full flex justify-end mb-6">
        <div className="max-w-[85%] bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl rounded-tr-none px-5 py-4 text-[var(--color-text)] shadow-sm">
          <p className="whitespace-pre-wrap">{message.command}</p>
          <div className="text-xs text-[var(--color-text-muted)] mt-2 text-right opacity-70">
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      </div>
    );
  }

  // Assistant Message
  return (
    <div className="w-full flex justify-start mb-6">
      <div className="max-w-[95%] sm:max-w-[85%] flex gap-4">
        <div className="flex-shrink-0 mt-1">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-indigo-400" />
          </div>
        </div>
        <div className="flex-1 min-w-0 bg-transparent">
          <div className="text-sm font-medium text-[var(--color-text-muted)] mb-1 flex items-center gap-2">
            <span>JAM</span>
            {message.intent && (
              <span className="px-2 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs uppercase tracking-wider font-semibold">
                {message.intent}
              </span>
            )}
          </div>
          
          <div className="text-[var(--color-text)]">
            {message.isError ? (
              <div className="flex items-start gap-3 p-4 rounded-xl border border-red-500/20 bg-red-500/5 text-red-400">
                <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <p className="text-sm">{message.errorMessage || "JAM couldn't complete that command."}</p>
              </div>
            ) : (
              <div className="p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]/50 space-y-4">
                <ResultRenderer result={message.result} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Recursive renderer for arbitrary structured result data
function ResultRenderer({ result }: { result?: Record<string, unknown> }) {
  if (!result || Object.keys(result).length === 0) {
    return <p className="text-[var(--color-text-muted)] italic text-sm">No result data returned.</p>;
  }

  return (
    <div className="space-y-4 text-sm w-full overflow-hidden">
      {Object.entries(result).map(([key, value]) => (
        <ResultItem key={key} label={key} value={value} />
      ))}
    </div>
  );
}

function ResultItem({ label, value }: { label: string; value: unknown }) {
  const formatLabel = (str: string) => {
    return str.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === 'boolean') {
    return (
      <div className="flex gap-2">
        <span className="text-[var(--color-text-muted)] font-medium w-1/3 flex-shrink-0">{formatLabel(label)}:</span>
        <span className="text-[var(--color-text)]">{value ? 'Yes' : 'No'}</span>
      </div>
    );
  }

  if (typeof value === 'string' || typeof value === 'number') {
    return (
      <div className="flex flex-col sm:flex-row sm:gap-2">
        <span className="text-[var(--color-text-muted)] font-medium sm:w-1/3 flex-shrink-0">{formatLabel(label)}:</span>
        <span className="text-[var(--color-text)] break-words">{value}</span>
      </div>
    );
  }

  if (Array.isArray(value)) {
    return (
      <div className="space-y-2">
        <span className="text-[var(--color-text-muted)] font-medium block">{formatLabel(label)}:</span>
        <ul className="list-disc list-inside space-y-1 pl-2 text-[var(--color-text)]">
          {value.map((item, idx) => (
            <li key={idx}>
              {typeof item === 'object' && item !== null ? (
                <div className="pl-4 mt-2 mb-2 border-l-2 border-[var(--color-border)]">
                  <ResultRenderer result={item as Record<string, unknown>} />
                </div>
              ) : (
                String(item)
              )}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (typeof value === 'object') {
    return (
      <div className="space-y-2">
        <span className="text-[var(--color-text-muted)] font-medium block">{formatLabel(label)}:</span>
        <div className="pl-4 border-l-2 border-[var(--color-border)]">
          <ResultRenderer result={value as Record<string, unknown>} />
        </div>
      </div>
    );
  }

  return null;
}
