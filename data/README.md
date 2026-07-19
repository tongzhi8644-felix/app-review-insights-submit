# data/ 目录说明

本目录用于**样本、标注缓存与示例输出**，方便面试官在无外网时审阅。

| 路径 | 标签 | 用途 |
|------|------|------|
| `sample_reviews.json` | SAMPLE / LABELED | 离线样本评论（JSON 导入示例） |
| `sample_reviews.csv` | SAMPLE / LABELED | 同内容 CSV 导入示例 |
| `cached_analysis/839285684_reviews.json` | CACHED / LABELED | 演示 App 的评论缓存 |
| `cached_analysis/839285684_bundle.json` | CACHED / LABELED | findings / PRD / 用例缓存包 |
| `sample_output/demo_run_summary.json` | SAMPLE OUTPUT / LABELED | 一次完整交付物摘要示例 |

**重要：**

- 上述文件均已在内容中用 `_label` 或本说明标注，**不能替代**在配置好网络与模型后处理**新链接 / 新数据集 / 新分析目标**的能力。
- 在线主路径仍通过 Apple US Reviews RSS 或用户上传的 JSON/CSV 实时处理。
