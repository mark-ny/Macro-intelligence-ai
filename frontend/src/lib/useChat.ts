"use client";

import { useCallback, useEffect, useState } from "react";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const STORAGE_KEY = "mia_chat_messages";
const MAX_HISTORY_MESSAGES = 12; // sent to the backend per request
const MAX_STORED_MESSAGES = 40; // kept in localStorage

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/**
 * One shared conversation, backed by localStorage, used by both the
 * floating ChatWidget (every page) and the full /assistant page — so
 * starting a conversation in one place and continuing it in the other
 * just works, instead of each keeping its own separate history.
 */
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) setMessages(JSON.parse(stored));
    } catch {
      // corrupted localStorage — start fresh rather than crash
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-MAX_STORED_MESSAGES)));
    } catch {
      // storage full/unavailable — conversation still works this session, just won't persist
    }
  }, [messages, hydrated]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      const next = [...messages, { role: "user" as const, content: trimmed }];
      setMessages(next);
      setError(null);
      setLoading(true);

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
        setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
      } catch {
        setError("Couldn't reach the assistant — check your connection.");
      } finally {
        setLoading(false);
      }
    },
    [messages, loading]
  );

  const clearConversation = useCallback(() => {
    setMessages([]);
    setError(null);
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }, []);

  return { messages, loading, error, sendMessage, clearConversation };
}
