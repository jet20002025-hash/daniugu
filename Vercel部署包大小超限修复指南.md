# 🔧 Vercel 部署包大小超限修复指南

## ❌ 错误信息

```
Error: The file 'prj_w0XW7wQ9lNuaBvqrkzYE1LOenVxP/dbc03d12c2cd27c006488cfd564ac6420993ed8f77218427f23876c87de71b95.zip' exceeds the maximum upload size limit of 300MB. Actual size: 314575541 bytes
```

## 🔍 问题原因

Vercel 的部署包大小限制是 **300MB**，但项目中包含：
- `cache/` 目录：**1.3GB**（股票数据缓存）
- `stock_data/` 目录：**269MB**（股票数据）
- 大量日志文件（`.log`）
- 压缩文件（`.tar.gz`, `.zip`）

这些文件**不应该**部署到 Vercel，因为：
1. Vercel 是 serverless 环境，每次部署都是全新环境
2. 数据应该从 GitHub Releases 或其他外部存储动态加载
3. 这些文件会大大增加部署包大小

## ✅ 解决方案

### 1. 已更新 `.vercelignore`

已创建/更新 `.vercelignore` 文件，排除以下内容：

```
# 大型数据目录
cache/
stock_data/
models/

# 日志和压缩文件
*.log
*.tar.gz
*.zip

# 大型输出文件
backtest_*.csv
backtest_*.json
scan_result_*.json
training_*.json
retrain_*.json

# 但保留必需的模型文件
!trained_model.json
```

### 2. 部署包大小验证

排除大型文件后，部署包大小约为 **632KB**，远低于 300MB 限制。

## 📋 下一步操作

### 1. 刷新 Vercel 页面

在 Vercel 配置页面：
- 刷新页面（F5 或 Cmd+R）
- 或返回项目列表，重新导入项目

### 2. 重新导入项目（推荐）

1. 返回 Vercel Dashboard
2. 点击 "New Project"
3. 重新选择 `jet20002025-hash/daniugu`
4. Vercel 会自动使用新的 `.vercelignore` 配置

### 3. 配置环境变量

展开 "Environment Variables"，添加：

**必需：**
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `INVITE_CODES` = `ADMIN2024,VIP2024`

**推荐：**
- `FLASK_SECRET_KEY` = 随机字符串
- `STOCK_DATA_URL` = GitHub Releases 数据包 URL（如果使用）

### 4. 点击 "Deploy"

配置完成后，点击 "Deploy" 按钮。

## ✅ 验证部署

部署完成后（2-5 分钟），访问：
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

## 📝 重要说明

### 数据文件处理

由于排除了 `cache/` 和 `stock_data/` 目录，Vercel 部署后：

1. **首次启动**：系统会从 GitHub Releases 下载数据（如果配置了 `STOCK_DATA_URL`）
2. **运行时缓存**：数据会缓存在 `/tmp` 目录（Vercel 的临时存储）
3. **数据更新**：通过 Web 界面的"更新数据"按钮触发

### 必需文件

以下文件**必须**包含在部署中：
- ✅ `trained_model.json` - 训练好的模型
- ✅ `requirements.txt` - Python 依赖
- ✅ `api/index.py` - Flask 入口点
- ✅ `bull_stock_web.py` - 主应用
- ✅ 所有 `.py` 源代码文件

### 排除的文件

以下文件**不会**部署（通过 `.vercelignore`）：
- ❌ `cache/` - 本地数据缓存
- ❌ `stock_data/` - 股票数据文件
- ❌ `models/` - 其他模型文件
- ❌ `*.log` - 日志文件
- ❌ `*.tar.gz`, `*.zip` - 压缩文件

## 🐛 如果仍然失败

### 检查部署日志

1. Deployments → 最新部署 → Build Logs
2. 查看是否有其他大型文件被包含
3. 确认 `.vercelignore` 规则是否生效

### 手动验证

在本地运行：
```bash
cd /Users/zwj/股票分析
tar -czf /tmp/test.tar.gz --exclude-from=.vercelignore --exclude='.git' --exclude='.venv' .
du -sh /tmp/test.tar.gz
```

如果大小超过 300MB，需要进一步优化 `.vercelignore`。

---

**`.vercelignore` 已更新并推送，请刷新 Vercel 页面后重新部署！**
