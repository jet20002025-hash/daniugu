# Vercel 分批扫描功能说明

## 📋 功能概述

为了解决 Vercel serverless 环境的 10 秒执行时间限制，实现了**分批处理 + Upstash Redis 存储**方案，可以将 10 分钟的扫描任务拆分成多个小批次完成。

## 🔧 工作原理

1. **分批处理**：将扫描任务分成多个小批次，每批约 50 只股票（5-10 秒内完成）
2. **持久化存储**：使用 Upstash Redis 存储扫描进度和结果
3. **自动继续**：前端自动调用下一批次，直到所有批次完成

## 📦 需要的配置

### 1. 创建 Upstash Redis 数据库

1. 访问 [Upstash Console](https://console.upstash.com/)
2. 注册/登录账号
3. 点击 "Create Database"
4. 选择 "Redis" 类型
5. 选择免费计划（Free Tier）
6. 创建数据库

### 2. 获取连接信息

创建数据库后，在数据库详情页面可以看到：
- **REST URL**：类似 `https://xxx-xxx.upstash.io`
- **REST Token**：类似 `AXxxxxx...`

### 3. 在 Vercel 配置环境变量

1. 进入 Vercel Dashboard → 你的项目 → Settings → Environment Variables
2. 添加以下环境变量：

```
UPSTASH_REDIS_REST_URL=https://xxx-xxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=AXxxxxx...
```

3. 点击 "Save"
4. 重新部署项目（Vercel 会自动检测到新环境变量并重新部署）

## 🚀 使用流程

1. **用户点击"扫描全市场"**
   - 后端处理第一批（50 只股票）
   - 生成 `scan_id` 并保存进度到 Redis
   - 返回 `scan_id` 和批次信息

2. **前端自动继续**
   - 检测到 `scan_id` 和 `has_more: true`
   - 自动调用 `/api/continue_scan` 处理下一批次
   - 更新进度显示

3. **重复直到完成**
   - 每批完成后自动处理下一批
   - 所有批次完成后显示最终结果

## 📊 API 说明

### `/api/scan_all_stocks` (POST)

启动扫描任务（Vercel 环境会自动使用分批模式）

**请求体：**
```json
{
  "min_match_score": 0.97,
  "max_market_cap": 100.0,
  "limit": null
}
```

**响应（Vercel 环境）：**
```json
{
  "success": true,
  "scan_id": "uuid-string",
  "message": "扫描已开始（共 100 批），已处理第 1 批",
  "progress": {...},
  "batch": 1,
  "total_batches": 100,
  "has_more": true
}
```

### `/api/continue_scan` (POST)

继续处理下一批次

**请求体：**
```json
{
  "scan_id": "uuid-string"
}
```

**响应：**
```json
{
  "success": true,
  "message": "第 2/100 批处理完成",
  "progress": {...},
  "batch": 2,
  "total_batches": 100,
  "has_more": true,
  "is_complete": false
}
```

### `/api/get_progress` (GET)

获取扫描进度（Vercel 环境从 Redis 读取）

**查询参数：**
- `scan_id`: 扫描任务ID（可选）

**响应：**
```json
{
  "success": true,
  "progress": {
    "type": "scan",
    "scan_id": "uuid-string",
    "current": 50,
    "total": 5000,
    "status": "进行中",
    "detail": "正在扫描第 1/100 批...",
    "percentage": 1.0,
    "found": 5,
    "batch": 1,
    "total_batches": 100
  }
}
```

## ⚠️ 注意事项

1. **Upstash Redis 免费计划限制**：
   - 10,000 次命令/天
   - 256 MB 存储
   - 足够支持日常使用

2. **批次大小**：
   - 默认每批 50 只股票
   - 可以根据实际情况调整（在 `bull_stock_web.py` 中修改 `batch_size`）

3. **超时处理**：
   - 每只股票最多处理 8 秒
   - 如果超时，自动跳过该股票

4. **错误处理**：
   - 如果某批次失败，会自动尝试继续下一批次
   - 进度信息保存在 Redis 中，不会丢失

## 🔍 故障排查

### 问题：扫描无法继续

**检查：**
1. 确认 Upstash Redis 环境变量已正确配置
2. 检查 Vercel 日志，查看是否有错误信息
3. 确认 Redis 数据库状态正常

### 问题：进度丢失

**原因：** Redis 数据过期（默认 TTL 2 小时）

**解决：** 在 `scan_progress_store.py` 中增加 TTL 时间

### 问题：批次处理失败

**检查：**
1. 查看浏览器控制台错误信息
2. 检查 Vercel 函数日志
3. 确认网络连接正常

## 📝 代码文件

- `scan_progress_store.py` - Redis 存储模块
- `vercel_scan_helper.py` - 分批处理逻辑
- `bull_stock_web.py` - API 路由（已修改）
- `templates/bull_stock_web.html` - 前端代码（已修改）

## 🎯 优势

1. ✅ **突破时间限制**：可以在 10 秒限制下完成 10 分钟的任务
2. ✅ **状态持久化**：进度保存在 Redis，不会丢失
3. ✅ **自动处理**：前端自动调用下一批次，无需手动操作
4. ✅ **错误恢复**：单批次失败不影响其他批次
5. ✅ **免费使用**：Upstash Redis 免费计划足够使用



