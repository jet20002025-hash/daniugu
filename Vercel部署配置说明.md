# Vercel 部署配置说明

## ✅ 已完成的配置

### 1. vercel.json 配置文件

已更新 `vercel.json`，包含：
- **路由配置**：所有请求转发到 `api/index.py`
- **函数配置**：设置最大执行时间为 10 秒（Hobby 计划）
- **Cron 任务**：配置了定时扫描任务

```json
{
  "version": 2,
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "api/index.py"
    }
  ],
  "functions": {
    "api/index.py": {
      "maxDuration": 10
    }
  },
  "crons": [...]
}
```

### 2. api/index.py Serverless 入口

`api/index.py` 已配置为 Vercel serverless 函数入口：
- 自动设置 `VERCEL=1` 环境变量
- 导入 `bull_stock_web` 应用
- 包含错误处理

### 3. 环境检测逻辑

代码已支持 Vercel 环境检测：
- 自动检测 `VERCEL`、`VERCEL_ENV`、`VERCEL_URL` 环境变量
- Vercel 环境使用 `user_auth_vercel.py`（Redis 存储）
- Vercel 环境使用分批处理扫描（`vercel_scan_helper.py`）

## 🚀 部署步骤

### 步骤 1: 提交代码到 GitHub

```bash
git add .
git commit -m "配置 Vercel 部署"
git push origin main
```

### 步骤 2: 在 Vercel 创建项目

1. 访问 [Vercel Dashboard](https://vercel.com/dashboard)
2. 点击 **"New Project"**
3. 选择你的 GitHub 仓库
4. Vercel 会自动检测配置

### 步骤 3: 配置环境变量

在 Vercel Dashboard → Settings → Environment Variables 添加：

**必需的环境变量：**
- `UPSTASH_REDIS_REST_URL` - Upstash Redis REST URL
- `UPSTASH_REDIS_REST_TOKEN` - Upstash Redis REST Token
- `INVITE_CODES` - 邀请码列表（用逗号分隔，如：`ADMIN2024,VIP2024`）
- `FLASK_SECRET_KEY` - Flask 会话密钥（可选，建议设置）

**可选的环境变量：**
- `PYTHON_VERSION=3.9` - Python 版本（默认会自动检测）

### 步骤 4: 部署

点击 **"Deploy"**，Vercel 会：
1. 安装依赖（从 `requirements.txt`）
2. 构建项目
3. 部署到生产环境

### 步骤 5: 配置域名（可选）

1. 在 Vercel Dashboard → Settings → Domains
2. 添加你的域名（如：`daniugu.online`）
3. 按照提示配置 DNS 记录

## ⚠️ 重要限制

### Vercel Hobby 计划（免费）

- **执行时间限制**：10 秒
- **解决方案**：已实现分批处理，将大任务拆分成多个小批次

### Vercel Pro 计划（推荐）

- **执行时间限制**：60 秒
- **费用**：$20/月
- **优势**：更长的执行时间，更适合扫描任务

## 🔧 代码特性

### 1. 自动环境检测

代码会自动检测 Vercel 环境：
```python
is_vercel = (
    os.environ.get('VERCEL') == '1' or 
    os.environ.get('VERCEL_ENV') is not None or
    os.environ.get('VERCEL_URL') is not None
)
```

### 2. 分批处理扫描

Vercel 环境使用 `vercel_scan_helper.py` 进行分批处理：
- 每个批次在 10 秒内完成
- 使用 Redis 存储进度
- 前端通过轮询查询进度

### 3. Redis 存储

Vercel 环境使用 Upstash Redis 存储：
- 用户数据（`user_auth_vercel.py`）
- 扫描进度（`scan_progress_store.py`）
- 股票缓存（可选）

## 📊 监控和日志

### 查看日志

1. **Vercel Dashboard**：
   - 进入项目 → Deployments → 最新部署
   - 查看 "Function Logs"

2. **Vercel CLI**：
   ```bash
   vercel logs [项目名] --follow
   ```

### 健康检查

访问 `/api/health` 端点检查服务状态：
```
https://你的域名.vercel.app/api/health
```

应该返回：
```json
{
  "success": true,
  "status": "ok",
  "environment": "vercel"
}
```

## 🐛 常见问题

### 1. 超时错误

**问题**：扫描任务超过 10 秒导致超时

**解决方案**：
- 已实现分批处理，自动拆分任务
- 确保使用缓存，避免直接调用 API
- 考虑升级到 Pro 计划（60 秒限制）

### 2. 导入错误

**问题**：`ModuleNotFoundError` 或 `ImportError`

**解决方案**：
- 检查 `requirements.txt` 是否包含所有依赖
- 确认 `api/index.py` 路径设置正确

### 3. Redis 连接失败

**问题**：无法连接到 Upstash Redis

**解决方案**：
- 检查环境变量是否正确设置
- 确认 Upstash Redis 服务正常
- 查看 Vercel 日志中的错误信息

## 📝 部署检查清单

- [ ] 代码已推送到 GitHub
- [ ] 在 Vercel 创建项目
- [ ] 配置环境变量（Redis、邀请码等）
- [ ] 部署成功
- [ ] 测试健康检查端点 `/api/health`
- [ ] 测试登录功能
- [ ] 测试扫描功能（分批处理）
- [ ] 配置域名（可选）
- [ ] 配置 Cloudflare（可选）

## 🔄 持续部署

每次推送到 GitHub 主分支，Vercel 会自动：
1. 检测代码变更
2. 重新构建
3. 部署新版本

## 💡 优化建议

1. **使用缓存**：确保股票数据使用缓存，避免直接调用 API
2. **分批处理**：大任务自动分批，无需手动处理
3. **监控日志**：定期查看 Vercel 日志，及时发现问题
4. **升级计划**：如果经常超时，考虑升级到 Pro 计划

---

**按照以上步骤操作，即可成功部署到 Vercel！**
