# Vercel 环境变量配置指南

## 配置 Upstash Redis 环境变量

### 步骤 1：获取 Upstash Redis 凭证

如果您还没有 Upstash Redis 账户，请先：

1. 访问 [Upstash Redis](https://upstash.com/)
2. 注册/登录账户
3. 创建一个 Redis 数据库
4. 在数据库详情页面，找到 **REST API** 部分
5. 复制以下信息：
   - **UPSTASH_REDIS_REST_URL**：例如 `https://your-redis.upstash.io`
   - **UPSTASH_REDIS_REST_TOKEN**：一长串 Token 字符串

### 步骤 2：在 Vercel 中配置环境变量

#### 方法一：通过 Vercel Dashboard（推荐）

1. **登录 Vercel**
   - 访问 [Vercel Dashboard](https://vercel.com/dashboard)
   - 登录您的账户

2. **选择项目**
   - 在项目列表中找到 `daniugu` 项目（或您的项目名称）
   - 点击进入项目详情页

3. **进入设置**
   - 点击顶部的 **Settings** 标签
   - 在左侧菜单中，点击 **Environment Variables**

4. **添加环境变量**
   - 点击 **Add New** 按钮
   - 输入以下环境变量：

   **环境变量 1：**
   - Key: `UPSTASH_REDIS_REST_URL`
   - Value: 您的 Upstash Redis REST URL（例如：`https://your-redis.upstash.io`）
   - Environment: 选择 **Production**、**Preview** 和 **Development**（或至少选择 Production）
   - 点击 **Save**

   **环境变量 2：**
   - Key: `UPSTASH_REDIS_REST_TOKEN`
   - Value: 您的 Upstash Redis REST Token
   - Environment: 选择 **Production**、**Preview** 和 **Development**（或至少选择 Production）
   - 点击 **Save**

5. **重新部署**
   - 环境变量配置后，需要重新部署才能生效
   - 点击 **Deployments** 标签
   - 点击最新的部署右侧的 **...** 菜单
   - 选择 **Redeploy**
   - 或者在 **Settings** > **Environment Variables** 页面，点击 **Redeploy** 按钮

#### 方法二：通过 Vercel CLI

如果您使用 Vercel CLI，可以通过命令行配置：

```bash
# 配置 Production 环境
vercel env add UPSTASH_REDIS_REST_URL production
vercel env add UPSTASH_REDIS_REST_TOKEN production

# 配置 Preview 环境
vercel env add UPSTASH_REDIS_REST_URL preview
vercel env add UPSTASH_REDIS_REST_TOKEN preview

# 配置 Development 环境
vercel env add UPSTASH_REDIS_REST_URL development
vercel env add UPSTASH_REDIS_REST_TOKEN development

# 拉取环境变量（可选）
vercel env pull
```

### 步骤 3：验证环境变量是否配置成功

1. **查看环境变量**
   - 在 Vercel Dashboard > Settings > Environment Variables 页面
   - 确认两个环境变量都已添加
   - 确认它们已分配给正确的环境（Production/Preview/Development）

2. **检查部署日志**
   - 重新部署后，查看部署日志
   - 查找以下日志信息：
     - `✅ Redis 环境变量已设置，尝试保存到 Redis...`
     - 或 `⚠️ UPSTASH_REDIS_REST_URL 环境变量未设置，跳过 Redis 保存`

3. **测试缓存保存**
   - 访问 `https://www.daniugu.online/api/refresh_stock_cache?force=true`
   - 查看返回的 JSON 响应，应该包含 `success: true`
   - 或者查看 Vercel 日志，应该看到 Redis 保存成功的日志

### 步骤 4：如果仍然失败

如果配置环境变量后仍然失败，请检查：

1. **环境变量名称是否正确**
   - 确保完全一致：`UPSTASH_REDIS_REST_URL` 和 `UPSTASH_REDIS_REST_TOKEN`
   - 注意大小写

2. **环境变量值是否正确**
   - URL 应该是完整的 HTTPS URL，例如：`https://your-redis.upstash.io`
   - Token 应该是一长串字符串，不要包含额外的空格或换行

3. **是否重新部署**
   - 环境变量配置后，**必须重新部署**才能生效
   - 简单的代码推送不会自动重新部署

4. **检查 Upstash Redis 状态**
   - 登录 Upstash Dashboard
   - 确认 Redis 数据库状态为 **Active**
   - 确认 REST API 功能已启用

5. **查看详细日志**
   - 在 Vercel Dashboard > Deployments > 最新部署 > Logs
   - 查找 `[_save_stock_list_to_cache]` 相关的日志
   - 查看具体的错误信息

### 其他相关环境变量

除了 Redis 环境变量，您可能还需要配置：

- `VIP_ALIPAY_ACCOUNT`：VIP 支付支付宝账号（可选，默认：`522168878@qq.com`）
- `VIP_WECHAT_ACCOUNT`：VIP 支付微信账号（可选）
- `VERCEL_GIT_COMMIT_SHA`：Git commit SHA（Vercel 自动设置）
- `VERCEL_GIT_COMMIT_MESSAGE`：Git commit 消息（Vercel 自动设置）

### 注意事项

1. **安全性**
   - 环境变量中的 Token 是敏感信息，不要泄露
   - 不要在代码中硬编码 Token
   - 不要将包含 Token 的文件提交到 Git

2. **环境变量作用域**
   - **Production**：生产环境（www.daniugu.online）
   - **Preview**：预览环境（每个 PR 的预览部署）
   - **Development**：开发环境（本地开发）

3. **免费版限制**
   - Upstash Redis 免费版有使用限制（请求次数、数据大小等）
   - 如果超过限制，可能需要升级到付费计划

4. **备份方案**
   - 如果 Redis 不可用，代码会尝试使用 Vercel KV 作为备用方案
   - 如果两者都不可用，缓存保存会失败（但不会影响其他功能）

