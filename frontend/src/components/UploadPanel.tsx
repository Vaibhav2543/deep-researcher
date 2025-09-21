// frontend/src/components/UploadPanel.tsx
import React, { useRef, useState } from "react";
import client from "../api";
import { motion } from "framer-motion";

/** Helper to format bytes to human readable */
function humanFileSize(bytes: number, si = false) {
  const thresh = si ? 1000 : 1024;
  if (Math.abs(bytes) < thresh) {
    return bytes + " B";
  }
  const units = si
    ? ["kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    : ["KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"];
  let u = -1;
  do {
    bytes /= thresh;
    ++u;
  } while (Math.abs(bytes) >= thresh && u < units.length - 1);
  return bytes.toFixed(1) + " " + units[u];
}

export default function UploadPanel() {
  const [dragOver, setDragOver] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [fileInfo, setFileInfo] = useState<{ name: string; size: number } | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const onFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) {
      setStatus("No file selected.");
      return;
    }
    const file = files[0];
    setFileInfo({ name: file.name, size: file.size });
    setStatus(`Uploading ${file.name} ...`);
    setProgress(0);

    const fd = new FormData();
    fd.append("files", file);

    try {
      const res = await client.post("/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (evt: ProgressEvent) => {
          if (evt.lengthComputable) {
            const pct = Math.round((evt.loaded / evt.total) * 100);
            setProgress(pct);
          }
        },
      });

      const data = res.data;
      setProgress(100);

      if (data?.index_result?.status === "indexed") {
        setStatus(`Indexed: ${data.index_result.n_chunks} chunks`);
      } else if (data?.index_result?.status === "no_text_found") {
        setStatus("No text found — please run OCR or upload text.");
      } else {
        setStatus("Upload completed.");
      }
    } catch (err: any) {
      console.error("upload error", err);
      setStatus("Upload failed: " + (err?.response?.data || err?.message || "unknown"));
      setProgress(0);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    onFiles(e.dataTransfer.files);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => onFiles(e.target.files);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="max-w-3xl mx-auto"
    >
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`relative rounded-2xl p-6 border bg-white/60 backdrop-blur-md shadow-md transition-all ${
          dragOver ? "ring-2 ring-indigo-400 border-indigo-200" : "border-gray-100"
        }`}
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-slate-800">Upload Document</h3>
            <p className="mt-1 text-sm text-slate-500">
              Drag & drop a PDF or click to select. Documents are indexed for semantic search.
            </p>

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <input ref={inputRef} type="file" accept=".pdf,.txt" onChange={handleFileChange} className="hidden" />
              <button
                onClick={() => inputRef.current?.click()}
                className="px-4 py-2 bg-white/90 border border-gray-200 rounded-md shadow-sm hover:scale-[1.01] transition transform"
              >
                Choose file
              </button>

              {/* filename + size display */}
              {fileInfo ? (
                <div
                  className="ml-2 flex items-center gap-3"
                  title={`${fileInfo.name} • ${humanFileSize(fileInfo.size)}`}
                >
                  <div className="min-w-0">
                    {/* truncate so it never overflows; responsive max widths */}
                    <div className="text-sm font-medium text-slate-700 truncate max-w-[220px] sm:max-w-[420px]">
                      {fileInfo.name}
                    </div>
                    <div className="text-xs text-slate-400">{humanFileSize(fileInfo.size)}</div>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-slate-500">or drop here</div>
              )}
            </div>
          </div>

          <div className="w-full sm:w-48 text-right">
            <div className="text-xs text-slate-400">Status</div>
            <div className="mt-1 font-medium text-black">{status ?? "Awaiting upload"}</div>
          </div>
        </div>

        <div className="mt-4">
          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
            <motion.div
              className="h-2 bg-indigo-500"
              style={{ width: `${Math.max(0, Math.min(progress, 100))}%` }}
              initial={{ width: 0 }}
              animate={{ width: `${Math.max(0, Math.min(progress, 100))}%` }}
              transition={{ ease: "easeOut", duration: 0.4 }}
            />
          </div>
          <div className="text-xs text-slate-400 mt-2">{progress > 0 ? `${progress}%` : ""}</div>
        </div>
      </div>
    </motion.div>
  );
}
