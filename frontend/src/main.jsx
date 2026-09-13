import React from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./styles.css";

/* Each product mounts its own provider inside App, so there is no shared
 * provider at the root (PRD 2.1). */
createRoot(document.getElementById("root")).render(
	<React.StrictMode>
		<App />
	</React.StrictMode>,
);
