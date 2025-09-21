// frontend/src/components/Header.tsx
import React from "react";
import { motion } from "framer-motion";

export default function Header() {
  return (
    <header className="py-6 border-b border-slate-800">
      <div className="container mx-auto px-6 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <motion.div
            initial={{ scale: 0.9, rotate: -10 }}
            animate={{ scale: 1, rotate: 0 }}
            className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-accent shadow-soft flex items-center justify-center"
          >
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none"><path d="M3 7v10a2 2 0 0 0 2 2h4" stroke="white" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/><path d="M21 7v10a2 2 0 0 1-2 2h-4" stroke="white" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </motion.div>
          <div>
            <h1 className="text-xl font-semibold">Deep Researcher</h1>
            <p className="text-sm text-slate-400">Upload docs • ask questions • export reports</p>
          </div>
        </div>
        <div className="text-right text-sm text-slate-400">Local mode • Ollama</div>
      </div>
    </header>
  );
}
