<div align="center">

# ∞ Hilbert XVI · Dual-Argus Observatory

### Two isolated research processes, one evidence-first coordination layer

[![Visibility](https://img.shields.io/badge/repository-private-6f42c1)](#)
[![Argus A](https://img.shields.io/badge/Argus_A-initializing-64748b)](status/argus-a.md)
[![Argus B](https://img.shields.io/badge/Argus_B-initializing-64748b)](status/argus-b.md)
[![Coordination](https://img.shields.io/badge/coordination-isolated-2563eb)](status/coordinator.md)
[![Scientific claim](https://img.shields.io/badge/full_solution-not_claimed-f59e0b)](#scientific-integrity)

**[中文仪表板](README.zh-CN.md) · [English dashboard](README.en.md)**

</div>

---

## Live mission / 当前任务

Investigate the maximum number and relative configurations of limit cycles of planar polynomial vector fields of degree $n$—Hilbert's sixteenth problem, Part II—through two isolated Argus research campaigns.

通过两个彼此隔离的 Argus 研究进程，研究平面 $n$ 次多项式向量场极限环的最大数目与相对配置，即 Hilbert 第十六问题第二部分。

```mermaid
flowchart LR
    P[Immutable problem contract] --> A[Argus A<br/>theory / upper constraints]
    P --> B[Argus B<br/>construction / lower bounds]
    A -->|curated question| C[Coordinator broker]
    B -->|curated question| C
    C -->|one question, one answer| A
    C -->|one question, one answer| B
    A --> R[Evidence gate]
    B --> R
    R --> F[Single-writer final synthesis]
```

## Isolation contract

| Surface | Argus A | Argus B | Coordinator |
|---|---:|---:|---:|
| `math1/` | read/write | **forbidden** | audit |
| `math2/` | **forbidden** | read/write | audit |
| `talk/A-*` | scoped mailbox | no direct writes | broker |
| `talk/B-*` | no direct writes | scoped mailbox | broker |
| this repository | **forbidden** | **forbidden** | sole writer |

## Scientific integrity

This repository distinguishes **complete solution**, **verified partial result**, **computational evidence**, **known theorem**, **conjecture**, and **failed route**. A larger finite search, a plausible argument, or agreement between agents is never reported as a proof of a universal claim.

> This repository is an observability record, not a communication channel between the two research processes.

_Last dashboard initialization: 2026-08-12 14:08 UTC._
