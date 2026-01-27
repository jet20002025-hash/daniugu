# Vercel 缓存测试步骤

推送代码到 GitHub 后，按下面顺序测试「缓存是否在 /tmp 就绪」。

---

## 1. 等 Vercel 部署完成

1. 打开 [Vercel Dashboard](https://vercel.com/dashboard) → 你的项目。
2. 进入 **Deployments**，看最新一次部署状态是否为 **Ready**。
3. 若为 **Building** 或 **Error**，先等 Build 通过或按错误信息排查。

---

## 2. 确认环境变量

1. 项目 → **Settings** → **Environment Variables**。
2. 确认有 **STOCK_DATA_URL**，且值为可访问的 GitHub Release 数据包地址，例如：
   ```text
   https://github.com/jet20002025-hash/daniugu/releases/download/data-YYYYMMDD/stock_data_YYYYMMDD_HHMMSS.tar.gz
   ```
3. 若没有或地址错误，补全/修改后保存，并 **Redeploy** 一次（Deployments 右上角 ⋮ → Redeploy）。

---

## 3. 触发一次冷启动并测缓存状态

用浏览器或 `curl` 访问「检查缓存」接口（需先登录拿到 cookie，或用你实际带鉴权的接口）：

**方法 A：浏览器**

1. 打开：`https://www.daniugu.online/`（或你配置的域名）。
2. 登录后，在控制台或地址栏访问：
   ```text
   https://www.daniugu.online/api/check_cache_status
   ```

**方法 B：curl（需替换为你的 cookie 或鉴权方式）**

```bash
# 仅测接口是否可访问（若接口不强制登录，可直接用）
curl -s "https://www.daniugu.online/api/check_cache_status"
```

看返回 JSON 里的 `cache_exists` 和 `cached_stock_count`：

- **通过**：`"cache_exists": true` 且 `"cached_stock_count" > 0`
  - 说明 /tmp 下的缓存已就绪，check_cache_status 是从 `/tmp/cache` 读的。
- **未通过**：`"cache_exists": false` 或 `cached_stock_count === 0`
  - 继续做第 4 步。

---

## 4. 仍未就绪时：看 Vercel 日志

1. Vercel 项目 → **Deployments** → 最新一次部署 → 点进去。
2. 打开 **Functions** 或 **Logs**（不同版本入口可能写「Runtime Logs」或「Function Logs」）。
3. 再访问一次：`/api/check_cache_status` 或任意会触发你 serverless 的页面，以便产生新日志。
4. 在日志里搜：
   - `[api/index]`
   - `fetch_github_cache`
   - `LOCAL_CACHE_DIR`
   - 以及报错关键字：`Error`、`Exception`、`failed`。

把相关几行日志复制下来，便于排查是否：

- `STOCK_DATA_URL` 未生效；
- 下载/解压到 `/tmp` 失败；
- 超时或网络错误。

---

## 5. 再测「手动刷新缓存」

若 check_cache_status 已显示缓存存在，可再验证「手动刷新缓存」是否也走 /tmp：

1. 在页面上点「手动刷新缓存」，或请求：
   ```text
   GET https://www.daniugu.online/api/refresh_stock_cache?force=true
   ```
   （若该接口需要登录，请先带上登录态再请求。）

2. 再调一次 `GET /api/check_cache_status`，确认 `cache_exists` 仍为 `true` 且 `cached_stock_count` 合理。

---

## 6. 测试扫描是否用缓存

1. 在网页上进入「扫描」或对应功能。
2. 发起一次扫描，看是否能正常跑完、是否有“缓存不存在”类报错。
3. 若扫描正常且结果合理，说明整条链路（接口 → /tmp/cache → 扫描）都已在用新逻辑。

**若 check_cache 有缓存、但扫描仍报缓存不存在：** Vercel 每个实例的 `/tmp` 独立。建议先访问 `/api/cache_debug` 完成后再扫描，或重试扫描。

---

## 快速自检清单

- [ ] Vercel 最新部署为 **Ready**
- [ ] 环境变量 **STOCK_DATA_URL** 已设且可访问
- [ ] `GET /api/check_cache_status` 返回 `cache_exists: true`、`cached_stock_count > 0`
- [ ] 需要时看过 Vercel 日志，无 `fetch_github_cache` 相关报错
- [ ] 「手动刷新缓存」后，再次 check 仍为有缓存
- [ ] 扫描功能可正常使用、无缓存相关错误

若某一步结果和预期不符，把该步的操作方式、请求/响应和日志片段发出来，即可继续往下排查。
