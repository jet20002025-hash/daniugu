# Render 部署指南

## 📋 准备工作

### 1. 确保代码已推送到 GitHub

```bash
cd /Users/zwj/股票分析
git add .
git commit -m "添加Render部署支持"
git push origin main
```

### 2. 检查必要文件

- ✅ `requirements.txt` - Python依赖
- ✅ `Procfile` - 启动命令（已创建）
- ✅ `bull_stock_web.py` - 主应用文件（已修改支持PORT环境变量）

---

## 🚀 部署步骤

### 第一步：创建 Render 账号

1. 访问 [Render](https://render.com)
2. 点击 **"Get Started for Free"**
3. 使用 GitHub 账号登录（推荐）

### 第二步：创建 Web 服务

1. 登录后，点击 **"New +"** → **"Web Service"**
2. 选择 **"Connect GitHub"**（如果还没连接）
3. 授权 Render 访问你的 GitHub 仓库
4. 选择你的仓库（例如：`jet20002025-hash/daniugu`）

### 第三步：配置服务

#### 基本信息
- **Name**: `daniugu`（或你喜欢的名称）
- **Region**: 选择离你最近的区域（如 `Singapore` 或 `Oregon`）
- **Branch**: `main`（或你的主分支）
- **Root Directory**: 留空（使用根目录）

#### 构建和启动
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python bull_stock_web.py`（或留空，Render会自动使用Procfile）

#### 环境变量（重要！）

点击 **"Advanced"** → **"Add Environment Variable"**，添加以下变量：

**必需的环境变量：**

1. **PORT**（Render会自动设置，但可以手动设置）
   - Key: `PORT`
   - Value: `10000`（Render会自动设置，但可以手动指定）

2. **UPSTASH_REDIS_REST_URL**（如果使用Redis）
   - Key: `UPSTASH_REDIS_REST_URL`
   - Value: 你的Upstash Redis REST URL

3. **UPSTASH_REDIS_REST_TOKEN**（如果使用Redis）
   - Key: `UPSTASH_REDIS_REST_TOKEN`
   - Value: 你的Upstash Redis REST Token

4. **INVITE_CODES**（邀请码，可选）
   - Key: `INVITE_CODES`
   - Value: `ADMIN2024,VIP2024`（用逗号分隔）

5. **VIP_ALIPAY_ACCOUNT**（VIP支付账号，可选）
   - Key: `VIP_ALIPAY_ACCOUNT`
   - Value: `522168878@qq.com`

6. **VIP_WECHAT_ACCOUNT**（VIP微信账号，可选）
   - Key: `VIP_WECHAT_ACCOUNT`
   - Value: 你的微信账号

**可选的环境变量：**

- `PYTHON_VERSION`: `3.9`（Render会自动检测，但可以手动指定）

### 第四步：部署

1. 点击 **"Create Web Service"**
2. 等待部署完成（通常 3-5 分钟）
3. 部署完成后，你会得到一个地址：`https://你的服务名.onrender.com`

---

## ⚙️ 配置说明

### Procfile

```
web: python bull_stock_web.py
```

这个文件告诉Render如何启动你的应用。

### 端口配置

代码已修改为支持Render的PORT环境变量：

```python
# 支持Render等平台：从环境变量获取端口
port = int(os.environ.get('PORT', 5002))
app.run(host='0.0.0.0', port=port, ...)
```

### 环境检测

代码会自动检测环境：
- 如果检测到Vercel环境，使用`user_auth_vercel.py`
- 否则使用`user_auth.py`（本地文件存储）

**注意**：Render不是Vercel环境，所以会使用`user_auth.py`（文件存储）。如果需要持久化，建议：
1. 使用Upstash Redis（推荐）
2. 或修改代码以支持Render环境

---

## 🔧 免费版限制

### Render 免费版特点：

1. **自动休眠**
   - 15分钟无活动后自动休眠
   - 下次访问时需要等待约30-60秒启动（冷启动）

2. **资源限制**
   - CPU: 0.25 vCPU
   - 内存: 512MB RAM
   - 带宽: 100GB/月

3. **执行时间**
   - ✅ **无限制**（这是最重要的优势！）

### 升级到付费版（$7/月起）

- 不会休眠
- 更多资源（1 vCPU, 512MB RAM）
- 更快启动

---

## 📝 部署后检查

### 1. 检查服务状态

在Render Dashboard中：
- 查看 **"Logs"** 标签，确认应用正常启动
- 查看 **"Metrics"** 标签，监控资源使用

### 2. 测试访问

访问你的服务地址：
```
https://你的服务名.onrender.com
```

### 3. 测试功能

- ✅ 首页是否正常显示
- ✅ 登录/注册功能
- ✅ 扫描功能（应该不会超时了！）

---

## 🐛 常见问题

### 问题1：部署失败

**可能原因**：
- 依赖安装失败
- 代码错误

**解决方法**：
1. 查看 **"Logs"** 标签中的错误信息
2. 检查 `requirements.txt` 是否正确
3. 检查代码是否有语法错误

### 问题2：应用启动失败

**可能原因**：
- 端口配置错误
- 环境变量缺失

**解决方法**：
1. 确认 `Procfile` 正确
2. 确认环境变量已配置
3. 查看日志中的错误信息

### 问题3：免费版休眠

**现象**：
- 15分钟无活动后，下次访问需要等待30-60秒

**解决方法**：
1. 使用付费版（$7/月）
2. 或使用外部监控服务定期访问（保持活跃）

### 问题4：数据丢失

**原因**：
- 免费版使用文件存储，重启后可能丢失

**解决方法**：
1. 使用Upstash Redis（推荐）
2. 配置环境变量 `UPSTASH_REDIS_REST_URL` 和 `UPSTASH_REDIS_REST_TOKEN`

---

## 🔄 更新部署

### 自动部署（推荐）

Render会自动检测GitHub推送，自动重新部署。

### 手动部署

1. 在Render Dashboard中
2. 点击 **"Manual Deploy"** → **"Deploy latest commit"**

---

## 📊 与Vercel对比

| 特性 | Vercel Hobby | Render 免费版 |
|------|-------------|-------------|
| **执行时间限制** | ❌ 10秒 | ✅ 无限制 |
| **自动休眠** | ❌ 不会 | ⚠️ 15分钟无活动后 |
| **启动速度** | ✅ 快 | ⚠️ 冷启动30-60秒 |
| **配置难度** | ⭐⭐ 简单 | ⭐⭐ 简单 |
| **代码修改** | ✅ 无需 | ✅ 无需 |

---

## 💡 优化建议

### 1. 使用Redis持久化

配置Upstash Redis环境变量，确保数据持久化。

### 2. 升级到付费版

如果经常使用，建议升级到付费版（$7/月），避免休眠。

### 3. 配置自定义域名

在Render Dashboard中：
1. 进入 **"Settings"** → **"Custom Domains"**
2. 添加你的域名（如 `daniugu.online`）
3. 配置DNS记录

---

## ✅ 部署检查清单

- [ ] 代码已推送到GitHub
- [ ] 创建Render账号并登录
- [ ] 创建Web服务
- [ ] 配置环境变量（Redis URL等）
- [ ] 部署成功
- [ ] 测试访问
- [ ] 测试登录/注册
- [ ] 测试扫描功能（确认无超时）

---

## 🎉 完成！

部署完成后，你的应用应该可以：
- ✅ 无执行时间限制（可以长时间扫描）
- ✅ 自动部署（GitHub推送后自动更新）
- ✅ 免费使用（免费版可用）

如有问题，查看Render Dashboard中的 **"Logs"** 标签获取详细错误信息。

