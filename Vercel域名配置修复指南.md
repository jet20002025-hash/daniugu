# 🔧 Vercel 域名配置修复指南

## ❌ 当前问题

域名 `daniugu.online` 显示 **"Invalid Configuration"（无效配置）**。

**当前配置**：
- DNS 记录类型：A 记录
- DNS 记录值：216.198.79.1
- Proxy 状态：Disabled（未启用代理）
- 重定向：308 重定向到 www.daniugu.online

## ✅ 解决方案

### 方案一：使用 CNAME 记录（推荐，适合 Cloudflare）

如果使用 Cloudflare 作为 DNS 提供商，应该使用 **CNAME 记录**，而不是 A 记录。

#### 步骤 1：在 Cloudflare 修改 DNS 记录

1. **登录 Cloudflare Dashboard**
   - 访问 [Cloudflare Dashboard](https://dash.cloudflare.com)
   - 选择域名 `daniugu.online`

2. **删除现有的 A 记录**
   - 进入 **DNS** → **Records**
   - 找到类型为 **A**、名称为 **@** 的记录
   - 点击该记录右侧的 **"..."** 菜单 → **"Delete"**
   - 确认删除

3. **添加 CNAME 记录**
   - 点击 **"Add record"**
   - 配置如下：
     ```
     Type: CNAME
     Name: @
     Target: cname.vercel-dns.com
     Proxy status: 🟠 Proxied（橙色云朵，启用代理）
     TTL: Auto
     ```
   - 点击 **"Save"**

4. **添加 www 子域名（可选）**
   - 点击 **"Add record"**
   - 配置如下：
     ```
     Type: CNAME
     Name: www
     Target: cname.vercel-dns.com
     Proxy status: 🟠 Proxied（橙色云朵）
     TTL: Auto
     ```
   - 点击 **"Save"**

#### 步骤 2：在 Vercel 验证

1. **回到 Vercel Dashboard**
   - 进入项目 → **Settings** → **Domains**
   - 找到 `daniugu.online`

2. **刷新域名状态**
   - 点击 **"Refresh"** 按钮
   - 或者等待几分钟让 Vercel 自动检测

3. **等待验证**
   - DNS 记录更改通常需要 **5-30 分钟** 生效
   - Vercel 会自动验证配置
   - 状态会从 **"Invalid Configuration"** 变为 **"Valid Configuration"**

### 方案二：使用 A 记录（如果必须使用 A 记录）

如果必须使用 A 记录，需要在 Cloudflare 启用代理：

1. **在 Cloudflare 修改 A 记录**
   - 进入 **DNS** → **Records**
   - 找到 A 记录（名称为 @，值为 216.198.79.1）
   - 点击 **"Edit"**
   - 将 **Proxy status** 改为 **🟠 Proxied**（橙色云朵）
   - 点击 **"Save"**

2. **配置 SSL/TLS**
   - 进入 **SSL/TLS** 设置
   - 选择 **"Full"** 模式
   - 确保 **"Always Use HTTPS"** 已启用

3. **在 Vercel 刷新**
   - 回到 Vercel Dashboard
   - 点击 **"Refresh"** 按钮
   - 等待验证完成

## 🔍 验证配置

### 1. 检查 DNS 解析

在终端执行：

```bash
# 检查 CNAME 记录
dig daniugu.online CNAME

# 检查 A 记录
dig daniugu.online A
```

**应该看到**：
- 如果使用 CNAME：指向 `cname.vercel-dns.com`
- 如果使用 A 记录：指向 Vercel 的 IP 地址（如 216.198.79.1）

### 2. 检查 Cloudflare 代理状态

在 Cloudflare Dashboard → DNS → Records：
- 记录旁边应该有 **🟠 橙色云朵**（表示代理已启用）
- 如果是 **⚪ 灰色云朵**，说明代理未启用

### 3. 检查网站访问

等待 DNS 生效后（5-30 分钟），访问：
- `https://daniugu.online`
- `https://www.daniugu.online`

应该能看到你的网站。

## ⚠️ 重要提示

### 使用 Cloudflare 时：

1. **推荐使用 CNAME 记录**
   - CNAME 记录更适合 Cloudflare 和 Vercel
   - 当 Vercel 更改 IP 地址时，CNAME 会自动更新
   - A 记录需要手动更新 IP 地址

2. **必须启用代理**
   - 如果使用 A 记录，必须启用 Cloudflare 代理（🟠 Proxied）
   - 否则 Vercel 无法正确验证域名

3. **SSL/TLS 配置**
   - 必须设置为 **"Full"** 模式
   - 确保 **"Always Use HTTPS"** 已启用

## 📝 配置检查清单

- [ ] 在 Cloudflare 删除现有的 A 记录（如果存在）
- [ ] 在 Cloudflare 添加 CNAME 记录：
  - [ ] Type: CNAME
  - [ ] Name: @
  - [ ] Target: cname.vercel-dns.com
  - [ ] Proxy status: 🟠 Proxied（已启用）
- [ ] 在 Cloudflare 配置 SSL/TLS 为 "Full" 模式
- [ ] 在 Vercel Dashboard 点击 "Refresh" 刷新域名状态
- [ ] 等待 DNS 生效（5-30 分钟）
- [ ] 验证 Vercel 域名状态变为 "Valid Configuration"
- [ ] 验证网站可以正常访问

## 🐛 常见问题

### 问题 1: 状态仍然是 "Invalid Configuration"

**解决**：
- 等待更长时间（最长 30 分钟）
- 确认 DNS 记录已正确配置
- 确认 Cloudflare 代理已启用
- 在 Vercel 点击 "Refresh" 按钮
- 清除浏览器缓存

### 问题 2: 网站无法访问

**解决**：
- 检查 Cloudflare DNS 记录是否正确
- 检查 Cloudflare 代理是否启用
- 检查 Vercel 部署是否成功
- 检查 SSL/TLS 配置是否为 "Full" 模式

### 问题 3: SSL 证书错误

**解决**：
- 确保 Cloudflare SSL/TLS 设置为 "Full" 模式
- 等待 SSL 证书自动配置（通常几分钟）
- 检查 Vercel 域名状态

---

**按照上述步骤操作，域名配置应该会变为 "Valid Configuration"！**

