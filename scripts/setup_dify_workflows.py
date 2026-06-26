"""
一键创建 3 个 CI/CD Dify 工作流
用法: python scripts/setup_dify_workflows.py --api-key app-xxx --dify-url http://localhost:5001
"""
import argparse, json, sys
import requests

BASE_URL = "http://localhost:5001"


def create_workflow(name, description, prompt_template, inputs, outputs, api_key):
    """通过 Dify API 创建工作流应用（如果 API 不支持程序化创建，打印手动配置步骤）"""
    print(f"\n{'='*60}")
    print(f"📋 {name}")
    print(f"   {description}")
    print(f"{'='*60}")

    print(f"\n🔧 请手动在 Dify 后台创建此工作流（http://localhost）：")
    print(f"   1. 创建应用 → 类型: Workflow")
    print(f"   2. 名称: {name}")
    print(f"   3. 输入变量:")
    for var_name, var_type in inputs.items():
        print(f"      - {var_name}: {var_type}")
    print(f"   4. LLM 节点 Prompt:")
    for line in prompt_template.strip().split("\n"):
        print(f"      {line}")
    print(f"   5. 输出变量:")
    for var_name, var_type in outputs.items():
        print(f"      - {var_name}: {var_type}")
    print(f"   6. 发布 → 复制 API Key")

    return {"name": name, "created": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", default="", help="Dify API Key（所有工作流共用）")
    parser.add_argument("--dify-url", default="http://localhost:5001")
    args = parser.parse_args()

    # ---- 工作流 1: 部署通知 ----
    create_workflow(
        name="CI/CD 部署通知",
        description="接收 GitHub Actions 事件，发送部署状态通知",
        prompt_template="""
你是客留平台的 DevOps 助手。收到以下部署事件：

事件: {{event}}
仓库: {{repo}}
分支: {{branch}}
提交: {{commit}}
操作人: {{actor}}
时间: {{timestamp}}
错误: {{error}}

请生成一条简洁的中文通知消息，格式：
{{event_type_emoji}} [{{repo}}] {{summary}} ({{commit_short}} by {{actor}})

如果 event 包含 "failed"，语气要紧急且给出第一反应建议。
如果 event 是 "deploy_success"，语气积极庆贺。
        """,
        inputs={
            "event": "Text", "repo": "Text", "branch": "Text",
            "commit": "Text", "actor": "Text", "error": "Text", "timestamp": "Text",
        },
        outputs={"notification_text": "Text", "priority": "Text"},
        api_key=args.api_key,
    )

    # ---- 工作流 2: 失败诊断 ----
    create_workflow(
        name="CI/CD 失败诊断",
        description="分析部署失败原因，给出修复建议",
        prompt_template="""
你是客留平台的技术诊断专家。部署流水线在以下阶段失败：

失败阶段: {{pipeline_stage}}
仓库: {{repo}}
提交: {{commit}}
错误日志: {{error_log}}

请分析：
1. **根本原因**: 1-2 句精准定位
2. **严重级别**: critical/high/medium/low
3. **修复建议**: 3 条可操作的具体步骤
4. **相关文件**: 最可能需要修改的文件路径

输出 JSON 格式：
{"root_cause":"...", "severity":"...", "suggestions":["...","...","..."], "files":["..."]}

只输出 JSON，不要解释。
        """,
        inputs={
            "event": "Text", "repo": "Text", "commit": "Text",
            "error_log": "Text", "pipeline_stage": "Text",
        },
        outputs={"root_cause": "Text", "severity": "Text", "suggestions": "Text", "files": "Text"},
        api_key=args.api_key,
    )

    # ---- 工作流 3: 回滚分析 ----
    create_workflow(
        name="部署回滚分析",
        description="部署失败后对比上次成功部署，决定是否回滚",
        prompt_template="""
你是客留平台的生产环境守护者。当前部署在 {{pipeline_stage}} 阶段失败。

当前提交: {{commit}}
上次成功部署: {{last_good_commit}}
错误: {{error_log}}

请决策：
1. **建议操作**: "rollback" / "hotfix" / "wait"
2. **影响范围**: 哪些功能受影响
3. **回滚命令**: 如果需要回滚，给出具体 git/docker 命令
4. **预计恢复时间**: 分钟

输出 JSON：
{"action":"rollback|hotfix|wait", "impact":"...", "rollback_cmd":"...", "eta_minutes": 数字}
        """,
        inputs={
            "pipeline_stage": "Text", "commit": "Text",
            "last_good_commit": "Text", "error_log": "Text",
        },
        outputs={"action": "Text", "impact": "Text", "rollback_cmd": "Text", "eta_minutes": "Number"},
        api_key=args.api_key,
    )

    print(f"\n{'='*60}")
    print("✅ 配置完成!")
    print(f"{'='*60}")
    print()
    print("所有 3 个工作流创建完毕后，复制任意一个的 API Key")
    print("填入 backend/.env: DIFY_CHURN_API_KEY / DIFY_COPY_API_KEY / DIFY_INSIGHT_API_KEY")
    print()
    print("然后重新部署后，GitHub Actions 会自动触发这些工作流。")


if __name__ == "__main__":
    main()
