# Vercel Flask 入口点错误修复指南

## ❌ 错误信息

```
Error: No flask entrypoint found. Add an 'app' script in pyproject.toml or define an entrypoint in one of: app.py, src/app.py, app/app.py, api/app.py, index.py, src/index.py, app/index.py, api/index.py, server.py, src/server.py, app/server.py, api/server.py, main.py, src/main.py, app/main.py, api/main.py, wsgi.py, src/wsgi.py, app/wsgi.py, api/wsgi.py, asgi.py, src/asgi.py, app/asgi.py, api/asgi.py.
```

## ✅ 已实施的修复

### 1. 创建了 `pyproject.toml`

指定 Flask 应用入口点：

```toml
[project]
name = "daniugu"
version = "1.0.0"
description = "大牛股分析系统"

[project.scripts]
app = "index:app"
```

### 2. 创建了根目录 `index.py`

作为 Vercel 的入口点，重定向到 `api/index.py`：

```python
from api.index import app
```

### 3. 确保 `api/index.py` 正确导出 `app`

`api/index.py` 已经正确导出 `app = bull_stock_web.app`

## 🔧 部署步骤

### 步骤 1: 提交代码

```bash
git add .
git commit -m "修复 Vercel Flask 入口点错误"
git push origin main
```

### 步骤 2: 在 Vercel 重新部署

1. **自动部署**：Vercel 会自动检测到代码推送并重新部署
2. **手动部署**：在 Vercel Dashboard → Deployments → Redeploy

### 步骤 3: 验证部署

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

### 方案 A: 使用根目录 `app.py`（备选）

如果 `index.py` 不工作，可以创建根目录 `app.py`：

```python
from api.index import app
```

然后修改 `pyproject.toml`：

```toml
[project.scripts]
app = "app:app"
```

### 方案 B: 直接在 `api/index.py` 中创建 Flask 应用

如果导入失败，可以在 `api/index.py` 中直接创建 Flask 应用（不推荐，但可以作为临时方案）。

### 方案 C: 检查 Vercel 项目设置

1. 在 Vercel Dashboard → Settings → General
2. 检查 **"Framework Preset"** 是否设置为 **"Other"**
3. 检查 **"Root Directory"** 是否为空（使用根目录）
4. 检查 **"Build Command"** 是否为空
5. 检查 **"Output Directory"** 是否为空

## 📝 文件结构

修复后的文件结构：

```
项目根目录/
├── api/
│   └── index.py          # Flask 应用入口（导出 app）
├── index.py              # Vercel 入口点（重定向到 api/index.py）
├── pyproject.toml        # 指定入口点
├── vercel.json           # Vercel 配置
├── requirements.txt      # Python 依赖
└── bull_stock_web.py     # 主应用文件（定义 app）
```

## ✅ 验证清单

- [ ] `pyproject.toml` 已创建并配置
- [ ] `index.py` 已创建（根目录）
- [ ] `api/index.py` 正确导出 `app`
- [ ] 代码已推送到 GitHub
- [ ] Vercel 已重新部署
- [ ] 健康检查端点正常：`/api/health`

---

**按照以上步骤操作，应该可以解决 Flask 入口点错误！**
