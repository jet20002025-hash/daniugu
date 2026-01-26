# 🔧 Vercel 主页 500 错误 - 详细调试指南

## ❌ 错误信息

```
GET https://daniugu-1am2.vercel.app/ 500 (Internal Server Error)
```

## 🔍 调试步骤

### 1. 查看 Vercel 函数日志（最重要）

**这是最关键的一步**，日志会显示具体的错误信息。

1. Vercel Dashboard → 项目 → Deployments → 最新部署
2. 点击 **"Function Logs"**
3. 查找以下日志：
   - `[index] 开始处理主页请求...`
   - `[index] 检查登录状态...`
   - `[index] 登录状态检查结果: ...`
   - `[index] 已登录，开始渲染模板...`
   - `[index] ❌` 开头的错误日志

### 2. 常见错误和解决方案

#### 错误 1: `检查登录状态失败`

**可能原因**：
- Redis 连接失败
- Session 初始化失败
- `is_logged_in()` 函数内部错误

**解决方案**：
- ✅ 已修复：添加了错误处理，如果检查失败会自动重定向到登录页面
- 检查环境变量：`UPSTASH_REDIS_REST_URL` 和 `UPSTASH_REDIS_REST_TOKEN`

#### 错误 2: `渲染模板失败`

**可能原因**：
- 模板文件不存在
- 模板文件格式错误
- 模板路径不正确

**解决方案**：
- ✅ 已修复：添加了模板路径检查和错误处理
- 检查 `templates/bull_stock_web.html` 是否存在

#### 错误 3: `重定向失败`

**可能原因**：
- `url_for('login_page')` 失败
- Flask 应用未正确初始化

**解决方案**：
- ✅ 已修复：添加了备用重定向路径 `/login`

## 📋 检查清单

### 环境变量检查

确保以下环境变量已设置：
- [ ] `UPSTASH_REDIS_REST_URL`
- [ ] `UPSTASH_REDIS_REST_TOKEN`
- [ ] `FLASK_SECRET_KEY`（推荐）
- [ ] `INVITE_CODES`（如果需要）

### 文件检查

确保以下文件存在：
- [ ] `templates/bull_stock_web.html`
- [ ] `templates/login.html`
- [ ] `api/index.py`
- [ ] `bull_stock_web.py`

### 依赖检查

确保以下依赖已安装：
- [ ] Flask
- [ ] 其他依赖（见 `requirements.txt`）

## 🐛 如果仍然失败

### 步骤 1: 查看详细日志

查看 Vercel 函数日志，找到 `[index]` 开头的日志，这些日志会显示：
- 登录状态检查是否成功
- 模板渲染是否成功
- 具体的错误信息

### 步骤 2: 测试健康检查端点

访问：
```
https://daniugu-1am2.vercel.app/api/health
```

如果健康检查也失败，说明是应用初始化问题。

### 步骤 3: 检查环境变量

在 Vercel Dashboard → Settings → Environment Variables 中：
1. 确认所有必需的环境变量都已设置
2. 确认环境变量值正确（没有多余的空格）
3. 确认环境变量应用于正确的环境（Production/Preview/Development）

### 步骤 4: 手动触发重新部署

1. Vercel Dashboard → Deployments
2. 点击最新部署右侧的 "..." 菜单
3. 选择 "Redeploy"

## 📝 已添加的日志

现在主页路由会输出以下日志：
- `[index] 开始处理主页请求...`
- `[index] 检查登录状态...`
- `[index] 登录状态检查结果: True/False`
- `[index] 未登录，重定向到登录页面`（如果未登录）
- `[index] 已登录，开始渲染模板...`
- `[index] 模板路径: ...`
- `[index] ✅ 模板渲染成功`（如果成功）
- `[index] ❌` 开头的错误日志（如果失败）

## 🎯 下一步

1. **查看 Vercel 函数日志**，找到 `[index]` 开头的日志
2. **根据日志中的错误信息**，确定具体问题
3. **提供日志中的错误信息**，我可以进一步帮助修复

---

**请查看 Vercel 函数日志，找到 `[index]` 开头的日志，并提供具体的错误信息！**
