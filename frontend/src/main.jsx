import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import { SimulationProvider } from "./state/SimulationContext";

createRoot(document.getElementById("root")).render(
	<React.StrictMode>
		<SimulationProvider>
			<App />
		</SimulationProvider>
	</React.StrictMode>,
);
