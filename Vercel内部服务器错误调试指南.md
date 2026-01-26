# 🔧 Vercel Internal Server Error 调试指南

## ❌ 错误信息

```
Internal Server Error
The server encountered an internal error.
```

## 🔍 调试步骤

### 1. 检查 Vercel 函数日志

**最重要**：查看 Vercel 函数日志以获取具体错误信息。

1. Vercel Dashboard → 项目 → Deployments → 最新部署
2. 点击 "Function Logs"
3. 查找错误信息（通常以 `❌` 或 `Error` 开头）

### 2. 测试健康检查端点

访问：
```
https://daniugu.vercel.app/api/health
```

**如果返回 JSON**：
- 查看 `error` 和 `error_detail` 字段
- 这些字段包含具体的错误信息

**如果返回 HTML**：
- 说明导入 `bull_stock_web` 失败
- 查看 Vercel 函数日志获取详细错误

### 3. 常见错误和解决方案

#### 错误 1: `ModuleNotFoundError: No module named 'flask'`

**原因**：依赖未安装

**解决方案**：
- 确保 `pyproject.toml` 包含所有依赖
- 检查构建日志，确认依赖安装成功

#### 错误 2: `导入 bull_stock_web 失败`

**原因**：`bull_stock_web.py` 导入时出错

**解决方案**：
1. 查看 Vercel 函数日志中的详细错误
2. 检查 `bull_stock_web.py` 的导入语句
3. 确保所有依赖都已安装

#### 错误 3: `analyzer_initialized: false`

**原因**：`BullStockAnalyzer` 初始化失败

**解决方案**：
- 检查 `trained_model.json` 是否存在
- 检查数据文件是否已下载
- 查看初始化日志

### 4. 改进的错误处理

已添加详细的错误日志：

```python
print("[api/index.py] 开始导入 bull_stock_web...")
print("[api/index.py] ✅ 成功获取 app 对象")
print("[api/index.py] ❌ 导入 bull_stock_web 失败: {error}")
```

这些日志会出现在 Vercel 函数日志中，帮助定位问题。

## 📋 检查清单

### 部署前检查

- [ ] `requirements.txt` 存在且包含所有依赖
- [ ] `pyproject.toml` 存在且包含所有依赖
- [ ] `trained_model.json` 存在
- [ ] `api/index.py` 存在且正确
- [ ] `bull_stock_web.py` 存在且可导入

### 部署后检查

- [ ] 构建日志显示依赖安装成功
- [ ] 函数日志显示 "✅ 成功导入 bull_stock_web"
- [ ] `/api/health` 返回 `{"success": true}`

## 🐛 如果仍然失败

### 手动触发重新部署

1. Vercel Dashboard → Deployments
2. 点击最新部署右侧的 "..." 菜单
3. 选择 "Redeploy"

### 检查环境变量

确保以下环境变量已设置：
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `STOCK_DATA_URL`（可选）

### 联系支持

如果问题持续存在，请提供：
1. Vercel 函数日志（完整错误堆栈）
2. `/api/health` 的响应（如果有）
3. 构建日志（如果有错误）

## 📝 总结

✅ **已改进**：添加了详细的错误日志  
✅ **已推送**：代码已推送到 GitHub  
⏳ **等待部署**：Vercel 会自动重新部署  

**请查看 Vercel 函数日志以获取具体错误信息！**
