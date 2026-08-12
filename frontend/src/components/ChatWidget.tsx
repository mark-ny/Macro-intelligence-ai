"use client";

import { useRef, useState } from "react";
import { MessageCircle, Send, X } from "lucide-react";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const MAX_HISTORY_MESSAGES = 12; // mirrors the backend's own trim — keeps the request body small

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

const SUGGESTIONS = [
  "What's the AI decision on gold right now?",
  "Any big news releases coming up?",
  "What does premium/discount mean?",
];

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  function scrollToBottom() {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const next = [...messages, { role: "user" as const, content: trimmed }];
    setMessages(next);
    setInput("");
    setError(null);
    setLoading(true);
    scrollToBottom();

    try {
      const res = await fetch(`${BASE_URL}/api/chat/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: next.slice(-MAX_HISTORY_MESSAGES) }),
      });

      if (res.status === 429) {
        setError("Too many messages — try again in a bit.");
        return;
      }
      if (!res.ok) {
        setError("The assistant hit a problem. Try again in a moment.");
        return;
      }

      const data = await res.json();
      setMessages([...next, { role: "assistant", content: data.reply }]);
    } catch {
      setError("Couldn't reach the assistant — check your connection.");
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  }

  return (
    <>
      {open && (
        <div className="fixed bottom-20 right-4 z-50 flex h-[28rem] w-[calc(100vw-2rem)] max-w-sm flex-col rounded border border-border bg-panel shadow-xl sm:right-6">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <span className="font-display text-sm font-medium text-ink">AI Assistant</span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close chat"
              className="text-muted hover:text-ink"
            >
              <X size={18} aria-hidden="true" />
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {messages.length === 0 && (
              <div className="space-y-3">
                <p className="text-sm text-muted">
                  Ask about current signals, AI decisions, or upcoming releases. Not financial advice.
                </p>
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
                  className={`max-w-[85%] rounded px-3 py-2 text-sm ${
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

          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage(input);
            }}
            className="flex items-center gap-2 border-t border-border p-3"
          >
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
              aria-label="Send message"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-gold text-bg disabled:opacity-50"
            >
              <Send size={16} aria-hidden="true" />
            </button>
          </form>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-label={open ? "Close AI assistant" : "Open AI assistant"}
        className="fixed bottom-4 right-4 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-gold text-bg shadow-lg transition-transform hover:scale-105 sm:right-6"
      >
        {open ? <X size={22} aria-hidden="true" /> : <MessageCircle size={22} aria-hidden="true" />}
      </button>
    </>
  );
}
