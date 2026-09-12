import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const BACKEND_ORIGIN = "http://127.0.0.1:8000";

export default defineConfig({
	plugins: [react()],
	server: {
		proxy: {
			"/api": BACKEND_ORIGIN,
			"/health": BACKEND_ORIGIN,
			"/ws": { target: BACKEND_ORIGIN.replace("http", "ws"), ws: true },
		},
	},
});
