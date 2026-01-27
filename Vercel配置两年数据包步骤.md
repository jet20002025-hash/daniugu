# Vercel 配置 2024-2025 两年数据包步骤

## ✅ 已完成

- [x] 创建两年数据包：`stock_data_2024_2025_20260127_120927.tar.gz`（259MB）
- [x] 上传到 GitHub Releases：`data20260127`

---

## 📋 下一步：在 Vercel 中配置

### 1. 获取下载 URL

从 GitHub Release 页面获取：

1. 打开：https://github.com/jet20002025-hash/daniugu/releases/tag/data20260127
2. 在 "Assets" 部分，找到 `stock_data_2024_2025_20260127_120927.tar.gz`
3. **右键点击文件名** → **"复制链接地址"**，或直接点击文件名，复制浏览器地址栏的 URL

**下载 URL 格式：**
```
https://github.com/jet20002025-hash/daniugu/releases/download/data20260127/stock_data_2024_2025_20260127_120927.tar.gz
```

**可选（tag `data20242025`）：**
```
STOCK_DATA_URL=https://github.com/jet20002025-hash/daniugu/releases/download/data20242025/stock_data_2024_2025_20260127_120927.tar.gz
```

---

### 2. 在 Vercel Dashboard 中设置环境变量

1. 打开 Vercel Dashboard：https://vercel.com/dashboard
2. 进入你的项目（daniugu）
3. 进入 **Settings** → **Environment Variables**
4. 找到或创建环境变量 **`STOCK_DATA_URL`**
5. **Value** 填入上面复制的下载 URL
6. 确保勾选了所有环境（Production、Preview、Development）
7. 点击 **Save**

---

### 3. 重新部署（如果需要）

如果 Vercel 提示需要重新部署：

1. 进入 **Deployments** 页面
2. 点击最新部署右侧的 **⋮**（三个点）
3. 选择 **Redeploy**

或者直接触发一次新的部署（例如推送代码到 GitHub）。

---

### 4. 测试连接

部署完成后，访问：

```
https://www.daniugu.online/api/cache_debug
```

**预期结果：**
```json
{
  "success": true,
  "vercel": true,
  "has_stock_data_url": true,
  "local_cache_dir": "/tmp/cache",
  "tmp_cache_exists": true,
  "tmp_has_stock_list": true,
  "tmp_has_weekly_kline": true,
  "tmp_has_daily_kline": true,
  "fetch_attempted": true,
  "fetch_ok": true
}
```

如果 `fetch_ok: true` 且 `tmp_cache_exists: true`，说明数据包已成功下载并解压到 `/tmp/cache`！

---

### 5. 测试扫描功能

如果缓存状态正常，可以测试扫描功能：

1. 登录网站：https://www.daniugu.online/
2. 点击「扫描」按钮
3. 应该不再出现「缓存不存在」的错误

---

## 🔍 如果仍然失败

如果 `cache_debug` 返回 `fetch_ok: false` 或 `tmp_cache_exists: false`：

1. **检查 Vercel 日志**：
   - Vercel Dashboard → Deployments → 最新部署 → Logs
   - 查找 `[api/index]` 或 `fetch_github_cache` 相关日志
   - 查看是否有错误信息

2. **检查环境变量**：
   - 确认 `STOCK_DATA_URL` 已正确设置
   - 确认 URL 可以正常访问（在浏览器中打开应该能下载）

3. **检查下载 URL**：
   - 在浏览器中打开 `STOCK_DATA_URL` 的值
   - 应该能直接下载 `.tar.gz` 文件
   - 如果返回 404，说明 URL 不正确

---

## 📝 快速检查清单

- [ ] GitHub Release 已创建：`data20260127`
- [ ] 数据包已上传：`stock_data_2024_2025_20260127_120927.tar.gz`（259MB）
- [ ] 已获取下载 URL
- [ ] Vercel 环境变量 `STOCK_DATA_URL` 已设置
- [ ] 已重新部署（如果需要）
- [ ] `/api/cache_debug` 返回 `fetch_ok: true`
- [ ] `/api/check_cache_status` 返回 `cache_exists: true`

---

## 💡 提示

- 数据包大小：259MB（压缩后），解压后约 300-500MB
- 日期范围：2024-01-01 至 2025-12-31（仅两年数据）
- 相比原来的多年数据包（~450MB），体积减小约 42%，更适合 Vercel 的 /tmp 限制
