---
name: multi-model-review
description: 多模型候选评审管线:调度智谱 glm-5 / Claude opus-5(apiport 中转,真 CLI 通道)/ Gemini 3.1-pro-preview / Codex 四视角评审成长 artifact(教训/规则/GROWTH),结果只作 candidate_review_input,永不替代本地证据。适用:用户要求评审、周日仪式前自动评审、怀疑某条教训过度推广时。
whenToUse: 需要对 brain/ 下成长 artifact(lessons/rules/growth)做外部交叉评审时;或周日自进化仪式自动触发。
---

# 多模型候选评审(四视角)

## 环境现状(2026-08-16 锁定,改配置前先核对)

| 通道 | 模型 | 说明 |
| --- | --- | --- |
| 智谱 | glm-5 | 账号对 5.3/5.2/5.1 无权或空回复;降级链 glm-5→glm-5-turbo→glm-4.6 |
| Claude | opus-5 | apiport.cc.cd 中转;**只认真 Claude Code CLI 指纹**(claude -p 无头模式) |
| Gemini | gemini-3.1-pro-preview | 必须传 `max_completion_tokens`(max_tokens 会 30 token 就停) |
| Codex | Pro 默认 | codex exec,吃 Pro 额度,零 key |

- 密钥在 `~/Documents/TaijiOS Code/taiji/.env.local`(红线:只核对字段名,永不读值)
- 单轮成本:Claude ~$0.8(中转站起步计费);其余走免费/会员额度

## 入口

```bash
cd ~/xiaojiu-ops && python3 -u multi_model_review.py
```

- 零第三方依赖(urllib 标准库),任何 python3 可跑
- 输出:`brain/reviews/reviews-<时间戳>.jsonl`(每条含 verdict/strengths/risks/suggestions/cannot_claim)
- 账本:`provider-usage.jsonl`(in/out token + cost_usd 自动记)
- 失败留痕:`provider-keys.status`(401/403 自动记)

## 铁律(违背即放弃本轮结果)

1. provider 输出 = candidate_review_input,不是 truth;四家都说好 ≠ 成立(R12)
2. 评审对象只发 artifact 文本,绝不发送密钥、绝不发送整仓库
3. 每条建议逐条复核:采纳 → 实际改动 + LESSONS.jsonl 留痕;驳回 → 写驳回理由;两者都进周报
4. verdict ∈ {support, mixed, challenge} 只做定级参考

## 已知坑(不用重新踩)

- apiport `CLAUDE_RELAY_BASE` 不带 `/v1`(CLI 自己拼 `/v1/messages`)
- 智谱 403(1220 无权)= 换降级链下一模型;401 = 立刻停(key 失效)
- glm-5.2/5.1 空回复是账号权限隐性限制,不是 bug
- Gemini content 可能是 list(content parts),脚本已兼容
- 脚本 print 无缓冲,后台跑加 `-u`

## 收尾

1. 结果文件路径写进 `logs/receipts.jsonl`
2. 关键发现(如"抓到重复规则")进 LESSONS + 次日简报
3. 周日仪式已挂自动评审:weekly_digest.sh 先跑本轮再生成周报
