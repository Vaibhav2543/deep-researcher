// frontend/src/components/ChatBubble.tsx
import React from "react";
import { motion } from "framer-motion";

export default function ChatBubble({ text, from }: { text: string; from: "user" | "bot" }) {
  const isUser = from === "user";
  return (
    <motion.div initial={{ opacity: 0, x: isUser ? 20 : -20 }} animate={{ opacity: 1, x: 0 }} className={`mb-3 flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[78%] p-3 rounded-lg ${isUser ? "bg-gradient-to-r from-primary/80 to-accent/80 text-white" : "bg-slate-800 text-slate-200"}`}>
        <div className="whitespace-pre-wrap">{text}</div>
      </div>
    </motion.div>
  );
}
