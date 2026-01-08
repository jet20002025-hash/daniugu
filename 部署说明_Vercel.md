# Vercel + Cloudflare 部署指南

## ⚠️ 重要限制说明

**Vercel Serverless 函数的执行时间限制：**
- Hobby 计划：10秒
- Pro 计划：60秒
- Enterprise 计划：300秒（5分钟）

**当前应用的问题：**
- 扫描股票功能可能需要很长时间（几分钟到几小时）
- 后台任务使用线程，在 serverless 环境中可能不稳定
- 需要保持状态的分析器实例

## 🚀 部署步骤

### 1. 准备 GitHub 仓库

```bash
# 初始化 Git 仓库（如果还没有）
git init
git add .
git commit -m "准备部署到 Vercel"

# 创建 GitHub 仓库后，推送代码
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

### 2. 连接 Vercel

1. 访问 [Vercel](https://vercel.com)
2. 使用 GitHub 账号登录
3. 点击 "New Project"
4. 导入你的 GitHub 仓库
5. Vercel 会自动检测到 `vercel.json` 配置文件

### 3. 配置环境变量（如果需要）

在 Vercel 项目设置中添加环境变量：
- `PYTHON_VERSION=3.9`

### 4. 部署

Vercel 会自动：
- 检测 Python 项目
- 安装依赖（从 `requirements.txt`）
- 构建并部署

## 🔧 代码调整建议

由于 Vercel 的限制，建议进行以下调整：

### 方案一：异步任务处理（推荐）

将长时间运行的任务改为异步处理：

1. **扫描任务改为异步**：
   - 扫描开始时立即返回任务ID
   - 使用轮询机制查询进度
   - 或者使用 Vercel 的 Background Functions

2. **使用外部存储**：
   - 使用 Redis 或数据库存储扫描状态
   - 使用 Vercel KV 或 Upstash Redis

### 方案二：使用 Cloudflare Workers + Durable Objects

对于长时间运行的任务，可以考虑：
- 使用 Cloudflare Workers 处理 API
- 使用 Durable Objects 保持状态
- 使用 Cloudflare Queue 处理后台任务

### 方案三：混合架构

- **前端 + API**：部署到 Vercel（快速响应）
- **后台任务**：部署到其他平台（Railway、Render、Fly.io）
- **状态存储**：使用数据库或 Redis

## 📝 当前配置说明

### `vercel.json`
- 配置了 Python 3.9
- 设置了最大执行时间为 60 秒（Pro 计划）
- 路由配置：所有请求都转发到 `api/index.py`

### `api/index.py`
- Vercel serverless 函数入口
- 将 Flask 应用适配为 serverless 格式

## ⚡ Cloudflare 配置

### 1. 添加域名到 Cloudflare

1. 在 Cloudflare 添加你的域名
2. 更新 DNS 记录，将域名指向 Vercel 的部署地址

### 2. 配置 Cloudflare（可选）

- **CDN 加速**：自动启用
- **SSL/TLS**：自动启用（Full 模式）
- **缓存规则**：可以配置静态资源缓存

### 3. Cloudflare Workers（高级）

如果需要处理长时间任务，可以使用 Cloudflare Workers：
- 创建 Worker 处理 API 请求
- 使用 Durable Objects 保持状态
- 使用 Queue 处理后台任务

## 🐛 常见问题

### 1. 超时错误

**问题**：扫描任务超过 60 秒导致超时

**解决方案**：
- 将长时间任务改为异步处理
- 使用外部服务处理后台任务
- 升级到 Enterprise 计划（300秒限制）

### 2. 状态丢失

**问题**：serverless 函数是无状态的，每次调用都是新的实例

**解决方案**：
- 使用外部存储（Redis、数据库）保存状态
- 使用 Vercel KV 或 Upstash Redis

### 3. 依赖安装失败

**问题**：某些包在 Vercel 上安装失败

**解决方案**：
- 检查 `requirements.txt` 中的包版本
- 某些包可能需要系统依赖，Vercel 可能不支持

## 📊 监控和日志

- **Vercel Dashboard**：查看部署状态和日志
- **Cloudflare Analytics**：查看访问统计
- **Vercel Logs**：查看实时日志

## 🔄 持续部署

每次推送到 GitHub 主分支，Vercel 会自动：
1. 检测代码变更
2. 重新构建
3. 部署新版本

## 💡 优化建议

1. **静态资源**：将 CSS、JS、图片等放到 CDN
2. **API 缓存**：使用 Cloudflare 缓存 API 响应
3. **数据库连接池**：如果使用数据库，注意连接池管理
4. **错误处理**：添加完善的错误处理和日志

## 📞 需要帮助？

如果遇到问题，可以：
1. 查看 Vercel 部署日志
2. 检查 Cloudflare 配置
3. 查看应用日志

---

**注意**：由于 Vercel 的限制，建议先测试部署，确认功能正常后再正式使用。如果长时间任务较多，建议考虑其他部署方案。

