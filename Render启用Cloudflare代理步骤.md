# 🚀 Render 启用 Cloudflare 代理（CDN）步骤

## ⚠️ 重要提示

**在启用 Cloudflare 代理之前，请确保：**

1. ✅ Render 的 SSL 证书已签发完成（Certificate Pending 变为 Certificate Active）
2. ✅ 域名可以正常访问（`https://www.daniugu.online` 和 `https://daniugu.online` 可以访问）
3. ✅ 域名在 Render Dashboard 显示 "Domain Verified" 和 "Certificate Active"

**如果 SSL 证书还未签发完成，请先等待证书签发完成后再启用 Cloudflare 代理。**

---

## 📋 启用 Cloudflare 代理的步骤

### 步骤 1：登录 Cloudflare Dashboard

1. **访问 Cloudflare Dashboard**
   - 访问：https://dash.cloudflare.com
   - 使用你的账号登录

2. **选择域名**
   - 在左侧菜单点击 **"Websites"**（网站）
   - 找到并点击 `daniugu.online`

---

### 步骤 2：启用 DNS 记录的代理

1. **进入 DNS 设置**
   - 点击左侧菜单 **"DNS"** → **"Records"**

2. **启用 www 子域名的代理**
   - 找到 `www` 的 CNAME 记录（内容为 `daniugu.onrender.com`）
   - 找到记录右侧的 **云朵图标**
   - 当前状态应该是 **⚪ 灰色云朵**（DNS only，仅 DNS）
   - **点击云朵图标**，将其变为 **🟠 橙色云朵**（Proxied，已代理）
   - 记录会自动保存

   **说明**：
   - ⚪ 灰色云朵 = DNS only（仅 DNS，不使用 CDN）
   - 🟠 橙色云朵 = Proxied（已代理，启用 CDN 加速）

3. **启用根域名的代理**
   - 找到 `daniugu.online` 或 `@` 的 A 记录（内容为 `216.24.57.1`）或 CNAME 记录（如果已改为 CNAME）
   - 找到记录右侧的 **云朵图标**
   - 当前状态应该是 **⚪ 灰色云朵**（DNS only，仅 DNS）
   - **点击云朵图标**，将其变为 **🟠 橙色云朵**（Proxied，已代理）
   - 记录会自动保存

   **注意**：
   - 如果根域名使用的是 A 记录，Cloudflare 仍然可以通过代理加速
   - 点击云朵图标后，Cloudflare 会自动处理代理

---

### 步骤 3：配置 SSL/TLS 设置

1. **进入 SSL/TLS 设置**
   - 点击左侧菜单 **"SSL/TLS"**

2. **选择加密模式**
   - 找到 **"SSL/TLS encryption mode"**（SSL/TLS 加密模式）
   - 当前可能是 **"Flexible"**（灵活）或 **"Full"**（完全）
   - **选择 "Full"**（完全加密）
   
   **说明**：
   - **"Flexible"**：Cloudflare 到浏览器加密，Cloudflare 到源服务器不加密（不推荐）
   - **"Full"**：全程加密，Cloudflare 到浏览器加密，Cloudflare 到源服务器也加密（推荐）
   - **"Full (strict)"**：全程加密并验证证书（如果 Render 证书已验证，可以使用此模式）

3. **启用 Always Use HTTPS**
   - 向下滚动，找到 **"Always Use HTTPS"** 部分
   - 如果显示 **"Off"**（关闭），点击开关将其变为 **"On"**（启用）
   
   **作用**：
   - 自动将所有 HTTP 请求重定向到 HTTPS
   - 确保所有访问都使用加密连接

---

### 步骤 4：验证配置

1. **等待 DNS 生效**
   - DNS 记录更改通常需要 **1-5 分钟** 生效
   - 可以在 Cloudflare Dashboard 查看状态

2. **测试访问**
   - 访问 `https://www.daniugu.online`
   - 访问 `https://daniugu.online`
   - 确认可以正常访问
   - 确认地址栏显示 HTTPS（绿色锁图标）

