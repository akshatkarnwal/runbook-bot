# Disk Space Alert Runbook

## Detection
Alert fires when disk usage exceeds 80%. PagerDuty severity P3.

## Investigation
1. Check disk usage: df -h
2. Find large files: du -sh /* 2>/dev/null | sort -hr | head -20
3. Check DNIF log retention settings
4. Check if log rotation is running

## Resolution
- Run log rotation manually: logrotate -f /etc/logrotate.conf
- Archive old DNIF indices older than retention period
- Delete tmp files: find /tmp -mtime +7 -delete
- Increase disk if persistent

## Escalation
Contact infra-team@company.com if disk full and cannot free space.
