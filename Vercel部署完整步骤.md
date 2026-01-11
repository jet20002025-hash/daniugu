# 🚀 Vercel 部署完整步骤 - daniugu.online

## 📋 当前状态

- ✅ 代码已推送到 GitHub: https://github.com/jet20002025-hash/daniugu
- ✅ 会员系统已配置
- ⏳ 待完成：Vercel 部署和域名配置

## 🎯 部署步骤

### 第一步：在 Vercel 部署项目

#### 1.1 登录 Vercel

1. 访问 [vercel.com](https://vercel.com)
2. 点击 **"Sign Up"** 或 **"Log In"**
3. 选择 **"Continue with GitHub"**
4. 授权 Vercel 访问你的 GitHub 账号

#### 1.2 导入项目

1. 登录后，点击 **"Add New..."** → **"Project"**
2. 在 **"Import Git Repository"** 中找到 `jet20002025-hash/daniugu`
3. 如果看不到仓库，点击 **"Adjust GitHub App Permissions"** 授权

#### 1.3 配置项目

Vercel 会自动检测到 `vercel.json` 配置，但需要确认：

- **Framework Preset**: 选择 **"Other"** 或让 Vercel 自动检测
- **Root Directory**: 留空（使用根目录）
- **Build Command**: 留空（Python 项目不需要构建）
- **Output Directory**: 留空
- **Install Command**: `pip install -r requirements.txt`

#### 1.4 环境变量（可选）

如果需要，可以添加环境变量：
- `PYTHON_VERSION=3.9`（通常不需要，vercel.json 已配置）

#### 1.5 部署

1. 点击 **"Deploy"**
2. 等待部署完成（通常 2-5 分钟）
3. 部署完成后会得到一个地址：`https://你的项目名.vercel.app`
4. **记下这个地址**，后续配置域名需要

### 第二步：在 Vercel 添加自定义域名

#### 2.1 添加域名

1. 在 Vercel Dashboard 中，进入你的项目
2. 点击顶部菜单 **"Settings"**
3. 点击左侧菜单 **"Domains"**
4. 点击 **"Add Domain"**
5. 输入 `daniugu.online`
6. 点击 **"Add"**

#### 2.2 获取 DNS 配置

Vercel 会显示需要配置的 DNS 记录：
- **类型**: CNAME
- **名称**: @
- **值**: `cname.vercel-dns.com`

**记下这个信息**，下一步在 Cloudflare 中配置。

### 第三步：配置 Cloudflare

#### 3.1 在 Cloudflare 添加域名

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com)
2. 点击 **"Add a Site"**
3. 输入 `daniugu.online`
4. 选择 **免费计划**（Free）
5. 点击 **"Continue"**

#### 3.2 获取 Cloudflare DNS 服务器

Cloudflare 会显示两个 DNS 服务器地址，例如：
- `tess.ns.cloudflare.com`
- `[第二个 DNS 服务器地址]`

**记下这两个地址**。

#### 3.3 在阿里云修改 DNS 服务器

1. 登录 [阿里云控制台](https://ecs.console.aliyun.com)
2. 进入 **域名** → **域名解析**
3. 找到 `daniugu.online`
4. 点击 **"修改 DNS 服务器"**
5. 将阿里云的 DNS 服务器替换为 Cloudflare 提供的两个地址
6. 点击 **"确认"** 保存

#### 3.4 在 Cloudflare 配置 DNS 记录

1. 回到 Cloudflare Dashboard
2. 进入 **DNS** → **Records**
3. 删除默认的记录（如果有）
4. 添加 CNAME 记录：
   - **Type**: CNAME
   - **Name**: @
   - **Target**: `cname.vercel-dns.com`
   - **Proxy status**: 🟠 **Proxied**（橙色云朵，重要！）
   - **TTL**: Auto
5. 点击 **"Save"**

6. （可选）添加 www 子域名：
   - **Type**: CNAME
   - **Name**: www
   - **Target**: `cname.vercel-dns.com`
   - **Proxy status**: 🟠 **Proxied**
   - **TTL**: Auto
   - 点击 **"Save"**

#### 3.5 配置 SSL/TLS

1. 在 Cloudflare Dashboard 中，点击 **SSL/TLS**
2. 选择 **"Full"** 模式
3. 点击 **"Edge Certificates"** 标签
4. 启用 **"Always Use HTTPS"**

### 第四步：等待生效

1. **DNS 服务器更改**：需要 1-24 小时生效（通常 1-2 小时）
2. **DNS 记录生效**：通常几分钟到几小时
3. **SSL 证书**：Cloudflare 自动配置，通常几分钟

### 第五步：验证

1. **检查 Vercel 域名状态**
   - 在 Vercel Dashboard → Domains
   - 应该显示 **"Valid Configuration"**

2. **访问网站**
   - http://daniugu.online
   - https://daniugu.online

3. **检查 SSL**
   - 浏览器地址栏应该显示 🔒 锁图标
   - URL 应该是 `https://`

## ⚠️ 重要注意事项

### Vercel 限制

1. **执行时间限制**：
   - Hobby（免费）：10秒
   - Pro（$20/月）：60秒 ⭐ 推荐
   - Enterprise：300秒

2. **文件系统限制**：
   - Vercel 的 serverless 函数使用只读文件系统
   - `users.json` 和 `invite_codes.json` 无法写入
   - **需要修改为使用数据库或 Vercel KV**

### 解决方案

#### 方案一：使用 Vercel KV（推荐）

1. 在 Vercel Dashboard 添加 Vercel KV
2. 修改 `user_auth.py` 使用 KV 存储

#### 方案二：使用外部数据库

- Upstash Redis（免费额度）
- Supabase（PostgreSQL，免费额度）
- MongoDB Atlas（免费额度）

#### 方案三：暂时使用环境变量

- 将邀请码存储在环境变量中
- 用户数据使用 session（临时）

## 📝 部署检查清单

- [ ] 代码已推送到 GitHub
- [ ] 在 Vercel 创建项目并部署
- [ ] 在 Vercel 添加域名 `daniugu.online`
- [ ] 在 Cloudflare 添加域名
- [ ] 在阿里云修改 DNS 服务器为 Cloudflare
- [ ] 在 Cloudflare 配置 CNAME 记录指向 Vercel
- [ ] 启用 Cloudflare 代理（🟠 Proxied）
- [ ] 配置 SSL/TLS 为 "Full" 模式
- [ ] 等待 DNS 生效
- [ ] 验证网站可以访问
- [ ] 验证 HTTPS 正常工作
- [ ] 测试登录/注册功能
- [ ] 配置数据存储（KV 或数据库）

## 🔄 后续优化

1. **数据存储**：迁移到 Vercel KV 或数据库
2. **性能优化**：使用缓存减少 API 调用
3. **监控**：配置错误监控和日志
4. **备份**：定期备份用户数据

---

**按照以上步骤操作，完成后访问 https://daniugu.online 即可使用！**





