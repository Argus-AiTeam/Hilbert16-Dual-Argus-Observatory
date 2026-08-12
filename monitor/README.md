# Deterministic Monitor

`monitor.py` polls the two Argus durable state directories every five minutes. It:

- verifies both daemon identities and immutable isolation controls;
- renders `status/live.md` and `status/runtime.json`;
- records milestone event metadata without copying solution content;
- commits and pushes milestones immediately;
- publishes a routine checkpoint every three hours when state changed;
- never invokes a model and never brokers A/B mathematical messages.

Runtime PID, offsets, logs, and stop controls live outside Git under `talk/monitor/runtime/`.
