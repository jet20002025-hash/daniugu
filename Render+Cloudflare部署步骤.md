# Render + Cloudflare CDN 部署步骤（方案1）

## 📋 部署前准备

### 1. 确认代码已准备好

- ✅ `Procfile` 已创建
- ✅ `bull_stock_web.py` 已支持 PORT 环境变量
- ✅ `bull_stock_web.py` 已支持 Render 环境检测
- ✅ `requirements.txt` 已准备

### 2. 准备环境变量

需要准备的环境变量：
- `UPSTASH_REDIS_REST_URL` - Upstash Redis REST URL
- `UPSTASH_REDIS_REST_TOKEN` - Upstash Redis REST Token
- `INVITE_CODES` - 邀请码（可选）
- `VIP_ALIPAY_ACCOUNT` - VIP支付账号（可选）

### 3. 准备域名（如果需要自定义域名）

- 如果没有域名，可以先使用 Render 提供的免费域名（`.onrender.com`）
- 如果有域名（如 `daniugu.online`），可以后续配置 Cloudflare CDN

---

## 🚀 第一步：部署到 Render

### 步骤 1.1：推送到 GitHub

```bash
cd /Users/zwj/股票分析
git add .
git commit -m "添加Render部署支持（支持PORT环境变量和Render环境检测）"
git push origin main
```

### 步骤 1.2：创建 Render 账号

1. **访问 Render**
   - 打开 https://render.com
   - 点击 **"Get Started for Free"**

2. **使用 GitHub 登录（推荐）**
   - 点击 **"Continue with GitHub"**
   - 授权 Render 访问你的 GitHub 账号

### 步骤 1.3：创建 Web 服务

1. **进入 Dashboard**
   - 登录后，点击 **"New +"** → **"Web Service"**

2. **连接 GitHub 仓库**
   - 如果还没连接，点击 **"Connect GitHub"**
   - 授权 Render 访问你的仓库
   - 选择你的仓库（如 `jet20002025-hash/daniugu`）

3. **配置服务**
   - **Name**: `daniugu`（或你喜欢的名称）
   - **Region**: 选择 `Singapore`（离中国最近）或 `Oregon`（美国）
   - **Branch**: `main`（或你的主分支）
   - **Root Directory**: 留空（使用根目录）

### 步骤 1.4：配置构建和启动

1. **Environment**: 选择 `Python 3`
2. **Build Command**: `pip install -r requirements.txt`
3. **Start Command**: 留空（Render 会自动使用 `Procfile`）

### 步骤 1.5：配置环境变量（重要！）

点击 **"Advanced"** → **"Add Environment Variable"**，添加以下变量：

#### 必需的环境变量：

1. **UPSTASH_REDIS_REST_URL**
   - Key: `UPSTASH_REDIS_REST_URL`
   - Value: 你的 Upstash Redis REST URL（例如：`https://xxx.upstash.io`）

2. **UPSTASH_REDIS_REST_TOKEN**
   - Key: `UPSTASH_REDIS_REST_TOKEN`
   - Value: 你的 Upstash Redis REST Token

#### 可选的环境变量：

3. **INVITE_CODES**（邀请码）
   - Key: `INVITE_CODES`
   - Value: `ADMIN2024,VIP2024`（用逗号分隔）

4. **VIP_ALIPAY_ACCOUNT**（VIP支付账号）
   - Key: `VIP_ALIPAY_ACCOUNT`
   - Value: `522168878@qq.com`

5. **VIP_WECHAT_ACCOUNT**（VIP微信账号，可选）
   - Key: `VIP_WECHAT_ACCOUNT`
   - Value: 你的微信账号

6. **PYTHON_VERSION**（Python版本，可选）
   - Key: `PYTHON_VERSION`
   - Value: `3.9`（或你需要的版本）

### 步骤 1.6：部署

1. 点击 **"Create Web Service"**
2. 等待部署完成（通常 3-5 分钟）
3. 部署完成后，你会得到一个地址：`https://你的服务名.onrender.com`

### 步骤 1.7：测试部署

1. **访问服务地址**
   - 打开 `https://你的服务名.onrender.com`
   - 确认可以正常访问

2. **查看日志**
   - 在 Render Dashboard → **"Logs"** 标签
   - 查看应用是否正常启动
   - 确认没有错误

3. **测试功能**
   - 测试登录/注册功能
   - 测试主要功能

---

## 🌐 第二步：配置自定义域名（可选）

如果你有域名（如 `daniugu.online`），可以配置自定义域名。

