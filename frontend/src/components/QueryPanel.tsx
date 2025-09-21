// frontend/src/components/QueryPanel.tsx
import React, { useState, useRef } from "react";
import client from "../api";
import { motion } from "framer-motion";
import type { Source } from "../types";

type JobStatus = "pending" | "running" | "done" | "failed" | "unknown";

export default function QueryPanel() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [error, setError] = useState<string | null>(null);
  const stopPollingRef = useRef(false);

  // Poll job results with exponential backoff until done/failed or timeout
  const pollJob = async (id: string, onProgress?: (status: JobStatus) => void, timeoutMs = 10 * 60 * 1000) => {
    const start = Date.now();
    let delay = 500; // start at 0.5s
    stopPollingRef.current = false;

    while (!stopPollingRef.current && Date.now() - start < timeoutMs) {
      try {
        const res = await client.get(`/results/${id}`);
        const payload = res.data;
        const status: JobStatus = (payload.status as JobStatus) || "unknown";
        onProgress && onProgress(status);

        if (status === "done") {
          return payload;
        }
        if (status === "failed") {
          throw new Error(payload.error || "Job failed");
        }
      } catch (err: any) {
        // If it's a transient network error, continue and backoff
        console.error("poll error", err?.message || err);
      }

      // wait
      await new Promise((r) => setTimeout(r, delay));
      delay = Math.min(5000, Math.round(delay * 1.5)); // exponential backoff cap 5s
    }

    throw new Error("Polling timed out");
  };

  // Helper to start job with retries (use longer timeout here)
  const startJobWithRetries = async (formBody: string, maxAttempts = 3) => {
    let attempt = 0;
    let lastErr: any = null;
    while (attempt < maxAttempts) {
      attempt += 1;
      try {
        // increase timeout to 60s here (start can occasionally be slow)
        const res = await client.post("/query", formBody, {
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          timeout: 60000, // 60s start timeout
        });
        return res.data;
      } catch (err: any) {
        lastErr = err;
        console.warn(`startJob attempt ${attempt} failed:`, err?.message || err);
        // small backoff between attempts
        await new Promise((r) => setTimeout(r, 800 * attempt));
      }
    }
    throw lastErr;
  };

  const ask = async () => {
    if (!q.trim()) {
      setError("Please write a question first.");
      return;
    }

    setLoading(true);
    setError(null);
    setAnswer(null);
    setSources([]);
    setJobStatus("pending");
    setJobId(null);

    try {
      // start job (with retries)
      const params = new URLSearchParams();
      params.append("q", q.trim());
      params.append("top_k", "3");
      const formBody = params.toString();

      const startResp = await startJobWithRetries(formBody, 3);
      const jid = startResp?.job_id;
      if (!jid) throw new Error("No job id returned from server");
      setJobId(jid);
      setJobStatus("pending");

      // poll
      const result = await pollJob(
        jid,
        (status) => {
          setJobStatus(status);
        },
        10 * 60 * 1000 // 10 minutes
      );

      // handle final result
      if (result && result.status === "done") {
        const final = result.result || result;
        setAnswer(final.answer || null);
        setSources(final.sources || []);
        setJobStatus("done");
      } else if (result && result.status === "failed") {
        setError(result.error || "Job failed");
        setJobStatus("failed");
      } else {
        setError("Unexpected job result");
        setJobStatus("failed");
      }
    } catch (err: any) {
      console.error("ask error", err);
      // Improve user-facing message for timeout / connection issues
      if (err?.code === "ECONNABORTED" || (err?.message && err.message.toLowerCase().includes("timeout"))) {
        setError("Request timed out while starting the job. Try again or check the backend (uvicorn/Ollama).");
      } else if (err?.response?.status === 502 || err?.response?.status === 503) {
        setError("Backend temporarily unavailable (502/503). Try again in a moment.");
      } else {
        setError(err?.response?.data || err?.message || "Unknown error");
      }
      setJobStatus("failed");
    } finally {
      setLoading(false);
      stopPollingRef.current = true;
    }
  };

  const cancel = () => {
    // stop polling (does not cancel server job)
    stopPollingRef.current = true;
    setLoading(false);
    setJobStatus(null);
    setJobId(null);
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="max-w-3xl mx-auto mt-6">
      <div className="rounded-2xl p-6 bg-white/60 backdrop-blur-md border border-gray-100 shadow-sm">
        <textarea
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Ask a question about the uploaded documents..."
          rows={3}
          className="w-full p-3 rounded-md border-gray-200 bg-white/70 text-black focus:outline-none focus:ring-2 focus:ring-indigo-200 resize-none"
        />

        <div className="flex items-center gap-3 mt-3">
          <button
            onClick={ask}
            disabled={loading}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md shadow hover:scale-[1.01] transition transform disabled:opacity-60"
          >
            {loading ? "Submitting..." : "Ask"}
          </button>

          <button onClick={() => { setQ(""); setAnswer(null); setSources([]); setError(null); }} className="px-4 py-2 border rounded-md">
            Reset
          </button>

          {loading && (
            <button onClick={cancel} className="px-3 py-1 text-sm border rounded-md hover:bg-gray-50">
              Cancel
            </button>
          )}

          <div className="ml-auto text-sm text-slate-500">
            {jobStatus ? <span className="font-medium text-slate-700">Status: {jobStatus}</span> : null}
            {jobId ? <span className="ml-3 text-xs text-slate-400">Job: {jobId.slice(0, 8)}...</span> : null}
          </div>
        </div>

        <div className="mt-6 space-y-4">
          {error && <div className="p-3 bg-red-50 text-red-700 rounded">{String(error)}</div>}

          {answer && (
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
              <div className="p-4 bg-white rounded-lg shadow">
                <h4 className="text-sm font-semibold text-slate-700 mb-2">Answer</h4>
                <div className="text-black whitespace-pre-wrap">{answer}</div>
              </div>
            </motion.div>
          )}

          {sources.length > 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.05 }}>
              <h5 className="text-sm text-slate-500 font-medium mb-2">Sources</h5>
              <div className="grid grid-cols-1 gap-3">
                {sources.map((s, i) => (
                  <motion.div key={i} className="p-3 bg-white rounded-lg border" whileHover={{ scale: 1.01 }}>
                    <div className="flex justify-between text-xs text-slate-400 mb-2">
                      <div className="font-medium text-slate-600">{s.source}</div>
                      <div>dist: {Number(s.dist).toFixed(3)}</div>
                    </div>
                    <div className="text-sm text-black whitespace-pre-wrap">{s.text}</div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
