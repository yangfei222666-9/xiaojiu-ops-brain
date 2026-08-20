# 小九值班 · 四层文件记忆法(公开可验部分)

> 给 AI agent 装一套以「可审计」为第一优先的记忆 —— 这是它的全部**公开证据**。我们不宣称它永不失败,只承诺失败可被查见。
> 原则:无证据不写教训;说"做完了"要有可查验的 receipt;拿不准的写"不能宣称"。

## 四层结构

| 层 | 文件 | 作用 | 公开状态 |
|---|---|---|---|
| 1 | MEMORY.md | 我是谁、接管范围、状态快照 | 🔒 含个人身份信息,不上传(边界本身就是纪律) |
| 2 | `LESSONS.jsonl` | 教训库:每条强制带 evidence 字段(目标=报错原文/复现命令,个别早期条目为叙述,持续补强中) | ✅ 本仓库 |
| 3 | `rules/` | 操作规则 R1-R26:每条带授权来源与日期 | ✅ 本仓库(含 archived 墓碑) |
| 4 | `skills/` + `preset/` | 技能与预设宪法 | ✅ 本仓库 |

## 为什么不用向量库
刻意走反方向:不向量化、不自动捕捉会话,只维护纯文本文件 —— 换来的是每条记忆都能被审计;新会话恢复与三副本容灾为实测能力,恢复耗时未做正式计时演练。文件层的简单,换可审计、可交接。

## 配套证据
- 成长计分板:`GROWTH.md`(周度审计,五项指标,外部验证判定标准含 0.5 边界档与 L30-L30 分级)
- 外部验证台账:`external-validation.jsonl`(触点变化 + 判定 + 降级链)
- 交互演示:https://taiji-evidence-gate.netlify.app (静态演示,非运行时证据)
- 相关技能仓库:[memory-auditor](https://github.com/yangfei222666-9/memory-auditor) · [dsh-skill-multi-model-review](https://github.com/yangfei222666-9/dsh-skill-multi-model-review)

## 五步可验(不用信我)
1. `python3 -c "import json;[json.loads(l) for l in open('LESSONS.jsonl')]"` → 22 条,每条有 evidence
2. `grep -c "^R" rules/operator-rules-v1.md` → R1-R26 编号连续
3. `rules/archived/README.md` → 被取代条款的墓碑
4. GROWTH.md「外部验证记录」→ 判定 + 翻转条件 + 四模型评审降级链
5. 发现任何一条"无证据教训"或"过度宣称" → 开 issue,按规则挑得最狠的三条会写进教训库并附上你的 ID

## 同步方式
每日由 launchd 任务(com.xiaojiu.brain-publish,00:30)从值班工作区自动同步;手工触发:`bash ~/xiaojiu-ops/tools/brain_publish.sh`
