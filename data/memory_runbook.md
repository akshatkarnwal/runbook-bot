# High Memory Alert Runbook

## Detection
Alert fires when memory exceeds 90% for 10+ minutes. PagerDuty severity P2.

## Investigation
1. Run: free -h to check memory usage
2. Check for memory leaks: ps aux --sort=-%mem | head -10
3. Check DNIF pipeline buffer sizes in config
4. Review recent ingestion volume spikes

## Resolution
- Reduce pipeline buffer size in DNIF config
- Restart memory-heavy service: systemctl restart dnif-pipeline
- Clear log buffers if safe to do so
- Scale horizontally if persistent

## Escalation
Contact platform-team@company.com with memory dump if OOM kills occurring.
