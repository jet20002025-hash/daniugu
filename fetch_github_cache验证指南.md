# 🧪 fetch_github_cache.py 验证指南

## ⚠️ Vercel 上为何会「缓存不存在」

Vercel Serverless 只有 `/tmp` 可写，项目根目录只读。因此：

1. **api/index.py** 在导入主应用前会：
   - 设置 `LOCAL_CACHE_DIR=/tmp/cache`
   - 调用 `fetch_github_cache(root_dir='/tmp')` 将数据解压到 `/tmp`（得到 `/tmp/cache`、`/tmp/stock_data`）
2. **data_fetcher**、**refresh_stock_cache**、**generate_stock_list_from_files** 等都会从 `LOCAL_CACHE_DIR` 读路径，因此会使用 `/tmp/cache`。

若你仍看到 `cache_exists: false`，请确认：

- Vercel 环境变量 **STOCK_DATA_URL** 已正确配置；
- 部署/函数冷启动时，`fetch_github_cache` 已执行且未报错（在 Vercel 日志中查看 `[api/index]` 相关输出）。

---

## 📋 验证方法总览

验证 `fetch_github_cache.py` 最小模型是否正常工作，有以下几种方法：

1. **本地验证**：在本地运行测试脚本
2. **Vercel 环境验证**：查看 Vercel 部署日志
3. **功能验证**：检查缓存文件是否存在，API 是否正常

---

## 1️⃣ 本地验证（推荐先做）

### 步骤 1：运行测试脚本

```bash
cd /Users/zwj/股票分析
python3 test_fetch_github_cache.py
```

**预期输出**：
- ✅ 模块导入成功
- ✅ 检查环境变量（如果设置了 `STOCK_DATA_URL`）
- ✅ 检查目录结构
- ✅ 测试 skip_if_exists 逻辑
- ✅ 测试无 URL 的情况

### 步骤 2：测试实际下载（可选）

如果已设置 `STOCK_DATA_URL` 环境变量，可以测试实际下载：

```bash
# 方法 1：直接运行脚本
export STOCK_DATA_URL='https://github.com/jet20002025-hash/daniugu/releases/download/data-YYYYMMDD/stock_data.tar.gz'
python3 fetch_github_cache.py

# 方法 2：在 Python 中调用
python3 -c "
from fetch_github_cache import fetch_github_cache
import os
root = os.path.dirname(os.path.abspath('fetch_github_cache.py'))
result = fetch_github_cache(skip_if_exists=False, root_dir=root)
print('✅ 下载成功' if result else '❌ 下载失败')
"
```

**预期结果**：
- 如果缓存已存在：输出 `缓存已就绪`，退出码 0
- 如果缓存不存在且 URL 有效：下载并解压，输出 `缓存已就绪`，退出码 0
- 如果 URL 无效或下载失败：输出 `获取失败`，退出码 1

### 步骤 3：验证文件结构

下载成功后，检查文件是否存在：

```bash
# 检查 cache 目录
ls -lh cache/ | head -10

# 检查 stock_data 目录
ls -lh stock_data/ | head -10

# 检查股票列表（如果自动生成）
ls -lh cache/stock_list_all.json
```

**预期结果**：
- `cache/daily_kline/` 目录存在，包含多个 `.csv` 文件
- `cache/weekly_kline/` 目录存在，包含多个 `.csv` 文件
- `stock_data/` 目录存在（如果有）
- `cache/stock_list_all.json` 文件存在（如果自动生成成功）

---

## 2️⃣ Vercel 环境验证

### 步骤 1：检查 Vercel 环境变量

在 Vercel Dashboard 中确认：

1. 进入项目设置 → Environment Variables
2. 确认 `STOCK_DATA_URL` 已设置
3. 确认 `USE_GITHUB_DATA_ONLY=1`（可选，Vercel 环境会自动设置）

### 步骤 2：查看部署日志

在 Vercel Dashboard → Deployments → 最新部署 → Logs 中查找：

**成功标志**：
```
[api/index] fetch_github_cache 跳过或失败: ...
```

如果看到：
- **无错误信息**：说明 `fetch_github_cache` 执行成功（可能缓存已存在，跳过下载）
- **有错误信息**：查看具体错误原因

**注意**：由于 `skip_if_exists=True`，如果缓存已存在，不会输出下载日志，这是正常的。

### 步骤 3：查看运行时日志

在 Vercel Dashboard → Functions → 查看函数日志，或通过 API 触发一次请求后查看：

```bash
# 触发一次请求（会触发冷启动）
curl https://www.daniugu.online/api/check_cache_status
```

然后在 Vercel Dashboard → Logs 中查找：
- `[api/index]` 开头的日志
- `fetch_github_cache` 相关的输出

### 步骤 4：检查缓存状态 API

访问缓存状态检查接口：

```bash
curl https://www.daniugu.online/api/check_cache_status
```

