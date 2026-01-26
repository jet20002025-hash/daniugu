# 🔧 Cloudflare Error 1000 修复指南

## ❌ 错误信息

```
Error 1000: DNS points to prohibited IP
DNS points to prohibited IP
```

**原因**：DNS 记录（通常是 A 记录）指向了 Cloudflare 禁止的 IP 地址。

---

## ✅ 解决方案

### 步骤 1：检查当前 DNS 记录

1. **登录 Cloudflare Dashboard**
   - 访问：https://dash.cloudflare.com
   - 选择域名 `daniugu.online`

2. **进入 DNS 设置**
   - 点击左侧菜单 **"DNS"** → **"Records"**

3. **检查所有记录**
   - 查看是否有 A 记录指向以下 IP：
     - `192.0.2.1` 或 `192.0.2.x`（Cloudflare 保留 IP）
     - `104.21.x.x` 或 `172.67.x.x`（Cloudflare 自己的 IP）
     - 其他 Cloudflare 内部 IP

### 步骤 2：删除错误的 A 记录

**删除所有指向 Cloudflare 禁止 IP 的 A 记录：**

1. 找到所有类型为 **A** 的记录
2. 检查记录值（Target/Content）
3. 如果指向上述禁止的 IP，点击记录右侧的 **"Delete"**（删除）
4. 确认删除

### 步骤 3：配置正确的 CNAME 记录

**对于 `www.daniugu.online`：**

1. **检查是否已有 CNAME 记录**
   - 查找 Name 为 `www` 的记录
   - 如果存在但配置错误，点击 **"Edit"** 编辑
   - 如果不存在，点击 **"Add record"** 添加

2. **配置 CNAME 记录**
   ```
   Type: CNAME
   Name: www
   Target: cname.vercel-dns.com
   或
   Target: 0774abe293040a93.vercel-dns-017.com.
   （使用 Vercel Dashboard 中显示的地址）
   Proxy status: ⚪ DNS only（灰色云朵，禁用代理）
   或
   Proxy status: 🟠 Proxied（橙色云朵，启用代理）
   TTL: Auto
   ```

3. **点击 "Save" 保存**

**对于根域名 `daniugu.online`（可选）：**

1. **检查是否已有根域名记录**
   - 查找 Name 为 `@` 的记录

2. **如果存在错误的 A 记录，删除它**

3. **添加 CNAME 记录（如果 Cloudflare 支持）**
   ```
   Type: CNAME
   Name: @
   Target: cname.vercel-dns.com
   或
   Target: 0774abe293040a93.vercel-dns-017.com.
   Proxy status: ⚪ DNS only（灰色云朵）
   TTL: Auto
   ```

   **注意**：某些 DNS 提供商不支持根域名的 CNAME。如果 Cloudflare 不支持，可以：
   - 只配置 `www` 子域名
   - 或等待 Vercel 提供根域名的 A 记录配置

### 步骤 4：验证 Vercel 配置

1. **登录 Vercel Dashboard**
   - 访问：https://vercel.com/dashboard
   - 选择项目 `daniugu`

2. **检查域名配置**
   - 进入 **Settings** → **Domains**
   - 查看 `www.daniugu.online` 的状态
   - 查看 Vercel 显示的 DNS 配置要求

3. **使用 Vercel 提供的 DNS 地址**
   - Vercel Dashboard 会显示具体的 DNS 配置
   - 使用 Vercel 显示的 CNAME 地址（例如：`0774abe293040a93.vercel-dns-017.com.`）

### 步骤 5：等待 DNS 生效

- DNS 更改通常需要 **5-30 分钟** 生效
- 最长可能需要 **24 小时**（但通常很快）

### 步骤 6：验证修复

1. **检查 DNS 解析**
   ```bash
   # 检查 CNAME 记录
   dig www.daniugu.online CNAME
   
   # 或使用 nslookup
   nslookup www.daniugu.online
   ```

2. **访问网站**
   - 访问：https://www.daniugu.online
   - 应该不再显示 Error 1000

---

## 📋 正确的 DNS 配置示例

### ✅ 正确的配置

```
Type: CNAME
Name: www
Target: cname.vercel-dns.com
Proxy: ⚪ DNS only 或 🟠 Proxied
TTL: Auto
```

或使用 Vercel 提供的特定地址：

```
Type: CNAME
Name: www
Target: 0774abe293040a93.vercel-dns-017.com.
Proxy: ⚪ DNS only
TTL: Auto
```

### ❌ 错误的配置（会导致 Error 1000）

```
Type: A
Name: www
Target: 192.0.2.1（Cloudflare 禁止的 IP）
Proxy: 🟠 Proxied
```

```
Type: A
Name: @
Target: 104.21.8.79（Cloudflare 自己的 IP）
Proxy: 🟠 Proxied
```

---

## 🔍 常见问题

### Q1: 为什么不能使用 A 记录？

**A**: Vercel 使用动态 IP，不提供固定的 A 记录。必须使用 CNAME 记录指向 Vercel 的域名。

### Q2: 根域名（@）应该怎么配置？

**A**: 
- 如果 Cloudflare 支持根域名的 CNAME，使用 CNAME 记录
- 如果不支持，可以只配置 `www` 子域名，Vercel 会自动处理根域名重定向

### Q3: Proxy 状态应该选哪个？

**A**: 
- **DNS only（灰色云朵）**：直接解析到 Vercel，不经过 Cloudflare CDN
- **Proxied（橙色云朵）**：通过 Cloudflare CDN，提供加速和安全保护

**建议**：如果使用 Cloudflare，建议使用 **Proxied** 模式，但需要确保 SSL/TLS 设置为 "Full" 模式。

### Q4: 修改后多久生效？

**A**: 
- 通常 **5-30 分钟**
- 最长 **24 小时**（但很少见）
- 可以清除本地 DNS 缓存加速生效

---

## 🚀 快速修复步骤总结

1. ✅ 登录 Cloudflare Dashboard
2. ✅ 进入 DNS → Records
3. ✅ 删除所有指向禁止 IP 的 A 记录
4. ✅ 添加/编辑 CNAME 记录指向 `cname.vercel-dns.com` 或 Vercel 提供的地址
5. ✅ 确保 Proxy 状态正确
6. ✅ 等待 5-30 分钟让 DNS 生效
7. ✅ 访问网站验证

---

## 📞 需要帮助？

如果按照上述步骤仍然无法解决：

1. **检查 Vercel Dashboard** 显示的 DNS 配置要求
2. **截图 Cloudflare DNS 记录** 发送给我检查
3. **查看 Cloudflare 错误日志** 获取更多信息
