export default function ForkTransition({ forkLap, action }) {
	return (
		<article className="fork-transition data-projected">
			<div className="fork-transition-line">HISTORICAL RACE ENDS HERE AS TRUTH</div>
			<div className="fork-transition-action">→ {action} ACCEPTED AT LAP {forkLap} →</div>
			<div className="fork-transition-line">HISTORICAL REFERENCE + PROJECTED COUNTERFACTUAL BRANCHES</div>
		</article>
	);
}
