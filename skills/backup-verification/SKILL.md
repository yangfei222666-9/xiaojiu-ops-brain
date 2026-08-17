---
name: backup-verification
description: 备份验证技能:核验值班系统三副本(T7 本地 / iCloud 异地 / backup-mac 第三物理副本)的真实新鲜度,用哨兵哈希比对而非"看日志说完成";发现假完成时执行补同步并留证。适用:每日巡检备份段异常、怀疑备份没真跑、或需要向用户报告容灾状态时。
whenToUse: 备份告警、周日仪式容灾自检、或用户询问"数据安全吗"时。
---

# 备份验证(三副本 + 哨兵哈希)

## 铁律

- 备份脚本打印「完成」≠ 真完成:只信退出码与哈希(教训 L16:曾发生日志全绿但三副本停摆)
- 验证用哨兵:以 `logs/receipts.jsonl` 尾 2000 字节的 sha 与三副本逐一比对

## 验证清单(逐项执行)

1. **三副本文件级时间**:T7 `/Volumes/T7/xiaojiu-ops-backups/xiaojiu-ops/`、iCloud `~/Library/Mobile Documents/com~apple~CloudDocs/Desktop/T7_taijios_archive/xiaojiu-ops/`、backup-mac `~/xiaojiu-offsite/ops/` 下的 receipts.jsonl
   - 注意 rsync -a 保留源 mtime → 看「内容哈希」不看目录时间
2. **哨兵哈希比对**:
   ```bash
   SENT=$(tail -c 2000 ~/xiaojiu-ops/logs/receipts.jsonl | shasum | cut -c1-12)
   tail -c 2000 "/Volumes/T7/xiaojiu-ops-backups/xiaojiu-ops/logs/receipts.jsonl" | shasum | cut -c1-12  # 应=SENT
   ```
3. **第三副本连通性**:`ssh -o BatchMode=yes -o ConnectTimeout=6 taiji-backup-mac "tail -c 2000 ~/xiaojiu-offsite/ops/logs/receipts.jsonl | shasum"`(离线时交给 handoff-hourly 自动补)
4. **失败处置**:任一不符 → 立即跑 `~/xiaojiu-ops/backup_daily.sh`(v2 自带退出码校验+哨兵)→ 检查 `logs/backup-failures.jsonl` 新增条目 → 收尾写 receipt

## 恢复演练(月一次,周日仪式可做)

- 从 T7 副本恢复单文件到 /tmp 验证可读性(勿覆盖本机原件)
- 从 backup-mac 拉取 brain/MEMORY.md 验证 SSH 通道与数据完整性

## 已知边界

- dsh-home 段备份受目录权限限制(Operation not permitted 告警已知,不影响三副本主体)
- 本机 zsh ≥5.9.2(2026-08-16 已升级)后 .zsh_history 不再有静默截断风险
