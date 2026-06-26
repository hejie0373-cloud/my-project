# Dify 工作流 DSL 文件

本目录包含「客留」平台的 6 个 Dify 工作流配置，可直接导入 Dify 使用。

## 文件清单

| # | 文件名 | 模式 | 说明 |
|---|--------|------|------|
| 1 | `1-cicd-deploy-notify.yml` | workflow | CI/CD 部署通知 — 接收部署事件，生成中文通知消息，评估优先级 |
| 2 | `2-cicd-failure-diagnose.yml` | workflow | CI/CD 失败诊断 — 分析失败原因，生成结构化诊断报告和修复步骤 |
| 3 | `3-cicd-rollback-analyze.yml` | workflow | CI/CD 回滚分析 — 分析影响范围，生成回滚方案和验证检查清单 |
| 4 | `4-churn-predict.yml` | workflow | 客户流失预测 — 基于到店记录计算流失风险评分 + CLV，输出预警和建议 |
| 5 | `5-copy-generate.yml` | workflow | 营销文案生成器 — 根据客户画像自动生成个性化营销跟进文案（短信/邮件/微信） |
| 6 | `6-insight-chatbot.yml` | advanced-chat | 业务洞察对话机器人 — 面向店主/店员的智能问答助手 |

## 技术规格

- **DSL 版本**: `0.6.0`
- **AI 模型**: DeepSeek (deepseek-chat)
- **代码节点**: Python 3
- **适用环境**: Dify 开源版 / 云版

## 使用方法

### 导入工作流

1. 打开 Dify 后台 → 点击「创建应用」→ 选择「导入文件」
2. 选择对应的 `.yml` 文件
3. 确认导入后即可使用

### 前置要求

- 在 Dify 设置 → 模型供应商 中添加 **DeepSeek** 并配置 API Key
- 如未配置，导入后需手动将 LLM 节点的模型切换为已配置的模型

## DSL 格式说明

本套文件严格遵循 Dify DSL v0.6.0 规范：

| 关键字段 | 值 | 说明 |
|----------|-----|------|
| `version` | `"0.6.0"` | 当前 DSL 版本号 |
| `kind` | `app` | 应用类型标识 |
| `nodes[].type` | `"custom"` | 所有节点统一包装为 custom 类型 |
| `nodes[].data.type` | 实际类型 | start/end/llm/code/answer/knowledge-retrieval |
| `nodes[].id` | 数字串 | 如 `"1000001"`, `"1000002"` 等 |
| `edges[]` | 含 zIndex: 0 | 边需包含 z-index 属性 |
| `features` | 完整结构 | 包含 file_upload.image/retriever_resource/sensitive_word_avoidance/suggested_questions_after_answer |

## 变量引用语法

Dify DSL 中引用其他节点的输出变量格式：`{{#节点ID.字段名#}}`

示例：
- 引用 Start 节点输入：`{{#1000001.customer_name#}}`
- 引用 Code 节点输出：`{{#1000002.risk_score#}}`
- 引用 LLM 节点文本：`{{#1000003.text#}}`
- 引用系统查询（仅 chatflow）：`{{#sys.query#}}`

## 注意事项

1. **模型依赖**：所有 LLM 节点默认使用 deepseek-chat，请确保已在 Dify 中配置该模型
2. **知识库**：#6 chatbot 的知识检索节点默认无绑定数据集（dataset_ids 为空），可按需关联
3. **参数调整**：temperature、max_tokens 等 completion_params 可在 Dify 画布中随时修改
4. **Code 节点**：Python 函数必须命名为 `main`，返回值必须是 dict，且 key 与 outputs 定义一致
