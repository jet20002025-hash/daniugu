# 🌐 Cloudflare DNS 配置步骤 - daniugu.online

## 📋 DNS 服务器信息

你提供的 Cloudflare DNS 服务器：
- `tess.ns.cloudflare.com`

**注意**：Cloudflare 通常提供两个 DNS 服务器地址。请检查 Cloudflare Dashboard 获取完整的两个地址。

## 🔧 配置步骤

### 第一步：在阿里云修改 DNS 服务器

1. **登录阿里云控制台**
   - 访问 [阿里云控制台](https://ecs.console.aliyun.com)
   - 使用你的账号登录

2. **进入域名管理**
   - 点击顶部菜单 **"产品与服务"** → **"域名"**
   - 或直接访问：https://dc.console.aliyun.com/next/index#/domain/list/all-domain

3. **选择域名**
   - 找到 `daniugu.online`
   - 点击域名进入管理页面

4. **修改 DNS 服务器**
   - 点击 **"DNS 修改"** 或 **"修改 DNS 服务器"**
   - 将阿里云的 DNS 服务器替换为 Cloudflare 提供的地址
   - 通常需要填写两个 DNS 服务器地址，例如：
     ```
     tess.ns.cloudflare.com
     [第二个 DNS 服务器地址]
     ```
   - 点击 **"确认"** 或 **"保存"**

5. **等待生效**
   - DNS 服务器更改通常需要 **1-24 小时** 生效
   - 但通常 **1-2 小时** 内就会开始工作

### 第二步：在 Cloudflare 配置 DNS 记录

1. **登录 Cloudflare Dashboard**
   - 访问 [Cloudflare Dashboard](https://dash.cloudflare.com)
   - 使用你的账号登录

2. **选择域名**
   - 在左侧菜单点击 **"Websites"**
   - 找到并点击 `daniugu.online`

3. **进入 DNS 设置**
   - 点击左侧菜单 **"DNS"** → **"Records"**

4. **删除现有记录（如果有）**
   - 删除之前配置的 A 记录（如果有）

5. **添加 CNAME 记录指向 Vercel**
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

6. **添加 www 子域名（可选）**
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

### 第三步：配置 SSL/TLS

1. **进入 SSL/TLS 设置**
   - 在 Cloudflare Dashboard 中，点击左侧菜单 **"SSL/TLS"**

2. **选择加密模式**
   - 选择 **"Full"** 模式
   - 这样 Cloudflare 和 Vercel 之间会使用 HTTPS

3. **启用 Always Use HTTPS**
   - 点击 **"Edge Certificates"** 标签
   - 找到 **"Always Use HTTPS"**
   - 点击开关启用

### 第四步：在 Vercel 添加域名

1. **登录 Vercel Dashboard**
   - 访问 [vercel.com/dashboard](https://vercel.com/dashboard)
   - 使用 GitHub 账号登录

2. **选择项目**
   - 找到你的项目（`daniugu` 或项目名称）
   - 点击进入项目

3. **添加域名**
   - 点击顶部菜单 **"Settings"**
   - 点击左侧菜单 **"Domains"**
   - 点击 **"Add Domain"**
   - 输入 `daniugu.online`
   - 点击 **"Add"**

4. **获取 DNS 配置信息**
   - Vercel 会显示需要配置的 DNS 记录
   - 通常是 CNAME 记录：`cname.vercel-dns.com`
   - 这个已经在 Cloudflare 中配置了

5. **等待验证**
   - Vercel 会自动验证域名配置
   - 状态会显示为 **"Valid Configuration"**
   - 通常需要几分钟到几小时

## ✅ 验证配置

### 1. 检查 DNS 解析

在终端执行：

```bash
# 检查 CNAME 记录
dig daniugu.online CNAME

# 或使用 nslookup
nslookup daniugu.online
```

应该看到指向 `cname.vercel-dns.com` 的记录。

### 2. 检查网站访问

等待 DNS 生效后（1-24 小时），访问：

- **HTTP**: http://daniugu.online
- **HTTPS**: https://daniugu.online（Cloudflare 会自动配置 SSL）

### 3. 检查 SSL 证书

访问网站时，浏览器地址栏应该显示：
- 🔒 锁图标
- `https://` 开头

## 📝 配置检查清单

- [ ] 在阿里云将 DNS 服务器改为 Cloudflare 提供的地址
- [ ] 在 Cloudflare 配置 CNAME 记录指向 `cname.vercel-dns.com`
- [ ] 启用 Cloudflare 代理（🟠 Proxied）
- [ ] 在 Cloudflare 配置 SSL/TLS 为 "Full" 模式
- [ ] 启用 "Always Use HTTPS"
- [ ] 在 Vercel 添加域名 `daniugu.online`
- [ ] 等待 DNS 生效（1-24 小时）
- [ ] 验证网站可以正常访问
- [ ] 验证 HTTPS 正常工作

## 🐛 常见问题

### 问题1: DNS 不生效

**解决**：
- 等待更长时间（最长 24 小时）
- 检查 DNS 服务器是否正确配置
- 清除本地 DNS 缓存：
  ```bash
  # macOS
  sudo dscacheutil -flushcache
  
  # Windows
  ipconfig /flushdns
  ```

### 问题2: SSL 证书错误

**解决**：
- 确保 Cloudflare SSL/TLS 设置为 "Full" 模式
- 等待 SSL 证书自动配置（通常几分钟）
- 检查 Vercel 域名状态是否为 "Valid Configuration"

### 问题3: 网站无法访问

**解决**：
- 检查 Vercel 部署是否成功
- 检查 Cloudflare DNS 记录是否正确
- 检查 Cloudflare 代理是否启用
- 查看 Vercel 和 Cloudflare 的日志

## 📞 需要帮助？

如果遇到问题：
1. 查看 Cloudflare Dashboard 的 DNS 记录
2. 查看 Vercel Dashboard 的域名状态
3. 使用 DNS 检查工具验证解析
4. 查看错误日志

---

**配置完成后，访问 https://daniugu.online 即可使用！**





