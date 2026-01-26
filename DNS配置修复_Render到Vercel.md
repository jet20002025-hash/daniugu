# 🔧 DNS 配置修复 - 从 Render 迁移到 Vercel

## 📊 当前配置问题

根据你提供的 DNS 配置：

**当前配置：**
- ❌ `www` → `daniugu.onrender.com`（指向 Render，需要改为 Vercel）
- ❌ `daniugu.online` → `216.24.57.1`（A 记录，可能需要删除或修改）
- ⚠️ NS 记录指向 Spaceship（不是 Cloudflare）

---

## ✅ 修复步骤

### 步骤 1：修改 www 子域名的 CNAME 记录

**当前配置：**
```
Type: CNAME
Name: www
Content: daniugu.onrender.com
```

**需要改为：**
```
Type: CNAME
Name: www
Content: cname.vercel-dns.com
或
Content: 0774abe293040a93.vercel-dns-017.com.
（使用 Vercel Dashboard 中显示的地址）
```

**操作：**
1. 找到 `www` 的 CNAME 记录
2. 点击 **"编辑"**
3. 将 **内容** 从 `daniugu.onrender.com` 改为 `cname.vercel-dns.com`
4. 保持 **代理状态** 为 "仅 DNS"（灰色云朵）
5. 点击 **"保存"**

### 步骤 2：处理根域名（daniugu.online）

**选项 A：删除 A 记录（推荐）**

如果根域名不需要直接访问（Vercel 会自动重定向到 www）：

1. 找到 `daniugu.online` 的 A 记录
2. 点击 **"删除"**
3. 确认删除

**选项 B：修改 A 记录为 CNAME（如果 DNS 提供商支持）**

1. 删除现有的 A 记录
2. 添加新的 CNAME 记录：
   ```
   Type: CNAME
   Name: @ 或 daniugu.online
   Content: cname.vercel-dns.com
   代理状态: 仅 DNS
   ```

**选项 C：保留 A 记录但指向 Vercel（如果 Vercel 提供 IP）**

如果 Vercel Dashboard 显示了根域名的 A 记录 IP 地址，可以修改：
1. 点击 A 记录右侧的 **"编辑"**
2. 将 IP 地址改为 Vercel 提供的 IP
3. 保存

---

## 📋 正确的配置（修复后）

### ✅ www.daniugu.online

```
Type: CNAME
Name: www
Content: cname.vercel-dns.com
代理状态: 仅 DNS（灰色云朵）
TTL: 自动
```

### ✅ daniugu.online（根域名）

**方案 1：删除 A 记录（推荐）**
- 删除 A 记录，让 Vercel 自动处理根域名重定向

**方案 2：CNAME 记录（如果支持）**
```
Type: CNAME
Name: @
Content: cname.vercel-dns.com
代理状态: 仅 DNS
TTL: 自动
```

---

## 🔍 获取 Vercel 的 DNS 配置

### 方法 1：从 Vercel Dashboard 获取

1. **登录 Vercel Dashboard**
   - 访问：https://vercel.com/dashboard
   - 选择项目 `daniugu`

2. **查看域名配置**
   - 进入 **Settings** → **Domains**
   - 找到 `www.daniugu.online`
   - 查看 Vercel 显示的 DNS 配置要求

3. **使用 Vercel 提供的地址**
   - Vercel 可能会显示特定的 CNAME 地址（例如：`0774abe293040a93.vercel-dns-017.com.`）
   - 使用这个地址而不是通用的 `cname.vercel-dns.com`

### 方法 2：使用通用地址

如果 Vercel 没有显示特定地址，使用：
```
cname.vercel-dns.com
```

---

## ⚠️ 关于 NS 记录

你的 DNS 配置显示 NS 记录指向 Spaceship：
- `launch1.spaceship.net`
- `launch2.spaceship.net`

**说明：**
- 这些 NS 记录是在域名注册商（如阿里云）配置的，不是在 DNS 提供商这里配置的
- 如果你要使用 Cloudflare，需要在域名注册商处将 NS 记录改为 Cloudflare 的 DNS 服务器
- 如果继续使用 Spaceship 的 DNS，就在这里修改 CNAME 记录即可

---

## 📝 操作步骤总结

### 立即需要做的：

1. ✅ **修改 www 的 CNAME 记录**
   - 从 `daniugu.onrender.com` 改为 `cname.vercel-dns.com`
   - 或使用 Vercel Dashboard 显示的特定地址

2. ✅ **处理根域名的 A 记录**
   - 删除 A 记录（推荐）
   - 或改为 CNAME 记录（如果支持）

3. ✅ **等待 DNS 生效**
   - 通常 5-30 分钟
   - 最长 24 小时

4. ✅ **验证配置**
   - 访问 https://www.daniugu.online
   - 检查 Vercel Dashboard 中的域名状态

---

## 🔍 验证步骤

### 1. 检查 DNS 解析

```bash
# 检查 www 的 CNAME 记录
dig www.daniugu.online CNAME

# 应该看到指向 cname.vercel-dns.com 或 Vercel 提供的地址
```

### 2. 检查网站访问

- 访问：https://www.daniugu.online
- 应该能正常访问，不再显示 Error 1000

### 3. 检查 Vercel Dashboard

- 登录 Vercel Dashboard
- 进入 Settings → Domains
- 查看 `www.daniugu.online` 的状态
- 应该显示 **"Valid Configuration"** ✅

---

## 🐛 如果仍然有问题

### 问题 1：修改后仍然指向 Render

**解决**：
- 等待更长时间（DNS 传播可能需要 24 小时）
- 清除本地 DNS 缓存：
  ```bash
  # macOS
  sudo dscacheutil -flushcache
  
  # Windows
  ipconfig /flushdns
  ```

### 问题 2：Vercel 显示 Invalid Configuration

**解决**：
- 确认 CNAME 记录已正确配置
- 确认使用的是 Vercel Dashboard 显示的地址
- 等待 10-30 分钟让 Vercel 检测到更改

### 问题 3：根域名无法访问

**解决**：
- 根域名会自动重定向到 www
- 如果根域名也需要直接访问，需要配置根域名的 CNAME 或 A 记录

---

## ✅ 完成后的配置

**最终配置应该是：**

```
Type: CNAME
Name: www
Content: cname.vercel-dns.com（或 Vercel 提供的特定地址）
代理状态: 仅 DNS
TTL: 自动
```

**根域名：**
- 删除 A 记录（推荐）
- 或配置 CNAME 记录指向 Vercel

---

**按照上述步骤修改后，等待 5-30 分钟，然后访问 https://www.daniugu.online 验证！**
