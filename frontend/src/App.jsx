import { useState } from "react";

import RaceAnalysisPage from "./analysis/RaceAnalysisPage";
import { RaceAnalysisProvider } from "./analysis/RaceAnalysisProvider";
import SimulationLabPage from "./lab/SimulationLabPage";
import { SimulationLabProvider } from "./lab/SimulationLabProvider";

/*
 * Two products, one shell (PRD section 7).
 *
 * Only one product is mounted at a time, each inside its own provider. That is
 * the structural guarantee behind PRD 2.1: there is no shared stateful
 * component and no shared state object, so Simulation Lab controls cannot leak
 * into Race Analysis and projected values cannot appear on a page that only ever
 * shows the real race.
 */
const PRODUCTS = { ANALYSIS: "analysis", LAB: "lab" };

export default function App() {
	const [product, setProduct] = useState(PRODUCTS.ANALYSIS);

	if (product === PRODUCTS.LAB) {
		return (
			<SimulationLabProvider>
				<SimulationLabPage onOpenRaceAnalysis={() => setProduct(PRODUCTS.ANALYSIS)} />
			</SimulationLabProvider>
		);
	}

	return (
		<RaceAnalysisProvider>
			<RaceAnalysisPage onOpenSimulationLab={() => setProduct(PRODUCTS.LAB)} />
		</RaceAnalysisProvider>
	);
}
