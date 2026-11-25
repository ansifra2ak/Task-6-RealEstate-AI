# RealEstate AI — Service Level Objectives

## Proposed service targets

| Metric | Target |
|---|---|
| Service availability | 99% monthly |
| Prediction P95 latency | Below 1 second |
| Successful valid requests | At least 99% |
| Server error rate | Below 1% |
| Python application test coverage | Above 80% |
| High distribution drift alert | PSI ≥ 0.25 |

## Monitoring

Prometheus collects API request counts, response latency, errors and distribution drift metrics. Grafana provides operational dashboards and visualization.

## Incident management

Investigate failed health checks, elevated latency, server errors and distribution drift. Restore the previous validated model version if a model update causes a regression.

## Limitations

These are proposed service-level objectives, not measured production guarantees. Actual results are reported in the Phase 8 benchmark and monitoring reports. Long-term availability and production load capacity have not yet been established.