3. **验证 CDN 是否生效**
   - 在浏览器开发者工具（F12）中查看 **"Network"**（网络）标签
   - 刷新页面，查看请求的响应头
   - 如果看到 `cf-cache-status: HIT` 或 `cf-cache-status: MISS`，说明 CDN 已启用
   - 或者检查响应头中的 `server: cloudflare` 标识

---

## 📊 配置前后对比

### 配置前（仅 DNS，灰色云朵 ⚪）

- ✅ 域名可以正常访问
- ❌ 不使用 CDN 加速
- ❌ 访问速度较慢（直接访问 Render 服务器）
- ❌ 没有 DDoS 保护

### 配置后（已代理，橙色云朵 🟠）

- ✅ 域名可以正常访问
- ✅ 使用 Cloudflare CDN 加速（访问速度更快）
- ✅ 自动 DDoS 保护
- ✅ 自动缓存静态资源
- ✅ 全球 CDN 节点（加速访问）
- ✅ 更好的稳定性（Cloudflare 的全球网络）

---

## ⚠️ 注意事项

### 1. 启用代理后可能的问题

**问题 1：IP 地址变化**

启用 Cloudflare 代理后，访客看到的 IP 地址是 Cloudflare 的 IP，而不是 Render 的 IP。如果应用需要获取真实 IP，需要配置：

- 在 Cloudflare Dashboard → **"SSL/TLS"** → **"Edge Certificates"** → **"Always Use HTTPS"** 已启用
- 在应用代码中，从请求头 `CF-Connecting-IP` 或 `X-Forwarded-For` 获取真实 IP

**问题 2：SSL 证书验证**

- 如果使用 **"Full (strict)"** 模式，需要确保 Render 的 SSL 证书是有效的
- 如果证书有问题，建议使用 **"Full"** 模式

**问题 3：缓存问题**

- Cloudflare 会自动缓存静态资源（CSS、JS、图片等）
- 如果更新了静态资源但未看到变化，可以：
  - 在 Cloudflare Dashboard → **"Caching"** → **"Configuration"** → **"Purge Everything"**（清除所有缓存）
  - 或者等待缓存过期（默认 TTL）

### 2. 何时禁用代理

如果需要禁用 Cloudflare 代理（回到仅 DNS 模式）：

1. 进入 Cloudflare Dashboard → **"DNS"** → **"Records"**
2. 找到对应的 DNS 记录
3. 点击 **🟠 橙色云朵**，将其变为 **⚪ 灰色云朵**
4. 记录会自动保存

---

## ✅ 配置检查清单

- [ ] Render SSL 证书已签发完成
- [ ] 域名可以正常访问
- [ ] 已登录 Cloudflare Dashboard
- [ ] 已选择域名 `daniugu.online`
- [ ] 已进入 DNS 设置（DNS → Records）
- [ ] `www` 的 CNAME 记录已启用代理（🟠 橙色云朵）
- [ ] 根域名的 A/CNAME 记录已启用代理（🟠 橙色云朵）
- [ ] SSL/TLS 模式已设置为 **"Full"** 或 **"Full (strict)"**
- [ ] Always Use HTTPS 已启用（On）
- [ ] 等待 1-5 分钟让配置生效
- [ ] 测试访问域名，确认可以正常访问
- [ ] 验证 CDN 是否生效（查看响应头）

---

## 🎉 完成！

配置完成后，你的应用现在使用 Cloudflare CDN 加速，访问速度会更快，特别是在中国大陆访问时。

**优势：**
- ✅ 更快的访问速度（全球 CDN 节点）
- ✅ 自动 DDoS 保护
- ✅ 自动缓存静态资源
- ✅ 更好的稳定性
- ✅ HTTPS 加密连接

如有问题，可以随时禁用代理（将橙色云朵改为灰色云朵），或者查看 Cloudflare Dashboard 中的日志和统计信息。

