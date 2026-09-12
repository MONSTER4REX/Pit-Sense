const TIER_LABEL = { safe: "SAFE", marginal: "MARGINAL", optimal: "OPTIMAL", critical: "CRITICAL" };

export default function UndercutRiskTier({ tier }) {
	if (!tier) return null;
	return <span className={`risk-tier risk-tier-${tier}`}>{TIER_LABEL[tier] ?? tier.toUpperCase()}</span>;
}
