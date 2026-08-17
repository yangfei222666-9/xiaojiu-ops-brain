---
name: night-shift
description: 夜班执行技能:按每晚 22:00 自动生成的菜单(brain/night-shift/agenda-*.md)依次执行学习与标定任务——灰色样本标定(月例)、arXiv 深读 2-3 篇、OSS 精读 3-5 个、记忆层对照研究(周例);每项留 receipt,收尾写夜班日志并补记 GROWTH。适用:用户说「夜班」、会话收到夜班提醒、或早报显示昨夜漏班需要补。
whenToUse: 用户启动夜班时,或巡检显示昨夜夜班未执行需要补课时。
---

# 夜班(Night Shift)

目标:让值班 agent 每天在空闲时段(半价)持续学习不掉队,同时完成评审器标定等月例维护。

## 流程

1. **读菜单**:`~/xiaojiu-ops/brain/night-shift/agenda-$(date +%Y-%m-%d).md`(22:00 由 night_prep.sh 自动生成;缺失时现场生成:先跑 fetch_intel.sh 拉新,再列当日 arXiv/HN 候选项)
2. **按序执行**:
   - 灰样本标定(每月 1 次,日期含 1/11/21 时做):把 1 个新灰样本送四视角评审,4/4 mixed 为健康;结果写 GROWTH 标定区
   - arXiv 深读 2-3 篇:从当日菜单选与证据门/agent 可靠性/记忆相关的,写 intel-lessons.md(#N+)
   - OSS 精读 3-5 个:从当日候选仓库选,写 oss-study-log.md
   - 记忆层对照研究(每周日):deepDDW/rembric 等竞品的 brief/full 结构对照,写研究笔记
3. **纪律**:每项必须 receipt;深读只发内容不发密钥;22:00-08:00 全空闲段,可用全通道但优先 glm/gemini/codex(Claude 走中转有起步费,标注级任务才用)
4. **收尾**:写 `brain/night-shift/log-YYYY-MM-DD.md`(执行清单+失败段+消耗估算);GROWTH 证据栏补记;回执入账
5. **漏班**:若当晚未执行,次晨 08:00 巡检自动记"夜班漏 N 次",用户说「补夜班」时合并执行

## 健康线

- 每次夜班 ≥2 篇论文 + ≥3 仓库 为达标;连续 3 晚不达标记一条 LESSONS(候选不足则如实记 0 并说明)
