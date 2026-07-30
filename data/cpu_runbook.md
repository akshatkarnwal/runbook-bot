# High CPU Alert Runbook

## Detection
Alert fires when CPU exceeds 85% for 5+ minutes. PagerDuty severity P2.

## Investigation
1. SSH into affected node
2. Run htop to identify CPU-heavy process
3. Check worker logs: journalctl -u dnif-worker -n 100
4. Look for regex backtracking in active extraction rules

## Resolution
- Pause data source from DNIF console to stop ingestion
- Restart worker: systemctl restart dnif-worker
- Monitor for 5 minutes after restart

## Escalation
Contact platform-team@company.com if unresolved after 30 minutes.
Slack: #platform-oncall
