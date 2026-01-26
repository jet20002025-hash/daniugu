# 🚀 daniugu 快速部署指南

## 📋 你的项目信息

- **GitHub 仓库**: https://github.com/jet20002025-hash/daniugu
- **部署平台**: Vercel（推荐）或 Render
- **域名**: daniugu.online（可选）

---

## ⚡ 快速开始（3步完成）

### 步骤 1：推送代码到 GitHub

```bash
cd /Users/zwj/股票分析

# 添加所有更改
git add .

# 提交更改
git commit -m "更新代码，准备部署到 Vercel"

# 推送到 GitHub
git push origin main
```

### 步骤 2：在 Vercel 部署

1. 访问 https://vercel.com，使用 GitHub 登录
2. 点击 **"New Project"**
3. 选择仓库 `jet20002025-hash/daniugu`
4. 点击 **"Deploy"**（配置会自动检测）
5. 等待 2-5 分钟，部署完成后会得到地址：`https://daniugu.vercel.app`

### 步骤 3：配置环境变量（重要！）

1. **获取 Upstash Redis 凭证**：
   - 访问 https://upstash.com
   - 注册/登录 → Create Database → 选择区域 → Create
   - 复制 `UPSTASH_REDIS_REST_URL` 和 `UPSTASH_REDIS_REST_TOKEN`

2. **在 Vercel 配置环境变量**：
   - Settings → Environment Variables → Add New
   - 添加两个变量：
     ```
     UPSTASH_REDIS_REST_URL=https://your-redis.upstash.io
     UPSTASH_REDIS_REST_TOKEN=your-token-here
     INVITE_CODES=ADMIN2024,VIP2024
     ```
   - 选择所有环境（Production, Preview, Development）

3. **重新部署**：
   - Deployments → 最新部署 → ... → Redeploy

---

## ✅ 验证部署

1. 访问 `https://daniugu.vercel.app`
2. 使用邀请码 `ADMIN2024` 注册
3. 登录并测试扫描功能

---

## 📚 详细文档

- 完整指南: `部署指南.md`
- 快速参考: `快速部署参考.md`
- Vercel 配置: `Vercel环境变量配置指南.md`

---

## 🎯 一键部署

运行脚本自动完成代码准备：

```bash
bash 一键部署.sh
```
