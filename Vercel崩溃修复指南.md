# 🔧 Vercel Serverless Function 崩溃修复指南

## ❌ 错误信息

```
500: INTERNAL_SERVER_ERROR
Code: FUNCTION_INVOCATION_FAILED
```

## 🔍 问题原因

在 Vercel 环境中，`DataFetcher` 在初始化时需要检测 `USE_GITHUB_DATA_ONLY` 环境变量，但该变量在模块导入时还没有设置。

**执行顺序问题**：
1. `api/index.py` 导入 `bull_stock_web`
2. `bull_stock_web` 导入时可能创建 `DataFetcher` 实例
3. `DataFetcher.__init__()` 检测 `USE_GITHUB_DATA_ONLY`，但此时还未设置
4. `if __name__ == '__main__':` 块中的设置代码还未执行

## ✅ 已修复

### 1. 在 `api/index.py` 中提前设置环境变量

在导入 `bull_stock_web` **之前**设置 `USE_GITHUB_DATA_ONLY`：

```python
# ✅ 在导入前设置 USE_GITHUB_DATA_ONLY，确保 DataFetcher 能正确检测
os.environ['USE_GITHUB_DATA_ONLY'] = '1'
```

### 2. 优化 `data_fetcher.py` 的环境检测逻辑

改进了 Vercel 环境检测，支持多种检测方式：

```python
# 检测 Vercel 环境（多种方式）
is_vercel_env = (
    os.environ.get('VERCEL') == '1' or 
    os.environ.get('VERCEL_ENV') is not None or
    os.environ.get('VERCEL_URL') is not None
)
# 在 Vercel 环境中自动启用 GitHub 数据包模式
self._use_github_data_only = use_github_only or is_vercel_env
```

## 📋 验证修复

### 1. 重新部署

代码已推送到 GitHub，Vercel 会自动重新部署。

### 2. 检查日志

部署后，查看 Vercel 函数日志，应该看到：

```
✅ 成功导入 bull_stock_web，app 对象已准备就绪
```

而不是：

```
❌ 导入 bull_stock_web 失败: ...
```

### 3. 测试健康检查

访问：
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

## 🐛 如果仍然失败

### 检查 Vercel 日志

1. Vercel Dashboard → 项目 → Deployments → 最新部署
2. 点击 "Function Logs"
3. 查看具体错误信息

### 常见问题

1. **导入错误**：检查 `requirements.txt` 是否包含所有依赖
2. **环境变量**：确保 `UPSTASH_REDIS_REST_URL` 和 `UPSTASH_REDIS_REST_TOKEN` 已设置
3. **数据包**：确保 `STOCK_DATA_URL` 指向有效的 GitHub Releases URL

### 调试步骤

1. **检查导入**：
   ```python
   # 在 api/index.py 中添加
   print(f"[DEBUG] VERCEL={os.environ.get('VERCEL')}")
   print(f"[DEBUG] USE_GITHUB_DATA_ONLY={os.environ.get('USE_GITHUB_DATA_ONLY')}")
   ```

2. **检查 DataFetcher 初始化**：
   ```python
   # 在 data_fetcher.py 的 __init__ 中添加
   print(f"[DEBUG] _is_vercel={self._is_vercel}")
   print(f"[DEBUG] _use_github_data_only={self._use_github_data_only}")
   ```

## 📝 总结

✅ **已修复**：在导入前设置环境变量  
✅ **已优化**：改进 Vercel 环境检测逻辑  
✅ **已推送**：代码已推送到 GitHub  

---

**修复已推送，请等待 Vercel 重新部署后测试！**
