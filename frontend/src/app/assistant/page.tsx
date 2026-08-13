"use client";

import { useEffect, useRef, useState } from "react";
import { Trash2 } from "lucide-react";

import { useChat } from "@/lib/useChat";

const SUGGESTIONS = [
  "What's the AI decision on gold right now?",
  "How has the system performed on Nasdaq?",
  "Is the yield curve inverted right now?",
  "Any big news releases coming up?",
  "What does premium/discount mean?",
];

export default function AssistantPage() {
  const { messages, loading, error, sendMessage, clearConversation } = useChat();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  }, [messages, loading]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input;
    setInput("");
    sendMessage(text);
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-medium text-ink">AI Assistant</h1>
          <p className="mt-1 text-sm text-muted">
            Ask about current signals, AI decisions, macro data, or system performance. Not financial advice.
            Continues the same conversation as the chat button on other pages.
          </p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearConversation}
            className="flex shrink-0 items-center gap-1.5 rounded border border-border px-3 py-1.5 text-xs text-muted hover:border-gold hover:text-ink"
          >
            <Trash2 size={14} aria-hidden="true" />
            Clear
          </button>
        )}
      </div>

      <div className="flex flex-1 flex-col overflow-hidden rounded border border-border bg-panel">
        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="space-y-3">
              <p className="text-sm text-muted">Try asking:</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => sendMessage(s)}
                    className="rounded-full border border-border px-3 py-1.5 text-xs text-muted hover:border-gold hover:text-ink"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[75%] rounded px-3 py-2 text-sm ${
                  m.role === "user" ? "bg-gold/10 text-ink" : "bg-bg text-ink"
                }`}
              >
                {m.content}
              </div>
            </div>
          ))}

          {loading && <div className="text-xs text-muted">Thinking…</div>}
          {error && <div className="text-xs text-negative">{error}</div>}
        </div>

        <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-border p-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question…"
            disabled={loading}
            className="min-w-0 flex-1 rounded border border-border bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-gold disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded bg-gold px-4 py-2 text-sm font-medium text-bg transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
