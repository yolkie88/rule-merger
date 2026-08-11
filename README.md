# rule-merger

`rule-merger` 是一个将多个公开规则源规范化、审计并生成 Mihomo / sing-box 规则集的构建器。

当前 fork：`yolkie88/rule-merger`。生成物发布在 `release` 分支；`master` 只保存配置、构建器和测试。

## v2 结构

规则先进入中性分类，再由 profile 决定动作：

- `categories/`：`private`、`reject`、`cn`、平台、AI、流媒体、Telegram、GFW、global、CDN、download、Google-CN 等分类。
- `profiles/default/`：可直接绑定动作的 `direct-*`、`reject-*`、`proxy-*`，以及显式 `override-*`。
- CDN、download、Google-CN 只作为分类发布，不自动决定出口。

推荐的匹配顺序是：

```text
private → override-direct / override-reject / override-proxy
→ reject → direct → proxy → final
```

父子域名和 CIDR 包含关系可同时存在于不同动作产物中，并由上述匹配顺序决定：较具体的 `reject` 规则会先于包含它的 `direct` / `proxy` 规则匹配。这些关系会写入构建报告的 `ordered_containment`，但不会阻止发布。精确重复规则则按 `reject > direct > proxy` 的动作优先级解析。[`local/overrides.yaml`](local/overrides.yaml) 仅用于把本地例外提前输出为 `override-*` 产物。

## 使用

```text
python -m rulemerger build --config config.yaml --output <staging-dir> \
  --baseline <previous-manifest> --report <report.json>
```

构建失败不会替换已有输出目录。已有目录在 Windows 上采用备份、替换和回滚事务；若需要并发读者在替换期间也保持零空窗，需要另行引入版本目录加指针协议。`BuildReport` 和 `manifest.json` 会记录上游 URL、SHA256、ETag / Last-Modified、规则数量、输出 hash、冲突、波动和工具版本。

source 默认 `redistributable: false`；只有完成许可证/再分发审查并显式设为 `true` 的来源才会进入公开构建。
少于 `quality.small_output_limit` 条的产物必须在 `quality.critical_rules` 中列出关键规则；缺少清单时构建会 fail closed。
`critical_rules` 可使用无扩展名规则集路径（如 `categories/private-ip`），一次覆盖 YAML、JSON、SRS、MRS 的同一规则集。

输出格式：

- YAML：Mihomo classical `payload`，保留 `PROCESS-NAME`、`DOMAIN-WILDCARD`、`IP-ASN` 等 Mihomo 原生规则。
- JSON / SRS：sing-box rule-set；`PROCESS-NAME` 会映射为 `process_name`，域通配符会映射为等价 `domain_regex`。
- MRS：仅生成可由 Mihomo domain/ipcidr 规则集表达的规则；进程、ASN、关键词、通配符和正则规则不会写入 MRS。Mihomo 会将普通域名规范化为 suffix 匹配，并可能合并相邻 CIDR；构建会按等价匹配集合校验这些规范化结果。
- 规则无法在目标格式无损表达时，构建继续发布可兼容的产物，并在 `BuildReport.warnings` 和对应 output 的 `omitted_kinds` 中明确记录；例如 `IP-ASN` 是 Mihomo-only，不会伪造为 sing-box CIDR。
- sing-box `logical` 规则暂不接受；因统一模型无法保留其 AND/OR 语义，构建会显式失败而不会静默展平。

## 引用生成物

将 `<name>` 替换为 `categories/<category>.<format>` 或 `profiles/default/<action>.<format>`：

```text
https://raw.githubusercontent.com/yolkie88/rule-merger/refs/heads/release/<name>
```

第一次 v2 发布可通过 `--include-legacy` 同时生成旧根目录名称；下一次成功发布不再带该参数，旧名称随之删除。新配置和路径应优先迁移到 `categories/` / `profiles/default/`。

## 自动更新

GitHub Actions 每 12 小时运行一次，也支持手动触发。必选源获取、解析、转换、冲突、数量波动或格式往返验证失败时，`release` 分支不变；无变化时不提交。工具版本、依赖和 Actions 使用固定版本，发布不使用 force push。

## 来源与许可证

来源、用途和许可证核对记录见 [`SOURCES.md`](SOURCES.md)。规则源的许可证状态必须在公开再分发前核实；本项目不为上游规则重新声明许可证。
