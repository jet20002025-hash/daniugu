# Render 环境变量配置指南

## 📋 必需的环境变量

### 1. UPSTASH_REDIS_REST_URL（必需）

**作用**：Upstash Redis 的 REST API URL，用于连接 Redis 数据库

**获取方式**：
1. 登录 https://console.upstash.com
2. 选择你的 Redis 数据库（如果没有，先创建一个）
3. 点击数据库名称进入详情页
4. 在 "Details" 页面找到 "REST API" 部分
5. 复制 "REST URL"（例如：`https://xxx-xxx-xxx.upstash.io`）

**在 Render 中配置**：
- Key: `UPSTASH_REDIS_REST_URL`
- Value: 你的 REST URL（例如：`https://xxx-xxx-xxx.upstash.io`）

---

### 2. UPSTASH_REDIS_REST_TOKEN（必需）

**作用**：Upstash Redis 的 REST API Token，用于认证

**获取方式**：
1. 在 Upstash Redis 数据库的 "Details" 页面
2. 在 "REST API" 部分
3. 复制 "REST Token"（一长串字符）

**在 Render 中配置**：
- Key: `UPSTASH_REDIS_REST_TOKEN`
- Value: 你的 REST Token

---

## 📋 可选的环境变量

### 3. INVITE_CODES（可选）

**作用**：注册邀请码列表

**配置**：
- Key: `INVITE_CODES`
- Value: `ADMIN2024,VIP2024`（用逗号分隔多个邀请码）

**说明**：
- 如果不配置，会使用默认值
- 多个邀请码用逗号分隔

---

### 4. VIP_ALIPAY_ACCOUNT（可选）

**作用**：VIP 支付支付宝账号

**配置**：
- Key: `VIP_ALIPAY_ACCOUNT`
- Value: `522168878@qq.com`

---

### 5. VIP_WECHAT_ACCOUNT（可选）

**作用**：VIP 支付微信账号

**配置**：
- Key: `VIP_WECHAT_ACCOUNT`
- Value: 你的微信账号

---

### 6. PYTHON_VERSION（可选）

**作用**：指定 Python 版本

**配置**：
- Key: `PYTHON_VERSION`
- Value: `3.9`（或你需要的版本）

**说明**：
- Render 会自动检测 Python 版本
- 通常不需要手动配置

---

## 🚀 在 Render 中配置环境变量

### 步骤 1：进入环境变量设置

1. **登录 Render Dashboard**
   - 访问 https://dashboard.render.com
   - 登录你的账号

2. **选择你的 Web 服务**
   - 在 Dashboard 中找到你的 Web 服务（如 `daniugu`）
   - 点击服务名称进入详情页

3. **进入环境变量设置**
   - 点击左侧菜单 **"Environment"** 标签
   - 或点击 **"Environment Variables"** 部分

### 步骤 2：添加环境变量

1. **点击 "Add Environment Variable"** 按钮

2. **添加第一个环境变量（UPSTASH_REDIS_REST_URL）**
   - **Key**: `UPSTASH_REDIS_REST_URL`
   - **Value**: 你的 Upstash Redis REST URL
   - 点击 **"Save"**

3. **添加第二个环境变量（UPSTASH_REDIS_REST_TOKEN）**
   - 再次点击 **"Add Environment Variable"**
   - **Key**: `UPSTASH_REDIS_REST_TOKEN`
   - **Value**: 你的 Upstash Redis REST Token
   - 点击 **"Save"**

4. **添加可选环境变量（如果需要）**
   - `INVITE_CODES` = `ADMIN2024,VIP2024`
   - `VIP_ALIPAY_ACCOUNT` = `522168878@qq.com`
   - `VIP_WECHAT_ACCOUNT` = 你的微信账号（可选）

### 步骤 3：重新部署

1. **环境变量配置后，需要重新部署**
   - 点击 **"Manual Deploy"** → **"Deploy latest commit"**
   - 或等待 Render 自动检测到代码更新后部署

2. **查看部署日志**
   - 在 **"Logs"** 标签查看部署过程
   - 确认应用正常启动

---

## 📝 配置示例

### 完整的环境变量列表

```
UPSTASH_REDIS_REST_URL=https://xxx-xxx-xxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=AXxxxxx...（一长串字符）
INVITE_CODES=ADMIN2024,VIP2024
VIP_ALIPAY_ACCOUNT=522168878@qq.com
VIP_WECHAT_ACCOUNT=你的微信账号（可选）
PYTHON_VERSION=3.9（可选）
```

---

## ⚠️ 重要提示

### 1. 环境变量是必需的

**如果没有配置 Redis 环境变量**：
- ❌ 应用可能无法正常启动
- ❌ 用户数据无法保存
- ❌ 扫描进度无法保存
- ❌ 可能导致应用不断重启

### 2. 如何获取 Upstash Redis 配置

**如果还没有 Upstash Redis 数据库**：

1. **创建 Upstash 账号**
   - 访问 https://console.upstash.com
   - 使用 GitHub 或邮箱注册

2. **创建 Redis 数据库**
   - 点击 **"Create Database"**
   - 选择 **"Redis"**
   - 选择区域（推荐选择离你最近的区域，如 `ap-northeast-1` 或 `ap-southeast-1`）
   - 点击 **"Create"**

3. **获取 REST URL 和 Token**
   - 创建完成后，进入数据库详情页
   - 在 **"Details"** 页面找到 **"REST API"** 部分
   - 复制 **"REST URL"** 和 **"REST Token"**

### 3. 环境变量配置后需要重新部署

- ✅ 配置环境变量后，Render 会自动重新部署
- ✅ 或手动点击 **"Manual Deploy"** → **"Deploy latest commit"**

### 4. 验证配置

**部署后，查看日志确认**：
- ✅ 应用正常启动
- ✅ 没有 Redis 连接错误
- ✅ 环境检测正确（显示 "环境: Render"）

---

## 🔍 常见问题

### 问题 1：找不到 Upstash Redis 配置

**解决方法**：
1. 确认已登录 https://console.upstash.com
2. 确认已创建 Redis 数据库
3. 在数据库详情页的 "Details" 标签中找到 "REST API" 部分

### 问题 2：环境变量配置后应用仍然无法启动

**可能原因**：
- Redis URL 或 Token 配置错误
- 环境变量名称拼写错误
- 没有重新部署

**解决方法**：
1. 检查环境变量名称是否正确（注意大小写）
2. 检查 Redis URL 和 Token 是否正确（没有多余空格）
3. 重新部署应用
4. 查看日志中的错误信息

### 问题 3：如何验证环境变量已配置

**方法**：
1. 在 Render Dashboard → Environment 标签
2. 查看环境变量列表
3. 确认 `UPSTASH_REDIS_REST_URL` 和 `UPSTASH_REDIS_REST_TOKEN` 已配置

---

## ✅ 配置检查清单

- [ ] 已创建 Upstash Redis 数据库
- [ ] 已获取 REST URL
- [ ] 已获取 REST Token
- [ ] 在 Render 中配置了 `UPSTASH_REDIS_REST_URL`
- [ ] 在 Render 中配置了 `UPSTASH_REDIS_REST_TOKEN`
- [ ] 配置了可选环境变量（如果需要）
- [ ] 已重新部署应用
- [ ] 查看日志确认应用正常启动

---

## 📞 需要帮助？

如果遇到问题：
1. 查看 Render Dashboard → Logs 中的错误信息
2. 确认环境变量名称和值是否正确
3. 确认 Redis 数据库是否正常
4. 重新部署应用


