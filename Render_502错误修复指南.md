# 🔧 Render 502 错误修复指南

## ❌ 问题：HTTP 502 Bad Gateway

**错误信息**：`daniugu.onrender.com 目前无法处理此请求。HTTP ERROR 502`

**原因**：应用无法正常响应请求，可能是：
1. Flask 开发服务器在生产环境中不稳定
2. 应用启动后崩溃
3. 健康检查失败

---

## ✅ 解决方案：使用 Gunicorn

对于生产环境，建议使用 **Gunicorn**（生产级 WSGI 服务器）而不是 Flask 开发服务器。

### 步骤 1：已添加 Gunicorn 支持

我已经在代码中添加了 Gunicorn 支持：

1. **在 `requirements.txt` 中添加了 `gunicorn>=20.1.0`**
2. **修改了 `Procfile`**：
   ```
   web: gunicorn bull_stock_web:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile -
   ```

### 步骤 2：确认 Render Start Command

在 Render Dashboard 中：

1. **进入你的 Web 服务**
   - 点击服务名称进入详情页

2. **进入 Settings**
   - 点击 **"Settings"** 标签

3. **检查 Start Command**
   - 找到 **"Start Command"** 字段
   - 应该显示：`gunicorn bull_stock_web:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile -`
   - 或者留空（Render 会自动使用 Procfile）

**注意**：如果 Start Command 字段显示 `python bull_stock_web.py`，需要修改为使用 gunicorn。

### 步骤 3：重新部署

1. **推送代码到 GitHub**（已完成）
2. **在 Render Dashboard 中重新部署**
   - 点击 **"Manual Deploy"** → **"Deploy latest commit"**
   - 或等待 Render 自动检测到代码更新

---

## 🔍 检查部署状态

### 步骤 1：查看构建日志

在 Render Dashboard → Logs 中，查看构建过程：

**应该看到**：
```
==> Running build command 'pip install -r requirements.txt'...
Collecting gunicorn>=20.1.0
  Downloading gunicorn-21.2.0-py3-none-any.whl
...
Successfully installed gunicorn-21.2.0 ...
```

### 步骤 2：查看启动日志

**应该看到**：
```
==> Running 'gunicorn bull_stock_web:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile -'
[INFO] Starting gunicorn 21.2.0
[INFO] Listening at: http://0.0.0.0:10000
[INFO] Using worker: sync
[INFO] Booting worker with pid: ...
✅ 使用 Upstash Redis 持久化存储
[环境检测] Render环境检测到，使用Redis存储（user_auth_vercel）
✅ 创建默认测试用户: super (超级用户)
✅ 创建默认测试用户: vip (VIP用户)
✅ 创建默认测试用户: free (免费用户)
✅ 默认测试用户已初始化
```

### 步骤 3：测试访问

1. **等待部署完成**（通常 2-3 分钟）
2. **访问应用 URL**
   - Render URL：`https://daniugu.onrender.com`
   - 或自定义域名：`https://www.daniugu.online`
3. **确认可以正常访问**（不再显示 502 错误）

---

## ⚠️ 如果仍然出现 502 错误

### 检查 1：查看完整日志

在 Render Dashboard → Logs 中，查看：
- 是否有错误信息？
- 应用是否正常启动？
- Gunicorn 是否正常运行？

### 检查 2：确认环境变量

确保已配置：
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`

### 检查 3：检查应用状态

在 Render Dashboard 中：
- 服务状态是否为 `Live`？
- 健康检查是否为绿色？

### 检查 4：尝试手动启动命令

如果问题仍然存在，可以尝试：

1. **在 Render Dashboard → Settings → Start Command**
2. **修改为**：
   ```
   gunicorn bull_stock_web:app --bind 0.0.0.0:$PORT --workers 1 --timeout 300 --access-logfile - --error-logfile -
   ```
3. **保存并重新部署**

**说明**：
- `--workers 1`：使用 1 个 worker（减少资源消耗）
- `--timeout 300`：增加超时时间到 300 秒

---

## 📊 Gunicorn 配置说明

### 当前配置

```
gunicorn bull_stock_web:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --access-logfile - --error-logfile -
```

**参数说明**：
- `bull_stock_web:app`：应用模块和 Flask app 对象
- `--bind 0.0.0.0:$PORT`：绑定到所有网络接口，使用 Render 提供的 PORT 环境变量
- `--workers 2`：使用 2 个 worker 进程（可以处理并发请求）
- `--timeout 120`：请求超时时间 120 秒（适合长时间扫描任务）
- `--access-logfile -`：访问日志输出到标准输出（在 Render Logs 中查看）
- `--error-logfile -`：错误日志输出到标准输出（在 Render Logs 中查看）

### 如果资源不足，可以调整

**减少 worker 数量**（如果内存不足）：
```
gunicorn bull_stock_web:app --bind 0.0.0.0:$PORT --workers 1 --timeout 300 --access-logfile - --error-logfile -
```

**增加超时时间**（如果扫描任务很长）：
```
gunicorn bull_stock_web:app --bind 0.0.0.0:$PORT --workers 2 --timeout 600 --access-logfile - --error-logfile -
```

---

## ✅ 修复检查清单

- [ ] 已添加 `gunicorn>=20.1.0` 到 `requirements.txt`
- [ ] 已修改 `Procfile` 使用 gunicorn
- [ ] 代码已推送到 GitHub
- [ ] 在 Render Dashboard 重新部署
- [ ] 查看构建日志，确认 gunicorn 已安装
- [ ] 查看启动日志，确认 gunicorn 正常运行
- [ ] 测试访问应用，确认不再出现 502 错误
- [ ] 测试登录功能，确认可以正常登录

---

## 🎉 完成！

使用 Gunicorn 后，应用应该更稳定，不再出现 502 错误。

如果仍然有问题，请查看 Render Dashboard → Logs 中的详细错误信息，并告诉我具体的错误内容。

