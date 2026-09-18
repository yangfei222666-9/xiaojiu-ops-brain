---
name: backup-verification
description: 备份验证技能:核验值班系统三副本(T7 本地 / iCloud 异地 / backup-mac 第三物理副本)的真实新鲜度,用哨兵哈希比对而非"看日志说完成";发现假完成时执行补同步并留证。适用:每日巡检备份段异常、怀疑备份没真跑、或需要向用户报告容灾状态时。
whenToUse: 备份告警、周日仪式容灾自检、或用户询问"数据安全吗"时。
---

# 备份验证(三副本 + 哨兵哈希)

## 铁律

- 备份脚本打印「完成」≠ 真完成:只信退出码与哈希(教训 L16:曾发生日志全绿但三副本停摆)
- 验证用哨兵:副本必须是源 `logs/receipts.jsonl` 的**字节前缀**(见下方命令),不要比"尾部 2000 字节哈希"

## 验证清单(逐项执行)

1. **三副本文件级时间**:T7 `/Volumes/T7/xiaojiu-ops-backups/xiaojiu-ops/`、iCloud `~/Library/Mobile Documents/com~apple~CloudDocs/Desktop/T7_taijios_archive/xiaojiu-ops/`、backup-mac `~/xiaojiu-offsite/ops/` 下的 receipts.jsonl
   - 注意 rsync -a 保留源 mtime → 看「内容哈希」不看目录时间
2. **哨兵判据 = 前缀一致,不是尾哈希相等**
   - **为什么不能用尾哈希**:账本只追加,备份跑完后当晚还会继续写入。拿"副本此刻的尾 2000 B"去比"源此刻的尾 2000 B",只要中间又落了一条 receipt 就必然不等 —— 2026-09-18 实测两副本各 1631 行、均为源的 sha256 精确前缀(数据无损),却被旧判据报成「账本尾行哈希不一致」。旧判据同时把"文件缺失"也报成"哈希不一致",把两类问题混成一句。
   - **正确做法**:取副本字节数 N,比对源的前 N 字节与副本全文。
   ```bash
   SRC=~/xiaojiu-ops/logs/receipts.jsonl
   CP="/Volumes/T7/xiaojiu-ops-backups/xiaojiu-ops/logs/receipts.jsonl"
   N=$(wc -c < "$CP" | tr -d ' ')
   head -c "$N" "$SRC" | shasum   # 应等于 ↓
   shasum < "$CP"
   ```
   - 副本**大于**源 → ❌(源被回滚或截断);两者哈希任一算不出来 → ❌ **按失败计,不得当作通过**(空的空会相等,是本判据最容易踩的假绿)
   - `backup_daily.sh` 已内置该判据(`sentinel_prefix_rc`/`sentinel_report`),日常直接看它的输出即可;上面的命令用于手工复核
3. **第三副本连通性**:`ssh -o BatchMode=yes -o ConnectTimeout=6 taiji-backup-mac 'f=$HOME/xiaojiu-offsite/ops/logs/receipts.jsonl; wc -c <"$f"; shasum <"$f"'`(离线时交给 handoff-hourly 自动补;不可达按失败计并留痕)
4. **失败处置**:任一不符 → 看 `backup_daily.sh` 报的是"副本缺失/比源大/真分歧/校验工具失败"哪一种(四种原因已分开报,不再统一说"不一致")→ 检查 `logs/backup-failures.jsonl` 新增条目 → 收尾写 receipt

> **2026-09-18 注**:本技能原先教的就是"尾 2000 字节比对",那正是被证伪的判据;已按 `backup_daily.sh` 的新实现改写。旧写法会制造 nightly 误报,并诱导"再跑一次备份"这种无效处置。

## 恢复演练(月一次,周日仪式可做)

- 从 T7 副本恢复单文件到 /tmp 验证可读性(勿覆盖本机原件)
- 从 backup-mac 拉取 brain/MEMORY.md 验证 SSH 通道与数据完整性

## 已知边界

- dsh-home 段备份受目录权限限制(Operation not permitted 告警已知,不影响三副本主体)
- 本机 zsh ≥5.9.2(2026-08-16 已升级)后 .zsh_history 不再有静默截断风险
