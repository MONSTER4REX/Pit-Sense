/*
 * Shared primitives - and only primitives.
 *
 * PRD section 7 allows Race Analysis and Simulation Lab to share buttons, cards,
 * typography, and icons, and nothing else. Everything here is presentational: it
 * takes values and renders them. None of it fetches, holds product state, or
 * knows which of the two products is rendering it, so the two pages can never
 * end up sharing behaviour just because they share a look.
 */

export function Panel({ label, title, tone = "neutral", className = "", children }) {
	return (
		<article className={`panel tone-${tone} ${className}`.trim()}>
			{label && <div className="panel-label">{label}</div>}
			{title && <h2 className="panel-title">{title}</h2>}
			{children}
		</article>
	);
}

export function StatusBadge({ tone = "neutral", children }) {
	return <span className={`status-badge badge-${tone}`}>{children}</span>;
}

export function Meter({ label, value, displayValue, tone = "neutral", unavailable = false }) {
	const width = unavailable ? 0 : Math.min(100, Math.max(0, value * 100));
	return (
		<div className={`meter ${unavailable ? "meter-unavailable" : ""}`.trim()}>
			<div className="meter-head">
				<span>{label}</span>
				<strong>{unavailable ? "not measured" : displayValue}</strong>
			</div>
			<div className="meter-track">
				<span className={`meter-fill fill-${tone}`} style={{ width: `${width}%` }} />
			</div>
		</div>
	);
}

export function MetricRow({ label, value, hint }) {
	return (
		<div className="metric-row">
			<span>
				{label}
				{hint && <em className="metric-hint" title={hint}>?</em>}
			</span>
			<strong>{value}</strong>
		</div>
	);
}

export function Button({ variant = "default", ...props }) {
	return <button type="button" className={`button button-${variant}`} {...props} />;
}

export function Note({ tone = "muted", children }) {
	return <p className={`note note-${tone}`}>{children}</p>;
}

export function EmptyState({ title, children }) {
	return (
		<div className="empty-state">
			<strong>{title}</strong>
			{children}
		</div>
	);
}
