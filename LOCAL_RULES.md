# Local rule provenance

本文件逐项记录 `local/*.yaml` 中人工维护规则的用途和依据，核对日期为 2026-08-12。

依据强度分为：

- `官方端点`：官方网络、接入或 API 文档明确给出该主机。
- `官方域名`：产品官网或官方文档使用同一注册域名；`DOMAIN-SUFFIX` 是本项目为覆盖产品子域作出的策略选择。
- `运行观察`：客户端实际使用或历史规则观察，尚无公开官方端点清单；此类规则需要在产品网络行为变化时优先复核。
- `维护者例外`：本 fork 所有者明确指定的本地策略，不主张为公共产品端点。

这些条目是分类依据，不是完整 firewall allowlist。

| File | Rule | Product / purpose | Evidence | Strength |
| --- | --- | --- | --- | --- |
| `direct.yaml` | `DOMAIN,www.cycani.org` | 本地直连例外 | 仓库维护者策略 | 维护者例外 |
| `proxy.yaml` | `DOMAIN-SUFFIX,steam-chat.com` | Steam Chat 本地代理例外 | 仓库维护者策略 | 维护者例外 |
| `microsoft@cn.yaml` | `DOMAIN,ntp.msn.com` | Microsoft NTP | [Microsoft 365 endpoint guidance](https://learn.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges) | 运行观察 |
| `microsoft@cn.yaml` | `DOMAIN,edge.microsoft.com` | Microsoft Edge | [Microsoft Edge enterprise documentation](https://learn.microsoft.com/en-us/deployedge/) | 官方域名 |
| `ai-general.yaml` | `DOMAIN-SUFFIX,copilot.com` | Microsoft Copilot | [Microsoft Copilot network requirements](https://learn.microsoft.com/en-us/copilot/manage) | 官方端点 |
| `ai-general.yaml` | `DOMAIN-SUFFIX,copilot.microsoft.com` | Microsoft Copilot | [Microsoft Copilot network requirements](https://learn.microsoft.com/en-us/copilot/manage) | 官方端点 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,pi.dev` | Pi coding agent | [Pi](https://pi.dev/) | 官方域名 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,ampcode.com` | Amp | [Amp](https://ampcode.com/) | 官方域名 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,ampworkers.com` | Amp worker service | [Amp manual](https://ampcode.com/manual) | 运行观察 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,opencode.ai` | OpenCode | [OpenCode documentation](https://opencode.ai/docs/) | 官方域名 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,cline.bot` | Cline | [Cline documentation](https://docs.cline.bot/cline-overview) | 官方域名 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,cursor-cdn.com` | Cursor assets | [Cursor troubleshooting](https://docs.cursor.com/en/troubleshooting/troubleshooting-guide) | 运行观察 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,cursor.com` | Cursor | [Cursor documentation](https://docs.cursor.com/) | 官方域名 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,cursor.sh` | Cursor legacy service | [Cursor documentation](https://docs.cursor.com/) | 运行观察 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,cursorapi.com` | Cursor API | [Cursor troubleshooting](https://docs.cursor.com/en/troubleshooting/troubleshooting-guide) | 运行观察 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,codeium.com` | Windsurf / Codeium | [Devin Desktop network requirements](https://docs.devin.ai/desktop/troubleshooting/windsurf-common-issues#what-domains-should-i-allowlist-for-network-filters-firewalls-vpns-or-proxies) | 官方端点 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,codeiumdata.com` | Windsurf distribution/service | [Devin Desktop network requirements](https://docs.devin.ai/desktop/troubleshooting/windsurf-common-issues#what-domains-should-i-allowlist-for-network-filters-firewalls-vpns-or-proxies) | 官方端点 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,windsurf.build` | Windsurf build service | [Devin Desktop network requirements](https://docs.devin.ai/desktop/troubleshooting/windsurf-common-issues#what-domains-should-i-allowlist-for-network-filters-firewalls-vpns-or-proxies) | 运行观察 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,windsurf.com` | Windsurf | [Windsurf](https://windsurf.com/) | 官方域名 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,githubcopilot.com` | GitHub Copilot API | [GitHub Copilot allowlist](https://docs.github.com/en/copilot/reference/copilot-allowlist-reference) | 官方端点 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,copilot-stg.com` | Copilot staging service | [GitHub Copilot allowlist](https://docs.github.com/en/copilot/reference/copilot-allowlist-reference) | 运行观察 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,copilot.cloud.microsoft` | Microsoft 365 Copilot | [Microsoft 365 Copilot requirements](https://learn.microsoft.com/en-us/copilot/microsoft-365/microsoft-365-copilot-requirements) | 官方端点 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,devin.ai` | Devin | [Devin network requirements](https://docs.devin.ai/zh/enterprise/vpc/requirements) | 官方端点 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,kiro.dev` | Kiro | [Kiro documentation](https://kiro.dev/docs/) | 官方域名 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,jetbrains.ai` | JetBrains AI | [JetBrains AI network endpoints](https://www.jetbrains.com/help/ai-assistant/disable-ai-assistant.html) | 官方端点 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,grazie.ai` | JetBrains AI / Grazie | [JetBrains AI network endpoints](https://www.jetbrains.com/help/ai-assistant/disable-ai-assistant.html) | 运行观察 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,grazie.aws.intellij.net` | JetBrains AI API | [JetBrains AI network endpoints](https://www.jetbrains.com/help/ai-assistant/disable-ai-assistant.html) | 官方端点 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,coderabbit.ai` | CodeRabbit | [CodeRabbit FAQ](https://docs.coderabbit.ai/faq) | 官方端点 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,coderabbit.gallery.vsassets.io` | CodeRabbit extension asset | [CodeRabbit documentation](https://docs.coderabbit.ai/) | 运行观察 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,jules.google` | Google Jules | [Jules](https://jules.google/) | 官方域名 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,jules.google.com` | Google Jules application | [Jules getting started](https://jules.google/docs/) | 官方端点 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,deepwiki.com` | Cognition DeepWiki legacy/current entry | [Cognition announcement](https://cognition.com/blog/deepwiki) | 官方端点 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,deepwiki.org` | Cognition DeepWiki | [DeepWiki](https://deepwiki.org/) | 官方域名 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,qoder.com` | Qoder | [Qoder quick start](https://docs.qoder.com/quick-start) | 官方域名 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,trae.ai` | TRAE | [TRAE](https://www.trae.ai/) | 官方域名 |
| `ai-coding.yaml` | `DOMAIN-SUFFIX,marscode.com` | MarsCode / TRAE predecessor service | [MarsCode](https://www.marscode.com/) | 官方域名 |
| `ai-gateway.yaml` | `DOMAIN-SUFFIX,vercel.ai` | Vercel AI platform | [Vercel AI Gateway](https://vercel.com/docs/ai-gateway) | 官方域名 |
| `ai-gateway.yaml` | `DOMAIN-SUFFIX,ai-gateway.vercel.sh` | Vercel AI Gateway API | [Vercel AI Gateway](https://vercel.com/docs/ai-gateway) | 官方端点 |
| `ai-gateway.yaml` | `DOMAIN-SUFFIX,openrouter.ai` | OpenRouter API | [OpenRouter quickstart](https://openrouter.ai/docs/quickstart) | 官方端点 |
| `ai-gateway.yaml` | `DOMAIN-SUFFIX,gateway.ai.cloudflare.com` | Cloudflare AI Gateway provider endpoint | [Cloudflare AI Gateway authentication](https://developers.cloudflare.com/ai-gateway/configuration/authentication/) | 官方端点 |
| `ai-gateway.yaml` | `DOMAIN,api.together.xyz` | Together AI API | [Together AI documentation](https://docs.together.ai/docs/quickstart) | 官方端点 |

## 维护规则

- 增删本地规则时同步更新本表；规则与依据必须一一对应。
- `运行观察` 条目不能仅因存在于旧列表就永久保留，应结合客户端网络日志或新的官方文档定期复核。
- 产品改名、域名迁移或端点弃用时，先更新本地规则和本表，再通过基线报告确认影响。
