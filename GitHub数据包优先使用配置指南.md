# 🚀 优先使用 GitHub 数据包配置指南

## ✅ 已完成的优化

系统已优化为**优先使用 GitHub 数据包**，**不连接实时股市数据库**，大幅提高速度。

## 🔧 修改内容

### 1. 自动检测 Vercel 环境

在 Vercel 环境中，系统会自动启用 `USE_GITHUB_DATA_ONLY` 模式：
- ✅ 只使用本地缓存/GitHub 数据包
- ❌ 不连接 akshare/sina 等实时 API
- ⚡ 大幅提高响应速度

### 2. 修改的方法

以下方法已优化，优先使用本地缓存：

- `get_all_stocks()` - 股票列表获取
- `get_daily_kline()` - 日K线数据
- `get_weekly_kline()` - 周K线数据
- `get_daily_kline_range()` - 指定日期范围的日K线
- `get_circulating_shares()` - 流通股本（禁用实时 API）
- `get_market_cap()` - 总市值（禁用实时 API）
- `calculate_circulating_market_cap()` - 流通市值（禁用实时 API）

## 📋 Vercel 环境配置

### 自动启用（推荐）

在 Vercel 环境中，系统**自动检测**并启用 GitHub 数据包模式，无需手动配置。

### 手动启用（可选）

如果需要手动启用，在 Vercel Dashboard 设置环境变量：

```
USE_GITHUB_DATA_ONLY=1
```

## 📦 GitHub 数据包准备

### 1. 确保数据包已上传

确保 GitHub Releases 中已有最新的股票数据包：
- `cache/daily_kline/` - 日K线数据
- `cache/weekly_kline/` - 周K线数据
- `cache/stock_list_all.json` - 股票列表（可选，会自动生成）

### 2. 设置环境变量

在 Vercel Dashboard 设置：

```
STOCK_DATA_URL=https://github.com/jet20002025-hash/daniugu/releases/download/data-YYYYMMDD/stock_data.tar.gz
```

**注意**：将 `YYYYMMDD` 替换为实际的日期标签。

## 🎯 使用效果

### 速度提升

- **之前**：每次扫描需要连接 akshare API，耗时 10-30 秒
- **现在**：直接从本地缓存读取，耗时 < 1 秒

### 稳定性提升

- **之前**：依赖外部 API，可能超时或失败
- **现在**：使用本地数据包，稳定可靠

### 成本降低

- **之前**：每次请求都调用外部 API
- **现在**：只使用本地数据，无 API 调用成本

## 🔍 验证配置

### 检查日志

部署后，查看 Vercel 函数日志，应该看到：

```
✅ Vercel 环境检测到，已启用 USE_GITHUB_DATA_ONLY 模式
   系统将优先使用 GitHub 数据包，不连接实时股市 API
```

### 检查数据获取

在扫描时，日志应该显示：

```
[get_all_stocks] ⚠️  USE_GITHUB_DATA_ONLY 模式：只使用缓存，不连接实时 API
[get_all_stocks] ✅ 从缓存获取 XXXX 只股票
```

而不是：

```
[get_all_stocks] ⚠️ 缓存中没有股票列表，开始从 akshare API 获取...
```

## ⚠️ 注意事项

### 1. 数据更新

GitHub 数据包需要定期更新：
- 建议每日收盘后更新数据包
- 上传到 GitHub Releases
- 更新 `STOCK_DATA_URL` 环境变量

### 2. 缺失数据

如果某个股票的数据不在缓存中：
- 系统会返回 `None`（不会尝试从 API 获取）
- 需要确保数据包包含所有需要的股票数据

### 3. 本地开发

本地开发时，如果需要测试实时 API：
- 不设置 `USE_GITHUB_DATA_ONLY` 环境变量
- 系统会回退到使用实时 API

## 📝 总结

✅ **已优化**：系统优先使用 GitHub 数据包，不连接实时 API  
✅ **自动启用**：Vercel 环境自动检测并启用  
✅ **速度提升**：响应时间从 10-30 秒降低到 < 1 秒  
✅ **稳定性提升**：不依赖外部 API，更稳定可靠  

---

**配置已优化并推送，请重新部署 Vercel 项目以生效！**
