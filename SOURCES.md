# Sources

本文件记录 `config.yaml` 中每类来源的用途和公开再分发批准状态。当前来源已于 2026-08-12 由项目维护者批准；批准表示本项目接受表中许可证与归属义务，不代表替上游重新授权。上游来源、许可证、用途或聚合内容变化时必须重新审查。

| Source family | Upstream | Use | License / obligations | Status |
| --- | --- | --- | --- | --- |
| Sukka Ruleset | [SukkaW/Surge](https://github.com/SukkaW/Surge) / [ruleset server](https://ruleset.skk.moe) | domestic, direct, AI provider/base, stream, Telegram, CDN, download, global, LAN and IP sets | AGPL-3.0；`china_ip` 特例为 CC BY-SA 2.0；保留来源与相应许可证 | Approved 2026-08-12 |
| MetaCubeX rule data | [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) | private, China IP, Cloudflare CN, AI-CN, GFW and Bytedance categories | GPL-3.0；保留来源与许可证 | Approved 2026-08-12 |
| DustinWin domain lists | [DustinWin/domain-list-custom](https://github.com/DustinWin/domain-list-custom) | China, Microsoft, Apple, AI provider/base and Google-CN categories | MIT；保留版权与许可声明 | Approved 2026-08-12 |
| blackmatrix7 Steam CN | [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) | Steam CN category | GPL-2.0，并保留仓库特别声明与来源链 | Approved 2026-08-12 |
| xndeye adblock list | [xndeye/adblock_list](https://github.com/xndeye/adblock_list) | reject domain category | 外层仓库 MIT；该产物聚合多个上游，保留上游清单链接并在聚合来源变化时重审 | Approved 2026-08-12 |
| ACL4SSR | [ACL4SSR/ACL4SSR](https://github.com/ACL4SSR/ACL4SSR) | supplemental AI provider/base category | CC BY-SA 4.0；保留署名、许可证及相同方式共享要求 | Approved 2026-08-12 |
| Local files | [`local/*.yaml`](LOCAL_RULES.md) | owner-maintained direct/proxy/Microsoft exceptions, general AI, coding agent and gateway subsets | 本 fork 维护；逐项依据与核对强度见 `LOCAL_RULES.md` | Approved 2026-08-12 |

AI provider/base 上游本身是宽口径 AI 列表，可能包含 coding agent 或 gateway 域名；`ai-coding-domain` 与 `ai-gateway-domain` 是额外维护的语义子集，因此 AI 子分类允许重叠。`ai-domain` 负责完整海外 AI 聚合，不以互斥为目标。`copilot.com` 与 `copilot.microsoft.com` 属于 Microsoft 通用 Copilot，只进入 `ai-domain`，不进入 `ai-coding-domain`。

新增来源在批准前必须保持 `redistributable: false`，不能通过 `legacy` 或格式转换绕过审查。当前批准失效或无法继续满足许可证义务时，应先撤销对应 source 的批准，再停止公开发布；构建器默认拒绝未显式批准的来源。
