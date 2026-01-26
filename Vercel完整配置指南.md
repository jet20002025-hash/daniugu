# 🚀 Vercel 完整配置指南

## 📋 配置前检查清单

- [x] ✅ `vercel.json` 配置文件已就绪
- [x] ✅ `api/index.py` serverless 入口已就绪
- [x] ✅ `requirements.txt` 依赖文件已就绪
- [x] ✅ 代码已支持 Vercel 环境检测
- [ ] ⏳ 需要：Upstash Redis 凭证
- [ ] ⏳ 需要：在 Vercel 创建项目
- [ ] ⏳ 需要：配置环境变量

---

## 🔧 第一步：获取 Upstash Redis 凭证

### 1.1 创建 Upstash Redis 数据库

1. **访问 Upstash**
   - 打开 https://upstash.com
   - 使用 GitHub 账号登录（推荐）或注册账号

2. **创建数据库**
   - 点击 **"Create Database"**
   - **Name**: `daniugu-redis`（或任意名称）
   - **Type**: 选择 **"Regional"**（推荐）或 **"Global"**
   - **Region**: 选择 **"ap-southeast-1"**（新加坡，离中国最近）或 **"us-east-1"**（美国东部）
   - 点击 **"Create"**

3. **获取 REST API 凭证**
   - 创建完成后，进入数据库详情页
   - 找到 **"REST API"** 部分
   - 复制以下信息：
     - **UPSTASH_REDIS_REST_URL**: `https://xxx.upstash.io`
     - **UPSTASH_REDIS_REST_TOKEN**: `xxx...`（长字符串）

**⚠️ 重要**：保存好这两个值，下一步需要用到！

---

## 🚀 第二步：在 Vercel 创建项目

### 2.1 登录 Vercel

1. **访问 Vercel**
   - 打开 https://vercel.com
   - 点击 **"Sign Up"** 或 **"Log In"**
   - 选择 **"Continue with GitHub"**（推荐）
   - 授权 Vercel 访问你的 GitHub 账号

### 2.2 导入项目

1. **创建新项目**
   - 登录后，点击 **"Add New..."** → **"Project"**
   - 在 **"Import Git Repository"** 中找到 `jet20002025-hash/daniugu`
   - 如果看不到仓库，点击 **"Adjust GitHub App Permissions"** 授权

2. **配置项目**
   - **Framework Preset**: 选择 **"Other"** 或让 Vercel 自动检测
   - **Root Directory**: 留空（使用根目录）
   - **Build Command**: 留空（Python 项目不需要构建）
   - **Output Directory**: 留空
   - **Install Command**: `pip install -r requirements.txt`（Vercel 会自动检测）

3. **环境变量配置**（先跳过，下一步详细配置）
   - 暂时不添加环境变量
   - 点击 **"Deploy"** 先完成首次部署

### 2.3 等待首次部署完成

- 部署通常需要 2-5 分钟
- 部署完成后会得到一个地址：`https://daniugu.vercel.app`
- **注意**：首次部署可能会失败（因为缺少环境变量），这是正常的

---

## ⚙️ 第三步：配置环境变量

### 3.1 进入环境变量设置

1. **在 Vercel Dashboard**
   - 进入你的项目
   - 点击顶部菜单 **"Settings"**
   - 点击左侧菜单 **"Environment Variables"**

### 3.2 添加必需的环境变量

按照以下顺序添加环境变量：

#### 1. Upstash Redis URL

- **Key**: `UPSTASH_REDIS_REST_URL`
- **Value**: `https://xxx.upstash.io`（从 Upstash 复制的 URL）
- **Environment**: 选择 **"Production, Preview, Development"**（全部环境）
- 点击 **"Save"**

#### 2. Upstash Redis Token

- **Key**: `UPSTASH_REDIS_REST_TOKEN`
- **Value**: `xxx...`（从 Upstash 复制的 Token）
- **Environment**: 选择 **"Production, Preview, Development"**（全部环境）
- 点击 **"Save"**

#### 3. 邀请码

