# 🚀 Vercel 从 GitHub 获取缓存数据配置指南

## ✅ 已完成的修改

系统已修改为在 **Vercel 环境**启动时自动从 GitHub Releases 下载股票数据包。

### 主要改动

1. **自动检测 Vercel 环境**：系统会自动检测 Vercel 环境并启用 `USE_GITHUB_DATA_ONLY` 模式
2. **自动下载数据包**：如果检测到 Vercel 环境且设置了 `STOCK_DATA_URL`，系统会在启动时自动下载数据包
3. **自动生成股票列表**：下载完成后，系统会自动从 K 线文件列表生成 `stock_list_all.json`

## 📋 Vercel 环境变量配置

### 必需的环境变量

在 Vercel Dashboard 中设置以下环境变量：

#### 1. `STOCK_DATA_URL`（必需）

指向 GitHub Releases 数据包的下载 URL。

**格式：**
```
STOCK_DATA_URL=https://github.com/jet20002025-hash/daniugu/releases/download/data-YYYYMMDD/stock_data.tar.gz
```

**示例：**
```
STOCK_DATA_URL=https://github.com/jet20002025-hash/daniugu/releases/download/data-20260126/stock_data_20260126_120000.tar.gz
```

**如何获取 URL：**
1. 访问 https://github.com/jet20002025-hash/daniugu/releases
2. 找到最新的数据包 Release（标签格式：`data-YYYYMMDD`）
3. 点击数据包文件（`stock_data_*.tar.gz`）
4. 复制下载链接（右键点击文件 → "复制链接地址"）

#### 2. `USE_GITHUB_DATA_ONLY`（可选，已自动设置）

系统会自动在 Vercel 环境中设置 `USE_GITHUB_DATA_ONLY=1`，无需手动配置。

#### 3. 其他必需的环境变量

- `FLASK_SECRET_KEY`：Flask 会话密钥（用于保持登录状态）
- `UPSTASH_REDIS_REST_URL`：Upstash Redis REST URL（用于用户认证和缓存）
- `UPSTASH_REDIS_REST_TOKEN`：Upstash Redis REST Token

## 🔧 配置步骤

### 步骤 1：准备 GitHub Releases 数据包

确保 GitHub Releases 中已有最新的股票数据包：

1. 使用 `upload_to_github.py` 或 `upload_stock_data.py` 上传数据包
2. 数据包应包含：
   - `cache/daily_kline/` - 日K线数据
   - `cache/weekly_kline/` - 周K线数据
   - `cache/stock_list_all.json` - 股票列表（可选，会自动生成）

### 步骤 2：在 Vercel Dashboard 中设置环境变量

1. 登录 Vercel Dashboard
2. 选择项目 `daniugu`
3. 进入 **Settings** → **Environment Variables**
4. 添加以下环境变量：

| Key | Value | 说明 |
|-----|-------|------|
| `STOCK_DATA_URL` | `https://github.com/jet20002025-hash/daniugu/releases/download/data-YYYYMMDD/stock_data.tar.gz` | GitHub 数据包下载 URL |
| `FLASK_SECRET_KEY` | `你的密钥字符串` | Flask 会话密钥 |
| `UPSTASH_REDIS_REST_URL` | `你的 Redis URL` | Upstash Redis REST URL |
| `UPSTASH_REDIS_REST_TOKEN` | `你的 Redis Token` | Upstash Redis REST Token |

### 步骤 3：重新部署

设置环境变量后，Vercel 会自动触发重新部署。或者手动触发：

1. 进入 **Deployments** 页面
2. 点击最新部署右侧的 **"..."** 菜单
3. 选择 **"Redeploy"**

## 📊 启动日志检查

部署后，检查 Vercel Function Logs，应该看到以下日志：

### 成功下载数据包

```
✅ Vercel 环境检测到，已启用 USE_GITHUB_DATA_ONLY 模式
   系统将优先使用 GitHub 数据包，不连接实时股市 API
================================================================================
📥 检测到 Vercel 环境，开始从 GitHub 下载股票数据...
   数据包 URL: https://github.com/...
================================================================================
📥 正在下载: https://github.com/...
   保存到: stock_data.tar.gz
   进度: 100.0% (XXX.X MB / XXX.X MB)
✅ 下载完成
📦 正在解压: stock_data.tar.gz
   包含 XXX 个文件/目录
✅ 解压完成
✅ 数据下载并解压成功！
📋 正在从K线文件列表生成股票列表...
✅ 股票列表生成成功！
✅ 股票数据已存在，跳过下载
```

