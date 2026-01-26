# 🚀 Vercel 部署配置步骤（当前页面）

## 📋 当前页面配置

根据你的截图，Vercel 已经检测到：
- ✅ Framework Preset: **Flask**（已自动检测）
- ✅ Root Directory: `./`（根目录）
- ✅ Project Name: `daniugu`
- ✅ Branch: `main`

## ⚙️ 配置步骤

### 步骤 1: 展开 "Build and Output Settings"

点击 **"Build and Output Settings"** 展开，配置如下：

#### Build Command
- **留空**（Vercel 会自动处理 Python 项目）

#### Output Directory
- **留空**（Flask 应用不需要输出目录）

#### Install Command
- **留空** 或填写：`pip install -r requirements.txt`
- Vercel 会自动检测 `requirements.txt` 并安装依赖

#### Development Command
- **留空**

### 步骤 2: 展开 "Environment Variables"

点击 **"Environment Variables"** 展开，添加以下环境变量：

#### 必需的环境变量

1. **UPSTASH_REDIS_REST_URL**
   - Key: `UPSTASH_REDIS_REST_URL`
   - Value: 你的 Upstash Redis REST URL（如：`https://xxx.upstash.io`）
   - Environment: 选择 **"Production, Preview, Development"**（全部环境）

2. **UPSTASH_REDIS_REST_TOKEN**
   - Key: `UPSTASH_REDIS_REST_TOKEN`
   - Value: 你的 Upstash Redis REST Token
   - Environment: 选择 **"Production, Preview, Development"**（全部环境）

3. **INVITE_CODES**
   - Key: `INVITE_CODES`
   - Value: `ADMIN2024,VIP2024`
   - Environment: 选择 **"Production, Preview, Development"**（全部环境）

#### 推荐的环境变量

4. **FLASK_SECRET_KEY**
   - Key: `FLASK_SECRET_KEY`
   - Value: 生成一个随机字符串（32+ 字符）
   - 生成命令：`python3 -c "import secrets; print(secrets.token_hex(32))"`
   - Environment: 选择 **"Production, Preview, Development"**（全部环境）

**⚠️ 重要**：如果还没有 Upstash Redis 凭证，可以：
- 先点击 **"Deploy"** 完成首次部署
- 部署后再配置环境变量并重新部署

### 步骤 3: 点击 "Deploy"

配置完成后，点击底部的 **"Deploy"** 按钮。

## ⏳ 部署过程

部署通常需要 2-5 分钟，Vercel 会：
1. 安装依赖（从 `requirements.txt`）
2. 检测 Flask 入口点（`api/index.py`）
3. 构建项目
4. 部署到生产环境

## ✅ 部署后验证

### 1. 查看部署状态

在 Vercel Dashboard → Deployments 查看：
- ✅ **"Ready"** - 部署成功
- ⏳ **"Building"** - 正在构建
- ❌ **"Error"** - 部署失败（查看日志）

### 2. 测试健康检查

部署完成后，访问：
```
https://daniugu.vercel.app/api/health
```

应该返回：
```json
{
  "success": true,
  "status": "ok",
  "environment": "vercel"
}
```

### 3. 如果仍然显示入口点错误

**解决方案 A：检查 Vercel 日志**
- Deployments → 最新部署 → Function Logs
- 查看具体错误信息

**解决方案 B：手动指定入口点**
- 在 "Build and Output Settings" 中
- 可能需要添加自定义配置（但通常不需要）

**解决方案 C：确认文件已提交**
- 确认 `api/index.py`、`index.py`、`app.py`、`pyproject.toml` 都已推送到 GitHub

## 📝 快速操作清单

- [ ] 展开 "Build and Output Settings"（检查配置，通常留空即可）
- [ ] 展开 "Environment Variables"（添加 Redis 和邀请码）
- [ ] 点击 "Deploy" 按钮
- [ ] 等待部署完成（2-5 分钟）
- [ ] 测试健康检查：`/api/health`
- [ ] 如果失败，查看 Function Logs

## 🎯 推荐操作顺序

### 方案一：先部署，后配置环境变量（推荐）

1. **直接点击 "Deploy"**（不配置环境变量）
2. 等待部署完成
3. 如果部署成功但功能异常，再配置环境变量
4. 重新部署

### 方案二：先配置环境变量，再部署

1. 展开 "Environment Variables"
2. 添加所有必需的环境变量
3. 点击 "Deploy"
4. 等待部署完成

---

**建议：先点击 "Deploy" 完成首次部署，然后根据结果决定是否需要调整配置！**