### 步骤 2.1：在 Render 添加域名

1. **进入服务设置**
   - 在 Render Dashboard，进入你的 Web 服务
   - 点击 **"Settings"** 标签

2. **添加自定义域名**
   - 滚动到 **"Custom Domains"** 部分
   - 点击 **"Add Custom Domain"**
   - 输入你的域名（如 `daniugu.online`）
   - 点击 **"Add"**

3. **获取 DNS 配置信息**
   - Render 会显示需要配置的 DNS 记录
   - 通常是 CNAME 记录：`cname.vercel-dns.com` 或类似的值
   - **记下这个信息**，下一步在 Cloudflare 中配置

---

## 🚀 第三步：配置 Cloudflare CDN（推荐）

### 步骤 3.1：在 Cloudflare 添加域名

1. **登录 Cloudflare**
   - 访问 https://dash.cloudflare.com
   - 使用你的账号登录（如果没有账号，先注册）

2. **添加站点**
   - 点击 **"Add a Site"**
   - 输入你的域名（如 `daniugu.online`）
   - 点击 **"Add Site"**

3. **选择计划**
   - 选择 **"Free"** 计划（免费版足够使用）
   - 点击 **"Continue"**

### 步骤 3.2：获取 Cloudflare DNS 服务器地址

1. **查看 DNS 服务器地址**
   - Cloudflare 会提供两个 DNS 服务器地址，例如：
     - `xxx.ns.cloudflare.com`
     - `yyy.ns.cloudflare.com`
   - **记下这两个地址**，下一步需要在域名注册商修改

### 步骤 3.3：在域名注册商修改 DNS 服务器

1. **登录域名注册商**（如阿里云）
   - 进入域名管理控制台
   - 找到你的域名

2. **修改 DNS 服务器**
   - 点击 **"DNS 服务器"** 或 **"Nameservers"**
   - 将现有的 DNS 服务器替换为 Cloudflare 提供的地址
   - 保存

3. **等待生效**
   - DNS 服务器更改通常需要 **24-48 小时** 完全生效
   - 但通常 **1-2 小时** 内就会开始工作

### 步骤 3.4：在 Cloudflare 配置 DNS 记录

1. **等待 DNS 服务器生效**
   - 等待 Cloudflare 检测到 DNS 服务器更改（通常几分钟到几小时）

2. **添加 DNS 记录**
   - 在 Cloudflare Dashboard，进入你的域名
   - 点击 **"DNS"** → **"Records"**
   - 点击 **"Add record"**

3. **配置 CNAME 记录（根域名）**
   - **Type**: `CNAME`
   - **Name**: `@`（或你的域名）
   - **Target**: 使用 Render 提供的 CNAME 值（通常在 Render Dashboard → Settings → Custom Domains 中显示）
   - **Proxy status**: 🟠 **Proxied**（橙色云朵，**启用代理，这是CDN加速的关键！**）
   - **TTL**: `Auto`
   - 点击 **"Save"**

4. **配置 CNAME 记录（www 子域名，可选）**
   - **Type**: `CNAME`
   - **Name**: `www`
   - **Target**: 与根域名相同的值
   - **Proxy status**: 🟠 **Proxied**（橙色云朵）
   - **TTL**: `Auto`
   - 点击 **"Save"**

### 步骤 3.5：配置 SSL/TLS

1. **进入 SSL/TLS 设置**
   - 在 Cloudflare Dashboard，点击 **"SSL/TLS"** 标签

2. **选择加密模式**
   - 选择 **"Full"** 模式（完全加密）
   - 这样 Cloudflare 和 Render 之间的连接也是加密的

3. **启用 Always Use HTTPS**
   - 滚动到 **"Always Use HTTPS"** 部分
   - 点击 **"On"**（启用）
   - 这样所有 HTTP 请求都会自动重定向到 HTTPS

### 步骤 3.6：优化设置（可选）

1. **启用 HTTP/2**
   - 在 **"Network"** 标签
   - 确认 **"HTTP/2"** 已启用（默认启用）

2. **启用压缩**
   - 在 **"Speed"** → **"Optimization"**
   - 确认 **"Auto Minify"** 已启用（可选）

3. **配置缓存规则（可选）**
   - 在 **"Caching"** → **"Configuration"**
   - 可以配置缓存规则以提高性能

### 步骤 3.7：等待生效并测试

1. **等待 DNS 生效**
   - 等待 DNS 记录生效（通常 5-30 分钟）
   - 可以在 Cloudflare Dashboard 查看状态

