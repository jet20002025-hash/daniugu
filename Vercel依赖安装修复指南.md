# 🔧 Vercel Flask 模块未找到修复指南

## ❌ 错误信息

```
ModuleNotFoundError: No module named 'flask'
```

## 🔍 问题原因

Vercel 没有正确安装 Python 依赖。虽然 `requirements.txt` 存在，但 Vercel 可能优先使用 `pyproject.toml` 来安装依赖。

## ✅ 已修复

### 1. 更新 `pyproject.toml`

在 `pyproject.toml` 中添加了所有依赖项：

```toml
[project]
name = "daniugu"
version = "1.0.0"
description = "大牛股分析系统"
requires-python = ">=3.11"
dependencies = [
    "Flask>=2.3.0,<3.0.0",
    "pandas>=2.0.0,<3.0.0",
    "numpy>=1.24.0,<2.0.0",
    "akshare>=1.11.0",
    "openpyxl>=3.1.0,<4.0.0",
    "Werkzeug>=2.3.0,<3.0.0",
    "requests>=2.31.0",
    "gunicorn>=20.1.0",
]

[project.scripts]
app = "api.index:app"
```

### 2. 确保 `requirements.txt` 存在

`requirements.txt` 文件已存在且格式正确。

## 📋 Vercel 依赖安装规则

Vercel 支持以下依赖文件格式（按优先级）：
1. **`pyproject.toml`** - 如果存在，优先使用
2. **`requirements.txt`** - 如果 `pyproject.toml` 不存在
3. **`Pipfile`** - 如果前两者都不存在

## 🚀 下一步操作

### 1. 等待 Vercel 重新部署

代码已推送到 GitHub，Vercel 会自动重新部署（通常 2-5 分钟）。

### 2. 检查构建日志

在 Vercel Dashboard：
1. 项目 → Deployments → 最新部署
2. 点击 "Build Logs"
3. 应该看到类似输出：

```
Installing dependencies...
Collecting Flask>=2.3.0,<3.0.0
Collecting pandas>=2.0.0,<3.0.0
...
Successfully installed Flask-2.3.x pandas-2.0.x ...
```

### 3. 验证部署

部署完成后，访问：
```
https://daniugu.vercel.app/api/health
```

应该返回：
```json
{
  "success": true,
  "status": "ok",
  "environment": "vercel"
}
```

## 🐛 如果仍然失败

### 检查构建日志

如果构建日志中没有看到依赖安装，可能的原因：

1. **Vercel 项目设置问题**：
   - 检查 Vercel Dashboard → Settings → General
   - 确认 "Framework Preset" 设置为 "Other" 或 "Flask"
   - 确认 "Root Directory" 设置为 `./`（根目录）

2. **Python 版本问题**：
   - Vercel 使用 Python 3.12（固定版本）
   - 确保依赖兼容 Python 3.12

3. **依赖冲突**：
   - 检查构建日志中的错误信息
   - 可能需要调整版本约束

### 手动触发重新部署

如果自动部署失败：
1. Vercel Dashboard → Deployments
2. 点击最新部署右侧的 "..." 菜单
3. 选择 "Redeploy"

## 📝 总结

✅ **已修复**：在 `pyproject.toml` 中添加所有依赖  
✅ **已推送**：代码已推送到 GitHub  
⏳ **等待部署**：Vercel 会自动重新部署  

---

**修复已推送，请等待 Vercel 重新部署后测试！**
