# 🔧 Render 登录问题修复指南

## 问题原因

**核心问题**：每次服务器重启时，Flask 会生成新的 `SECRET_KEY`，导致所有旧的 session cookie 失效。

在 Render 免费版中：
- 服务器不活跃时会休眠
- 休眠后首次访问会唤醒服务器（重启）
- 重启后生成新的 `SECRET_KEY`
- 旧的 session cookie 失效，用户需要重新登录

## 解决方案

### 方案 1：设置固定的 SECRET_KEY 环境变量（推荐）

1. **在 Render Dashboard 中设置环境变量**：
   - 进入你的 Web 服务
   - 点击 **"Environment"** 标签
   - 添加新的环境变量：
     - **Key**: `FLASK_SECRET_KEY`
     - **Value**: 一个随机字符串（例如：`bull-stock-secret-key-2024-xxxxx`）
   - 点击 **"Save Changes"**

2. **重新部署**：
   - 点击 **"Manual Deploy"** → **"Deploy latest commit"**

3. **生成安全的 SECRET_KEY**（可选）：
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

### 方案 2：清除浏览器缓存和 Cookie

如果暂时无法设置环境变量，可以：
1. **清除浏览器缓存和 Cookie**
2. **使用无痕模式**访问网站
3. **重新登录**

## 验证修复

运行诊断脚本：
```bash
python3 diagnose_render_login.py
```

如果显示 "✅ 后端登录功能正常"，说明后端已修复。

## 长期解决方案

### 1. 设置环境变量（必须）

在 Render Dashboard → Environment 中添加：
```
FLASK_SECRET_KEY=你的随机字符串
```

### 2. 使用 Redis Session Store（可选，更高级）

如果需要更可靠的 session 管理，可以考虑使用 Redis 存储 session：
- 配置 `SESSION_TYPE = 'redis'`
- 使用 `flask-session` 扩展

### 3. 升级到 Render 付费版（可选）

付费版不会自动休眠，减少重启频率。

## 当前状态

✅ 代码已更新：使用环境变量 `FLASK_SECRET_KEY`（如果设置）
⚠️ 需要操作：在 Render Dashboard 中设置 `FLASK_SECRET_KEY` 环境变量

## 快速测试

1. 清除浏览器缓存和 Cookie
2. 访问 https://daniugu.onrender.com/login
3. 使用账户：`super` / `superzwj`
4. 如果仍无法登录，检查 Render Dashboard → Logs 查看错误信息
