// frontend/src/api.ts
import axios from "axios";
const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const client = axios.create({
  baseURL: API_URL,
  timeout: 600000, // 10 minutes
});
export default client;