- **Key**: `INVITE_CODES`
- **Value**: `ADMIN2024,VIP2024`（用逗号分隔，可以添加更多）
- **Environment**: 选择 **"Production, Preview, Development"**（全部环境）
- 点击 **"Save"**

#### 4. Flask Secret Key（推荐）

- **Key**: `FLASK_SECRET_KEY`
- **Value**: 生成一个随机字符串（可以使用在线工具或运行 `python -c "import secrets; print(secrets.token_hex(32))"`）
- **Environment**: 选择 **"Production, Preview, Development"**（全部环境）
- 点击 **"Save"**

**示例 Secret Key**（不要使用这个，生成你自己的）：
```
a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6
```

### 3.3 可选环境变量

如果需要，可以添加：

- **PYTHON_VERSION**: `3.9`（通常不需要，Vercel 会自动检测）

---

## 🔄 第四步：重新部署

### 4.1 触发重新部署

配置环境变量后，需要重新部署使环境变量生效：

1. **方式一：手动重新部署**（推荐）
   - 在 Vercel Dashboard → **"Deployments"**
   - 找到最新的部署
   - 点击右侧的 **"..."** → **"Redeploy"**
   - 确认重新部署

2. **方式二：推送代码触发**
   ```bash
   git commit --allow-empty -m "触发重新部署以应用环境变量"
   git push origin main
   ```

### 4.2 等待部署完成

- 重新部署通常需要 2-5 分钟
- 查看部署日志，确认没有错误

---

## ✅ 第五步：测试部署

### 5.1 健康检查

访问健康检查端点：
```
https://daniugu.vercel.app/api/health
```

应该返回：
```json
{
  "success": true,
  "status": "ok",
  "environment": "vercel",
  "analyzer_initialized": false
}
```

### 5.2 测试主页

访问：
```
https://daniugu.vercel.app
```

应该能看到登录页面。

### 5.3 测试注册和登录

1. **注册账号**
   - 访问 `https://daniugu.vercel.app/register`
   - 使用邀请码 `ADMIN2024` 注册
   - 填写用户名、邮箱、密码

2. **登录**
   - 访问 `https://daniugu.vercel.app/login`
   - 使用刚注册的账号登录

### 5.4 测试扫描功能

1. **登录后**
   - 进入主页
   - 点击 **"扫描所有股票"**
   - 观察是否正常启动（Vercel 会使用分批处理）

---

## 🌐 第六步：配置自定义域名（可选）

### 6.1 在 Vercel 添加域名

1. **进入域名设置**
   - Vercel Dashboard → 你的项目 → **"Settings"** → **"Domains"**

2. **添加域名**
   - 点击 **"Add Domain"**
   - 输入 `daniugu.online` 或 `www.daniugu.online`
   - 点击 **"Add"**

3. **获取 DNS 配置**
   - Vercel 会显示需要配置的 DNS 记录
   - 通常是 CNAME 记录：
     - **Type**: CNAME
     - **Name**: @ 或 www
     - **Value**: `cname.vercel-dns.com`

### 6.2 配置 DNS（在 Cloudflare 或阿里云）

#### 方式一：使用 Cloudflare（推荐）

1. **在 Cloudflare 添加域名**
   - 登录 https://dash.cloudflare.com
   - 点击 **"Add a Site"**
   - 输入 `daniugu.online`
   - 选择免费计划

2. **配置 DNS 记录**
   - 进入 **"DNS"** → **"Records"**
   - 添加 CNAME 记录：
     ```
     Type: CNAME
     Name: www
     Target: cname.vercel-dns.com
     Proxy status: 🟠 Proxied（橙色云朵）
     TTL: Auto
     ```
   - 点击 **"Save"**

3. **等待生效**
   - DNS 解析：5-30 分钟
   - SSL 证书：几分钟到几小时

#### 方式二：使用阿里云 DNS

1. **登录阿里云控制台**
   - 进入 **"域名"** → **"域名解析"**
   - 选择 `daniugu.online`

2. **添加 CNAME 记录**
   ```
   记录类型: CNAME
   主机记录: www
   记录值: cname.vercel-dns.com
   TTL: 600
   ```

3. **等待生效**
   - DNS 解析：5-30 分钟

---

