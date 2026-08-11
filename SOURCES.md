# Sources

本文件记录 `config.yaml` 中每类上游的用途和再分发审查状态。它不是上游许可证的替代品。

| Source family | Upstream | Use | License / redistribution status |
| --- | --- | --- | --- |
| Sukka Ruleset | [ruleset.skk.moe](https://ruleset.skk.moe) | domestic, direct, AI, stream, Telegram, CDN, download, global, LAN and IP sets | 发布前必须核对上游当前声明 |
| MetaCubeX rule data | [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat) | private, China IP, Cloudflare CN, GFW and Bytedance categories | 发布前必须核对上游当前声明 |
| DustinWin domain lists | [DustinWin/domain-list-custom](https://github.com/DustinWin/domain-list-custom) | China, Microsoft, Apple, AI and Google-CN categories | 发布前必须核对上游当前声明 |
| blackmatrix7 Steam CN | [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) | Steam CN category | 发布前必须核对上游当前声明 |
| xndeye adblock list | [xndeye/adblock_list](https://github.com/xndeye/adblock_list) | reject domain category | 发布前必须核对上游当前声明 |
| ACL4SSR | [ACL4SSR/ACL4SSR](https://github.com/ACL4SSR/ACL4SSR) | supplemental AI category | 发布前必须核对上游当前声明 |
| Local files | `local/*.yaml` | owner-maintained direct, proxy, AI and Microsoft exceptions | Maintained with this fork; review before redistribution |

在许可证不明确、未授权再分发或来源用途发生变化时，配置中的 source 必须保持 `redistributable: false`，不能通过 `legacy` 或格式转换绕过审查。构建器默认拒绝未显式批准的来源。
