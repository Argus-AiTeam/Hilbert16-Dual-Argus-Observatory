# Blockers and Risks

| ID | Severity | Scope | Status | Description | Required action |
|---|---|---|---|---|---|
| R-001 | fundamental | scientific | open | The general problem is open; apparent completion is a high-risk overclaim. | Preserve the original goal gate and require independent verification. |
| R-002 | high | epistemic | controlled | Same backend/model can produce correlated errors. | Enforce route asymmetry and a blind phase; diversify models if authenticated. |
| R-003 | high | filesystem | mitigated | Logical isolation alone was insufficient. Each backend process now runs in Bubblewrap with host `/data` hidden and only its assigned worktree/mailboxes re-exposed. | Keep wrapper integrity checks active; stop on mount-policy drift. |
| R-004 | medium | operations | mitigating | Four-day intelligent supervision cannot self-awaken after the API session ends. | Combine live coordination with a deterministic health/dashboard monitor; use later operator sessions for mathematical intervention. |
