# 🌐 Render 自定义域名 DNS 配置指南

## 📋 当前状态

根据 Render Dashboard 显示，需要配置以下域名：
- `www.daniugu.online` - 需要 CNAME 记录
- `daniugu.online` - 需要 ANAME/ALIAS 记录（或 A 记录），会重定向到 `www.daniugu.online`

**状态**：两个域名都显示 "DNS update needed to verify domain ownership"（需要更新 DNS 以验证域名所有权）

---

## 🎯 需要配置的 DNS 记录

### 记录 1：www 子域名

**域名**：`www.daniugu.online`

**DNS 记录**：
```
Type: CNAME
Name: www
Target: daniugu.onrender.com
Proxy status: ⚪ DNS only（禁用代理，初始配置时）
TTL: Auto
```

### 记录 2：根域名

**域名**：`daniugu.online`

**方案一（推荐）**：使用 ANAME 或 ALIAS 记录
```
Type: ANAME 或 ALIAS（根据 DNS 提供商支持）
Name: @
Target: daniugu.onrender.com
Proxy status: ⚪ DNS only（禁用代理，初始配置时）
TTL: Auto
```

**方案二**：如果 DNS 提供商不支持 ANAME/ALIAS，使用 A 记录
```
Type: A
Name: @
Target: 216.24.57.1
Proxy status: ⚪ DNS only（禁用代理，初始配置时）
TTL: Auto
```

**注意**：`daniugu.online` 会自动重定向到 `www.daniugu.online`

---

## 🔧 配置步骤

### 方式一：直接在域名注册商配置（如果支持 ANAME/ALIAS）

如果你的域名注册商（如阿里云、腾讯云等）支持 ANAME/ALIAS 记录：

#### 1. 登录域名注册商

1. 登录你的域名注册商控制台（如阿里云、腾讯云、GoDaddy 等）
2. 进入域名管理页面
3. 找到 `daniugu.online` 域名

#### 2. 配置 www 子域名

1. 点击 **"DNS 解析"** 或 **"DNS 记录"**
2. 点击 **"添加记录"**
3. 配置如下：
   - **记录类型**：`CNAME`
   - **主机记录**：`www`
   - **记录值**：`daniugu.onrender.com`
   - **TTL**：`600`（或自动）
4. 点击 **"确认"** 或 **"保存"**

#### 3. 配置根域名

**如果支持 ANAME/ALIAS**：
1. 点击 **"添加记录"**
2. 配置如下：
   - **记录类型**：`ANAME` 或 `ALIAS`
   - **主机记录**：`@` 或留空
   - **记录值**：`daniugu.onrender.com`
   - **TTL**：`600`（或自动）
3. 点击 **"确认"** 或 **"保存"**

**如果不支持 ANAME/ALIAS，使用 A 记录**：
1. 点击 **"添加记录"**
2. 配置如下：
   - **记录类型**：`A`
   - **主机记录**：`@` 或留空
   - **记录值**：`216.24.57.1`
   - **TTL**：`600`（或自动）
3. 点击 **"确认"** 或 **"保存"**

---

### 方式二：使用 Cloudflare（推荐，支持更多功能）

如果你已经使用 Cloudflare 管理 DNS，或者想要使用 Cloudflare CDN 加速：

#### 步骤 1：在 Cloudflare 添加域名（如果还没有）

1. **登录 Cloudflare Dashboard**
   - 访问：https://dash.cloudflare.com
   - 使用你的账号登录（如果没有账号，先注册）

2. **添加站点**
   - 点击 **"Add a Site"**
   - 输入域名：`daniugu.online`
   - 点击 **"Add Site"**

3. **选择计划**
   - 选择 **"Free"** 计划（免费版足够使用）
   - 点击 **"Continue"**

4. **获取 DNS 服务器地址**
   - Cloudflare 会提供两个 DNS 服务器地址，例如：
     - `xxx.ns.cloudflare.com`
     - `yyy.ns.cloudflare.com`
   - **记下这两个地址**

5. **在域名注册商修改 DNS 服务器**
   - 登录域名注册商控制台
   - 进入域名管理 → DNS 服务器设置
   - 将 DNS 服务器改为 Cloudflare 提供的地址
   - 保存并等待生效（通常 1-24 小时）

#### 步骤 2：在 Cloudflare 配置 DNS 记录

1. **等待 DNS 服务器生效**
   - 等待 Cloudflare 检测到 DNS 服务器更改（通常几分钟到几小时）
   - 在 Cloudflare Dashboard 中，域名状态会变为 "Active"

2. **进入 DNS 设置**
   - 在 Cloudflare Dashboard，选择域名 `daniugu.online`
   - 点击左侧菜单 **"DNS"** → **"Records"**

3. **配置 www 子域名**
   - 点击 **"Add record"**
   - 配置如下：
     ```
     Type: CNAME
     Name: www
     Target: daniugu.onrender.com
     Proxy status: ⚪ DNS only（灰色云朵，初始配置时禁用代理）
     TTL: Auto
     ```
   - 点击 **"Save"**