2. **测试访问**
   - 访问你的域名（如 `https://daniugu.online`）
   - 确认可以正常访问

3. **测试 CDN 加速**
   - 可以使用工具测试访问速度（如 https://www.webpagetest.org）
   - 对比使用 Cloudflare CDN 前后的速度

---

## ✅ 部署后检查清单

### Render 部署检查

- [ ] 代码已推送到 GitHub
- [ ] 在 Render 创建 Web 服务
- [ ] 配置环境变量（Redis URL 等）
- [ ] 部署成功
- [ ] 服务可以正常访问
- [ ] 日志中没有错误

### Cloudflare CDN 配置检查

- [ ] 在 Cloudflare 添加域名
- [ ] 在域名注册商修改 DNS 服务器
- [ ] DNS 服务器更改已生效
- [ ] 在 Cloudflare 配置 DNS 记录
- [ ] Proxy 状态设置为 🟠 **Proxied**（启用代理）
- [ ] SSL/TLS 模式设置为 **"Full"**
- [ ] Always Use HTTPS 已启用
- [ ] 域名可以正常访问
- [ ] HTTPS 正常工作

---

## 🔍 测试和监控

### 1. 功能测试

- [ ] 首页可以正常访问
- [ ] 登录/注册功能正常
- [ ] 主要功能正常
- [ ] 扫描功能可以正常使用（无超时）

### 2. 性能测试

- [ ] 页面加载速度测试
- [ ] API 响应速度测试
- [ ] 对比使用 Cloudflare CDN 前后的速度

### 3. 监控

- [ ] 在 Render Dashboard 查看服务状态
- [ ] 在 Cloudflare Dashboard 查看访问统计
- [ ] 监控错误日志
- [ ] 收集用户反馈

---

## 🐛 常见问题

### 问题 1：Render 部署失败

**可能原因**：
- 依赖安装失败
- 代码错误

**解决方法**：
1. 查看 Render Dashboard → Logs 中的错误信息
2. 检查 `requirements.txt` 是否正确
3. 检查代码是否有语法错误

### 问题 2：应用启动失败

**可能原因**：
- 环境变量缺失
- 端口配置错误

**解决方法**：
1. 确认环境变量已正确配置（特别是 Redis 相关）
2. 查看日志中的错误信息
3. 确认 `Procfile` 正确

### 问题 3：域名无法访问

**可能原因**：
- DNS 记录未生效
- Proxy 状态未启用

**解决方法**：
1. 等待 DNS 记录生效（5-30 分钟）
2. 确认 Proxy 状态为 🟠 **Proxied**（启用代理）
3. 检查 DNS 记录是否正确

### 问题 4：SSL 证书问题

**可能原因**：
- SSL/TLS 模式不正确
- DNS 记录未生效

**解决方法**：
1. 确认 SSL/TLS 模式为 **"Full"**
2. 等待 DNS 记录生效
3. 查看 Cloudflare Dashboard → SSL/TLS 中的状态

### 问题 5：访问速度仍然较慢

**可能原因**：
- Cloudflare CDN 未生效
- 服务器位置较远

**解决方法**：
1. 确认 Proxy 状态为 🟠 **Proxied**（启用代理）
2. 等待 CDN 缓存生效
3. 如果仍然较慢，考虑迁移到国内云服务

---

## 📊 方案优势

### Render + Cloudflare CDN 的优势

1. **免费使用**（免费版可用）
2. **CDN 加速**（改善访问速度）
3. **HTTPS 加密**（自动配置 SSL 证书）
4. **无执行时间限制**（最重要）
5. **配置简单**（无需修改代码）
6. **自动部署**（GitHub 推送后自动更新）

### 适用场景

- ✅ 测试阶段
- ✅ 初期使用
- ✅ 访问量不大的应用
- ✅ 预算有限的项目

---

## 💡 后续优化建议

1. **如果访问速度不满意**
   - 考虑迁移到国内云服务（阿里云等）

2. **如果稳定性有问题**
   - 考虑迁移到国内云服务
   - 或使用付费版 Render（$7/月，不会休眠）

3. **如果访问量增加**
   - 升级到付费版 Render
   - 或迁移到国内云服务

---

## ✅ 完成！

部署完成后，你的应用应该可以：
- ✅ 通过自定义域名访问（如果配置了）
- ✅ 使用 Cloudflare CDN 加速
- ✅ 自动 HTTPS 加密
- ✅ 无执行时间限制
- ✅ 免费使用（免费版）

如有问题，查看 Render Dashboard 和 Cloudflare Dashboard 中的日志和状态信息。

