# App Review Insights

将美国区 App Store 用户评论转化为可追溯的 findings、PRD 与测试用例的本地可运行工具。

考核说明参考：[retro-labs/app-review-insights](https://github.com/retro-labs/app-review-insights)

---

## 本地运行

详见 **[deploy.txt](deploy.txt)**（中文完整部署步骤）。

简要步骤：

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# 编辑 .env：数据库与 OPENAI_API_KEY 等
# 按 deploy.txt 初始化数据库
python run.py
```

浏览器打开：http://127.0.0.1:5000

密钥只放在 `.env`，**不要提交**真实 Key。

---

## 数据采集方式与局限

### 在线主数据源（非页面 HTML 抓取）

使用 Apple 公开 **iTunes Customer Reviews RSS JSON**，强制 **美国区（us）** storefront：

```
https://itunes.apple.com/us/rss/customerreviews/page={n}/id={app_id}/sortby=mostrecent/json
```

实现见 `app/services/collector.py`。

**局限：**

- 仅公开、较新的评论（约 50 条/页，页数由 `MAX_REVIEW_PAGES` 限制）
- 不是完整历史库
- 客户端页间有礼貌延时，避免异常压力
- 不依赖 apps.apple.com 页面 DOM 可见内容爬取

### 导入与离线

| 方式 | 说明 |
|------|------|
| JSON / CSV 上传 | UI 可选导入；字段见下文 |
| 标注样本 | `data/sample_reviews.json`（`_label` 标明 SAMPLE） |
| 标注缓存 | `data/cached_analysis/`（`_label` 标明 CACHED；**不能替代**在线分析能力） |

面试官可提供：新的 App Store 链接、未见过的兼容评论集、或新的分析目标。系统不写死某一 App 的分类/结论/需求/用例。

---

## JSON / CSV 导入格式

**JSON**：评论对象数组，或 `{"reviews":[...]}`。

识别字段：`review_id`（或 `id`）、`rating`、`title`、`content`（或 `body`）、`author`、`version`、`updated_at`（可选）。

**CSV** 表头示例：

```csv
review_id,author,rating,title,content,version,updated_at
```

示例文件：

- `data/sample_reviews.json`
- `data/sample_reviews.csv`

---

## 方法选择（规则 vs 模型）

| 阶段 | 方法 | 原因 |
|------|------|------|
| 采集 | HTTP RSS / 导入 | 可复现、公开接口 |
| 清洗去重 | 规则 + 内容哈希 | 确定性 |
| 目标范围 | 轻量规则 | 仅缩小候选集 |
| 分类 / 发现 / PRD / 用例 | **DeepSeek**（运行时模型驱动） | 动态语义，非固定词表 |
| 追溯校验 | 规则 | 剔除无支撑结论 |

模型配置：`.env` 中 `OPENAI_*`。失败处理：阶段日志警告 → 可选标注缓存/启发式；不伪造评论。

更完整的设计说明见 **[设计说明.md](设计说明.md)**。

---

## 离线审阅样本输出

- `data/cached_analysis/839285684_bundle.json`：标注缓存的 findings / PRD / 用例  
- `data/sample_output/demo_run_summary.json`：一次完整跑通的交付物摘要示例  

以上均为 **LABELED / 离线审阅用**，有网络与模型配置时应能处理新输入。

---

## 交付物清单（考核「交付成果」）

- [x] 完整源码  
- [x] 依赖配置 `requirements.txt`  
- [x] 运行说明 `README.md` + `deploy.txt`  
- [x] 数据采集说明（本节 + `collector.py`）  
- [x] 标注样本 / 缓存结果（`data/`）  
- [x] JSON/CSV 导入  
- [x] 设计说明（含 AI / DeepSeek 使用方式）  
- [x] Git 完整提交历史（体现迭代）  

---

## 项目结构

```
app/                 应用、流水线服务、UI
data/                样本、标注缓存、示例输出
sql/schema.sql       数据库结构
run.py               启动入口
deploy.txt           部署说明
设计说明.md          设计思路 / 实现 / AI
requirements.txt
.env.example
```