### 数据已存在（跳过下载）

```
✅ 股票数据已存在，跳过下载
```

### 未设置 STOCK_DATA_URL

```
⚠️  未设置 STOCK_DATA_URL 环境变量（Vercel 环境）
   ⚠️  Vercel 环境：由于 USE_GITHUB_DATA_ONLY 模式，必须设置 STOCK_DATA_URL
   请在 Vercel Dashboard 中设置 STOCK_DATA_URL 指向 GitHub Releases 数据包
```

## 🎯 工作原理

### 启动流程

1. **环境检测**：系统检测到 Vercel 环境
2. **启用 GitHub 模式**：自动设置 `USE_GITHUB_DATA_ONLY=1`
3. **检查数据**：检查 `cache/` 和 `stock_data/` 目录是否存在数据
4. **下载数据包**：如果数据不存在且设置了 `STOCK_DATA_URL`，从 GitHub 下载
5. **解压数据包**：解压到项目根目录
6. **生成股票列表**：从 K 线文件列表自动生成 `stock_list_all.json`
7. **启动应用**：应用启动，使用本地缓存数据

### 数据使用

- **股票列表**：从 `cache/stock_list_all.json` 读取
- **日K线数据**：从 `cache/daily_kline/` 读取
- **周K线数据**：从 `cache/weekly_kline/` 读取
- **不连接实时 API**：`USE_GITHUB_DATA_ONLY` 模式下，所有实时 API 调用都被禁用

## ⚠️ 注意事项

### 1. 数据包更新

当需要更新数据时：

1. 上传新的数据包到 GitHub Releases
2. 更新 Vercel 环境变量 `STOCK_DATA_URL` 指向新的数据包 URL
3. 重新部署应用

### 2. Vercel 文件系统限制

- Vercel Serverless Functions 的文件系统是**临时**的
- 每次函数调用时，文件系统可能被重置
- 因此，数据包下载应该在**每次冷启动**时进行

### 3. 执行时间限制

- Vercel Hobby 计划：**10 秒**执行时间限制
- 数据包下载可能需要较长时间（取决于数据包大小）
- 如果下载超时，建议：
  - 减小数据包大小（只包含必要的数据）
  - 或使用 Vercel Pro 计划（更长的执行时间）

### 4. 缓存策略

- 系统会检查数据是否已存在，如果存在则跳过下载
- 但由于 Vercel 的文件系统是临时的，每次冷启动都需要重新下载

## 🔍 故障排查

### 问题 1：数据包下载失败

**症状：** 日志显示 "❌ 下载失败"

**解决方案：**
1. 检查 `STOCK_DATA_URL` 是否正确
2. 确认 GitHub Releases 中的数据包可以公开访问
3. 检查网络连接（Vercel 服务器到 GitHub）

### 问题 2：解压失败

**症状：** 日志显示 "❌ 解压失败"

**解决方案：**
1. 确认数据包格式正确（`.tar.gz`）
2. 检查数据包是否完整（文件大小）
3. 查看详细错误日志

### 问题 3：股票列表生成失败

**症状：** 日志显示 "⚠️ 股票列表生成失败"

**解决方案：**
1. 检查 K 线数据文件是否存在
2. 确认 `cache/daily_kline/` 和 `cache/weekly_kline/` 目录中有数据文件
3. 系统会继续运行，但可能需要从 API 获取股票列表（在非 `USE_GITHUB_DATA_ONLY` 模式下）

## 📝 总结

✅ **已完成**：Vercel 环境会自动从 GitHub 下载数据包  
✅ **已优化**：自动生成股票列表，无需手动操作  
✅ **已配置**：`USE_GITHUB_DATA_ONLY` 模式自动启用  

**下一步**：在 Vercel Dashboard 中设置 `STOCK_DATA_URL` 环境变量，然后重新部署。
