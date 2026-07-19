# 初始化 Git 提交历史（考核要求保留完整 commit history）
# 本机若尚未安装 Git：https://git-scm.com/download/win
# 安装后在项目根目录执行：
#   powershell -ExecutionPolicy Bypass -File scripts\init_git_history.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Git([string[]]$Args) {
  & git @Args
  if ($LASTEXITCODE -ne 0) { throw "git $($Args -join ' ') failed" }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Error "未找到 git。请先安装 Git for Windows，并重新打开终端。"
}

if (Test-Path .git) {
  Write-Host "已存在 .git，跳过 init。如需重建请先删除 .git 目录。"
} else {
  Git @("init")
  Git @("config", "user.name", "app-review-insights")
  Git @("config", "user.email", "candidate@local.dev")
}

function Commit-Step($message, $paths) {
  foreach ($p in $paths) {
    if (Test-Path $p) { Git @("add", "--", $p) }
  }
  $status = git status --porcelain
  if (-not $status) { return }
  Git @("commit", "-m", $message)
}

# 分步提交，体现迭代过程
Commit-Step "chore: scaffold project config and dependencies" @(
  ".gitignore", ".env.example", "requirements.txt", "run.py", "sql"
)

Commit-Step "feat: add data models and app factory" @(
  "app/__init__.py", "app/config.py", "app/extensions.py", "app/models.py"
)

Commit-Step "feat: implement review collection and cleaning" @(
  "app/services/__init__.py", "app/services/collector.py", "app/services/cleaner.py"
)

Commit-Step "feat: add model-driven analysis, PRD and test generation" @(
  "app/services/llm.py", "app/services/analyzer.py", "app/services/planner.py",
  "app/services/testgen.py", "app/services/validator.py", "app/services/workflow.py"
)

Commit-Step "feat: add Flask API routes and web UI" @(
  "app/routes", "app/templates", "app/static"
)

Commit-Step "docs: add sample data, labeled cache and import examples" @(
  "data"
)

Commit-Step "docs: add README, deploy guide and design notes" @(
  "README.md", "deploy.txt", "设计说明.md", "pack.bat", "scripts"
)

Write-Host ""
Write-Host "Git 历史已创建。查看："
Git @("log", "--oneline")
Write-Host ""
Write-Host "推送到 GitHub 示例："
Write-Host "  git remote add origin https://github.com/<你的用户名>/app-review-insights.git"
Write-Host "  git branch -M main"
Write-Host "  git push -u origin main"
