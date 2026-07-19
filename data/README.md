# data/ 目录说明

本目录用于**样本、标注缓存与示例输出**，方便面试官在无外网时审阅。

| 路径 | 标签 | 用途 |
|------|------|------|
| `sample_reviews.json` | SAMPLE / LABELED | 离线样本评论（JSON 导入示例） |
| `sample_reviews.csv` | SAMPLE / LABELED | 同内容 CSV 导入示例 |
| `cached_analysis/839285684_reviews.json` | CACHED / LABELED | 演示 App 的评论缓存 |
| `cached_analysis/839285684_bundle.json` | CACHED / LABELED | findings / PRD / 用例缓存包 |
| `cached_analysis/839285684_reviews_real_rss_run2.json` | CACHED REAL RSS / LABELED | Apple US RSS 的 500 条真实评论快照 |
| `cached_analysis/839285684_bundle_real_rss_run2.json` | CACHED REAL RSS ANALYSIS / LABELED | 与真实评论快照配对的 DeepSeek 分析结果 |
| `sample_output/demo_run_summary.json` | SAMPLE OUTPUT / LABELED | 一次完整交付物摘要示例 |

**重要：**

- 上述文件均已在内容中用 `_label` 或本说明标注，**不能替代**在配置好网络与模型后处理**新链接 / 新数据集 / 新分析目标**的能力。
- 在线主路径仍通过 Apple US Reviews RSS 或用户上传的 JSON/CSV 实时处理。
- 真实缓存对的 App Store 链接为 `https://apps.apple.com/us/app/workout-for-women-home-gym/id839285684`，采集 storefront 为 `us`，快照 ID 为 `839285684-run-2-20260719T182451Z`。
- 分析包中的 `source_data_file` 指向配对评论文件，并保存其 SHA-256。程序仅加载文件名和哈希均匹配的 `*_real_rss_runN.json` 缓存对。
- 配对分析由 `deepseek-chat` 在线生成，未使用 fallback；结果含 7 个 findings、10 个 requirements 和 4 个 test cases，追溯校验为 `is_valid: true`。
- `cached_analysis/839285684_reviews_real_rss.json` 是本地未配对快照，不属于提交的离线演示缓存，也不应上传替代上述已验证缓存对。