**预期响应**：
```json
{
  "success": true,
  "cache_exists": true,
  "cached_stock_count": 5000,
  "cache_age_hours": 2.5
}
```

如果 `cache_exists: true`，说明缓存已就绪。

---

## 3️⃣ 功能验证

### 验证 1：检查缓存文件数量

```bash
# 统计 cache 目录下的文件数
find cache/ -type f | wc -l

# 统计 daily_kline 文件数
find cache/daily_kline/ -name "*.csv" | wc -l

# 统计 weekly_kline 文件数
find cache/weekly_kline/ -name "*.csv" | wc -l
```

**预期结果**：
- `cache/` 下应该有数千个文件
- `daily_kline/` 和 `weekly_kline/` 下各有数千个 `.csv` 文件

### 验证 2：测试 API 是否能使用缓存

```bash
# 测试扫描接口（应该能使用缓存）
curl -X POST https://www.daniugu.online/api/scan_all_stocks \
  -H "Content-Type: application/json" \
  -d '{"max_results": 5}'
```

**预期结果**：
- 不返回 `cache_exists: false` 错误
- 能够正常扫描（如果其他条件满足）

### 验证 3：检查股票列表缓存

```bash
# 检查股票列表文件
ls -lh cache/stock_list_all.json

# 查看文件内容（前几行）
head -20 cache/stock_list_all.json
```

**预期结果**：
- 文件存在且大小合理（几 MB 到几十 MB）
- JSON 格式正确，包含股票代码和名称

---

## 4️⃣ 常见问题排查

### 问题 1：本地测试时提示 "获取失败"

**可能原因**：
- `STOCK_DATA_URL` 未设置
- URL 无效或无法访问
- 网络问题

**解决方法**：
```bash
# 检查环境变量
echo $STOCK_DATA_URL

# 手动设置（替换为实际 URL）
export STOCK_DATA_URL='https://github.com/jet20002025-hash/daniugu/releases/download/data-YYYYMMDD/stock_data.tar.gz'

# 测试 URL 是否可访问
curl -I $STOCK_DATA_URL
```

### 问题 2：Vercel 日志中没有 fetch_github_cache 相关输出

**可能原因**：
- `STOCK_DATA_URL` 未设置
- 缓存已存在，`skip_if_exists=True` 直接返回，无日志输出

**解决方法**：
- 检查 Vercel 环境变量是否设置
- 这是正常行为（如果缓存已存在，不会下载）

### 问题 3：下载成功但文件不存在

**可能原因**：
- 解压路径不正确
- 权限问题

**解决方法**：
```bash
# 检查当前工作目录
pwd

# 检查文件权限
ls -la cache/
ls -la stock_data/

# 手动测试解压
tar -tzf /tmp/test.tar.gz | head -10  # 查看压缩包内容
```

---

## 5️⃣ 验证清单

完成以下检查项，确认 `fetch_github_cache.py` 正常工作：

- [ ] 本地测试脚本运行成功
- [ ] 模块可以正常导入
- [ ] `skip_if_exists` 逻辑正确（有缓存时跳过）
- [ ] 无 URL 时正确返回 `False`
- [ ] Vercel 环境变量 `STOCK_DATA_URL` 已设置
- [ ] Vercel 部署日志无错误（或只有预期的跳过信息）
- [ ] `cache/` 目录存在且有内容
- [ ] `stock_data/` 目录存在（如果有）
- [ ] `cache/stock_list_all.json` 存在（如果自动生成）
- [ ] API `/api/check_cache_status` 返回 `cache_exists: true`
- [ ] 扫描接口不返回 `cache_exists: false` 错误

---

## 6️⃣ 快速验证命令

一键验证脚本：

```bash
cd /Users/zwj/股票分析

# 1. 运行测试脚本
python3 test_fetch_github_cache.py

# 2. 检查文件结构
echo "=== cache 目录 ==="
ls cache/ | head -5
echo "=== stock_data 目录 ==="
ls stock_data/ 2>/dev/null | head -5 || echo "stock_data 不存在"
echo "=== 股票列表 ==="
ls -lh cache/stock_list_all.json 2>/dev/null || echo "stock_list_all.json 不存在"

# 3. 统计文件数
echo "=== 文件统计 ==="
echo "cache 文件数: $(find cache/ -type f 2>/dev/null | wc -l)"
echo "daily_kline 文件数: $(find cache/daily_kline/ -name '*.csv' 2>/dev/null | wc -l)"
echo "weekly_kline 文件数: $(find cache/weekly_kline/ -name '*.csv' 2>/dev/null | wc -l)"
```

---

## 📝 总结

验证 `fetch_github_cache.py` 的核心是：

1. **本地验证**：确保模块可以正常导入和运行
2. **Vercel 验证**：确保在 Vercel 环境中能正常执行
3. **功能验证**：确保下载的文件存在且 API 能正常使用

如果所有验证都通过，说明最小模型工作正常！✅
