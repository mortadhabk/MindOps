import clsx from "clsx";
import { motion } from "framer-motion";

import type { ChatMessage } from "../hooks/useChat";

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const showTypingDots = message.pending && !message.text;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={clsx("flex", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={clsx(
          "max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm",
          isUser
            ? "rounded-br-md bg-gradient-to-br from-indigo-500 to-indigo-600 text-white"
            : "rounded-bl-md border border-white/10 bg-white/[0.04] text-slate-100",
        )}
      >
        {showTypingDots ? <TypingDots /> : message.text}
        {message.pending && !showTypingDots && (
          <span className="ml-0.5 inline-block h-3.5 w-[2px] animate-pulse bg-indigo-300 align-middle" />
        )}
      </div>
    </motion.div>
  );
}

function TypingDots() {
  return (
    <span className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400"
          style={{ animationDelay: `${i * 0.12}s` }}
        />
      ))}
    </span>
  );
}
