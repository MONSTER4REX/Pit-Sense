import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

/*
 * The dev server proxies the API and the tick stream to the backend, so the app
 * is only ever reached on one origin and there is no CORS setup to get wrong.
 *
 * The target is overridable for the case where the default port is already taken
 * or the backend is running elsewhere:
 *
 *     PITSENSE_API_ORIGIN=http://127.0.0.1:8001 npm run dev
 */
const BACKEND_ORIGIN = process.env.PITSENSE_API_ORIGIN ?? "http://127.0.0.1:8000";

export default defineConfig({
	plugins: [react(), tailwindcss()],
	server: {
		proxy: {
			"/api": BACKEND_ORIGIN,
			"/health": BACKEND_ORIGIN,
			"/ws": { target: BACKEND_ORIGIN.replace(/^http/, "ws"), ws: true },
		},
	},
});
