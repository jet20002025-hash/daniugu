# 🚀 部署最新代码到 Vercel - 快速指南

## ✅ 已完成的修复

### 1. 修复 Flask 入口点错误

- ✅ 创建了 `pyproject.toml`，指定入口点为 `index:app`
- ✅ 创建了根目录 `index.py`，从 `api/index.py` 导入 `app`
- ✅ 确保 `api/index.py` 正确导出 `app` 对象

### 2. 更新的文件

- `vercel.json` - Vercel 配置文件
- `api/index.py` - Serverless 函数入口
- `index.py` - 根目录入口点（新建）
- `pyproject.toml` - Python 项目配置（新建）

## 🚀 部署步骤

### 步骤 1: 提交代码到 GitHub

```bash
cd /Users/zwj/股票分析

# 添加修复文件
git add vercel.json api/index.py index.py pyproject.toml

# 提交更改
git commit -m "修复 Vercel Flask 入口点错误，添加 pyproject.toml 和根目录 index.py"

# 推送到 GitHub
git push origin main
```

### 步骤 2: Vercel 自动部署

- Vercel 会自动检测到代码推送
- 自动触发重新部署（通常 2-5 分钟）

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

## ⚙️ 配置环境变量（如果还没配置）

在 Vercel Dashboard → Settings → Environment Variables 添加：

**必需**：
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `INVITE_CODES` = `ADMIN2024,VIP2024`

**推荐**：
- `FLASK_SECRET_KEY` = 随机字符串

配置后需要重新部署。

## 🐛 如果仍然失败

### 检查 Vercel 日志

1. Vercel Dashboard → Deployments → 最新部署
2. 查看 "Function Logs"
3. 查找错误信息

### 常见问题

1. **导入错误**：检查 `requirements.txt` 是否包含所有依赖
2. **Redis 连接失败**：检查环境变量是否正确
3. **入口点错误**：确认 `pyproject.toml` 和 `index.py` 已提交

## 📝 文件说明

- `index.py`（根目录）：Vercel 的入口点，从 `api/index.py` 导入 `app`
- `api/index.py`：实际的 Flask 应用入口，导出 `app` 对象
- `pyproject.toml`：告诉 Vercel Flask 应用的入口点位置
- `vercel.json`：Vercel 路由和函数配置

---

**按照以上步骤操作，即可成功部署到 Vercel！**
