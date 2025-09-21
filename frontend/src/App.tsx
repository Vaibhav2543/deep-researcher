// frontend/src/App.tsx
import React from "react";
import UploadPanel from "./components/UploadPanel";
import QueryPanel from "./components/QueryPanel";
import { motion } from "framer-motion";

export default function App() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      <header className="py-6">
        <div className="max-w-5xl mx-auto px-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <motion.div initial={{ scale: 0.98 }} animate={{ scale: 1 }} transition={{ duration: 0.4 }}>
              <div className="w-12 h-12 rounded-lg bg-indigo-600 text-white flex items-center justify-center font-bold shadow">DR</div>
            </motion.div>
            <div>
              <h1 className="text-xl font-semibold text-slate-800">Deep Researcher Agent</h1>
              <div className="text-sm text-slate-500">Upload documents and ask natural language questions</div>
            </div>
          </div>
        </div>
      </header>

      <main className="py-6 px-4">
        <UploadPanel />
        <QueryPanel />
      </main>

      <footer className="py-8">
        <div className="max-w-5xl mx-auto text-sm text-slate-400 px-4">Built with ♥ — local Ollama + FastAPI</div>
      </footer>
    </div>
  );
}