4. **配置根域名**
   - 点击 **"Add record"**
   - 配置如下：
     ```
     Type: CNAME（Cloudflare 支持根域名的 CNAME）
     Name: @
     Target: daniugu.onrender.com
     Proxy status: ⚪ DNS only（灰色云朵，初始配置时禁用代理）
     TTL: Auto
     ```
   - 点击 **"Save"**

   **注意**：Cloudflare 支持根域名的 CNAME（通过 Flattening 技术），所以可以直接使用 CNAME 记录，不需要 A 记录。

---

## ✅ 验证配置

### 1. 等待 DNS 记录生效

DNS 记录通常需要 **5-30 分钟** 生效，但最长可能需要 **24 小时**。

### 2. 在 Render 验证

1. **返回 Render Dashboard**
   - 进入你的 Web 服务
   - 点击 **"Settings"** → **"Custom Domains"**

2. **点击 "Verify" 按钮**
   - 对每个域名点击 **"Verify"** 按钮
   - Render 会自动检查 DNS 配置

3. **等待验证结果**
   - 如果配置正确，状态会变为 **"Verified"**（已验证）
   - 如果仍然失败，检查 DNS 记录是否正确

### 3. 使用命令行验证（可选）

#### 检查 www 子域名：
```bash
# 检查 CNAME 记录
dig www.daniugu.online CNAME +short
# 应该返回：daniugu.onrender.com

# 或者使用 nslookup
nslookup -type=CNAME www.daniugu.online
```

#### 检查根域名：
```bash
# 如果使用 CNAME/ANAME
dig daniugu.online CNAME +short
# 应该返回：daniugu.onrender.com

# 如果使用 A 记录
dig daniugu.online A +short
# 应该返回：216.24.57.1
```

---

## 🚀 配置 Cloudflare CDN（可选，推荐）

如果你使用 Cloudflare，在 DNS 记录验证后，可以启用 CDN 加速：

### 步骤 1：启用 Cloudflare 代理

1. **进入 DNS 设置**
   - 在 Cloudflare Dashboard，选择域名 `daniugu.online`
   - 点击 **"DNS"** → **"Records"**

2. **启用代理**
   - 找到 `www` 的 CNAME 记录
   - 点击记录右侧的 **云朵图标**（从灰色 ⚪ 变为橙色 🟠）
   - 找到 `@` 的 CNAME 记录
   - 点击记录右侧的 **云朵图标**（从灰色 ⚪ 变为橙色 🟠）

3. **配置 SSL/TLS**
   - 点击左侧菜单 **"SSL/TLS"**
   - 将模式设置为 **"Full"**（完全）
   - 确保 **"Always Use HTTPS"** 已启用

---

## ❌ 常见问题

### 问题 1：DNS 记录配置后仍然无法验证

**可能原因**：
- DNS 记录还未生效（需要等待 5-30 分钟）
- DNS 记录配置错误（检查记录类型、名称、目标值）
- Proxy 状态启用了（初始配置时应禁用代理）

**解决方法**：
1. 等待 10-30 分钟后再验证
2. 使用 `dig` 或 `nslookup` 检查 DNS 记录是否正确
3. 确保 Proxy 状态为 **⚪ DNS only**（灰色云朵）
4. 检查记录值是否正确（`daniugu.onrender.com` 或 `216.24.57.1`）

### 问题 2：域名注册商不支持 ANAME/ALIAS 记录

**解决方法**：
- 使用 A 记录指向 `216.24.57.1`
- 或者使用 Cloudflare（支持根域名的 CNAME）

### 问题 3：Cloudflare 代理后无法访问

**可能原因**：
- SSL/TLS 模式配置错误
- Render 服务未正常启动

**解决方法**：
1. 检查 SSL/TLS 模式是否为 **"Full"**
2. 确保 Render 服务正常运行
3. 暂时禁用 Cloudflare 代理，使用 **⚪ DNS only** 测试

---

## ✅ 配置检查清单

- [ ] 已配置 `www.daniugu.online` 的 CNAME 记录指向 `daniugu.onrender.com`
- [ ] 已配置 `daniugu.online` 的 ANAME/ALIAS 记录（或 A 记录）
- [ ] DNS 记录已保存
- [ ] 等待 5-30 分钟让 DNS 记录生效
- [ ] 在 Render Dashboard 点击 "Verify" 按钮
- [ ] 域名验证通过，状态变为 "Verified"
- [ ] （可选）启用 Cloudflare CDN 代理
- [ ] （可选）配置 Cloudflare SSL/TLS 模式为 "Full"
- [ ] 测试访问 `https://www.daniugu.online`
- [ ] 测试访问 `https://daniugu.online`（应该重定向到 www）

---

## 🎉 完成！

配置完成后，你的应用应该可以通过以下地址访问：
- ✅ `https://www.daniugu.online`
- ✅ `https://daniugu.online`（自动重定向到 www）

如有问题，查看 Render Dashboard 中的 **"Logs"** 标签获取详细错误信息。