## 📊 第七步：验证配置

### 7.1 检查清单

- [ ] ✅ 健康检查端点正常：`/api/health`
- [ ] ✅ 主页可以访问
- [ ] ✅ 注册功能正常（使用邀请码）
- [ ] ✅ 登录功能正常
- [ ] ✅ 扫描功能正常启动（分批处理）
- [ ] ✅ Redis 连接正常（用户数据能保存）
- [ ] ✅ 自定义域名配置（如果配置了）

### 7.2 查看日志

如果遇到问题，查看 Vercel 日志：

1. **在 Vercel Dashboard**
   - 进入项目 → **"Deployments"** → 最新部署
   - 点击 **"Function Logs"**
   - 查看错误信息

2. **常见错误**
   - Redis 连接失败：检查环境变量是否正确
   - 导入错误：检查 `requirements.txt` 是否完整
   - 超时错误：正常，Vercel 免费版有 10 秒限制

---

## 🐛 常见问题排查

### 问题 1: 部署失败

**症状**：部署日志显示错误

**排查步骤**：
1. 查看 Function Logs 中的错误信息
2. 检查 `requirements.txt` 是否包含所有依赖
3. 确认 `api/index.py` 路径正确
4. 检查环境变量是否配置

### 问题 2: Redis 连接失败

**症状**：用户注册/登录失败，日志显示 Redis 错误

**排查步骤**：
1. 检查 `UPSTASH_REDIS_REST_URL` 是否正确
2. 检查 `UPSTASH_REDIS_REST_TOKEN` 是否正确
3. 确认 Upstash Redis 数据库状态正常
4. 检查网络连接（Vercel 到 Upstash）

### 问题 3: 扫描超时

**症状**：扫描任务超过 10 秒后失败

**说明**：
- ✅ **这是正常的**，Vercel 免费版有 10 秒限制
- ✅ 系统已实现分批处理，会自动拆分任务
- ✅ 前端会轮询查询进度

**如果经常超时**：
- 考虑升级到 Vercel Pro（60 秒限制，$20/月）
- 或确保使用缓存，避免直接调用 API

### 问题 4: 环境变量未生效

**症状**：配置环境变量后，应用仍使用旧值

**解决方案**：
1. 确认环境变量已保存
2. 重新部署项目（Redeploy）
3. 检查环境变量作用域（Production/Preview/Development）

---

## 📝 环境变量完整列表

### 必需的环境变量

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST URL | `https://xxx.upstash.io` |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST Token | `xxx...` |
| `INVITE_CODES` | 邀请码列表（逗号分隔） | `ADMIN2024,VIP2024` |

### 推荐的环境变量

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `FLASK_SECRET_KEY` | Flask 会话密钥 | 随机字符串（32+ 字符） |

### 可选的环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `PYTHON_VERSION` | Python 版本 | 自动检测 |

---

## 🎯 快速配置命令

如果需要快速测试，可以使用以下命令：

```bash
# 1. 检查代码状态
git status

# 2. 提交代码（如果有更改）
git add .
git commit -m "准备部署到 Vercel"
git push origin main

# 3. 测试健康检查（部署后）
curl https://daniugu.vercel.app/api/health
```

---

## 📚 相关文档

- **详细配置说明**: `Vercel部署配置说明.md`
- **环境变量配置**: `Vercel环境变量配置指南.md`
- **故障排除**: `Vercel错误调试指南.md`
- **分批处理说明**: `VERCEL分批扫描说明.md`

---

## ✅ 配置完成检查清单

- [ ] Upstash Redis 数据库已创建
- [ ] Redis 凭证已获取
- [ ] Vercel 项目已创建
- [ ] 环境变量已配置（Redis、邀请码、Secret Key）
- [ ] 项目已重新部署
- [ ] 健康检查通过：`/api/health`
- [ ] 注册功能正常
- [ ] 登录功能正常
- [ ] 扫描功能正常
- [ ] 自定义域名已配置（如果配置了）

---

**配置完成后，你的应用就可以在 Vercel 上运行了！** 🎉

如有问题，请查看 Vercel Dashboard 中的日志，或参考相关文档。
