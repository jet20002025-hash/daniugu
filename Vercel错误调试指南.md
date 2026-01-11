# 🔍 Vercel 错误调试指南

## 📋 当前错误

```
500: INTERNAL_SERVER_ERROR
Code: FUNCTION_INVOCATION_FAILED
```

## 🔧 已实施的修复

1. ✅ **改进导入逻辑**：更可靠的 Vercel 环境检测
2. ✅ **添加错误处理**：所有路由都有 try-catch
3. ✅ **健康检查端点**：`/api/health` 用于诊断
4. ✅ **改进初始化**：分析器初始化失败不会阻塞应用

## 📊 查看 Vercel 日志

### 方法一：在 Vercel Dashboard 查看

1. 登录 [Vercel Dashboard](https://vercel.com/dashboard)
2. 选择你的项目
3. 进入 **Deployments** 标签
4. 点击最新的部署
5. 查看 **"Function Logs"** 或 **"Build Logs"**

### 方法二：使用 Vercel CLI

```bash
# 安装 Vercel CLI
npm i -g vercel

# 登录
vercel login

# 查看日志
vercel logs [你的项目名] --follow
```

## 🔍 诊断步骤

### 步骤 1：测试健康检查端点

部署完成后，访问：
```
https://你的域名.vercel.app/api/health
```

应该返回：
```json
{
  "success": true,
  "status": "ok",
  "environment": "vercel",
  "analyzer_initialized": false
}
```

如果这个端点也返回 500，说明是基础导入问题。

### 步骤 2：检查环境变量

在 Vercel Dashboard → Settings → Environment Variables 确认：
- `INVITE_CODES` 已设置
- 值格式正确（用逗号分隔）

### 步骤 3：查看具体错误

在 Vercel Dashboard → Deployments → 最新部署 → Function Logs 中查看：
- 导入错误
- 初始化错误
- 运行时错误

## 🐛 常见错误及解决方案

### 错误 1：导入错误

**症状**：日志显示 `ModuleNotFoundError` 或 `ImportError`

**可能原因**：
- 模块路径问题
- 依赖未安装

**解决**：
- 检查 `api/index.py` 的路径设置
- 确认所有依赖都在 `requirements.txt` 中

### 错误 2：初始化超时

**症状**：日志显示超时或初始化失败

**可能原因**：
- `BullStockAnalyzer` 初始化时间过长
- 自动训练导致超时

**解决**：
- 已禁用自动训练（Vercel 环境）
- 如果仍有问题，可以进一步简化初始化

### 错误 3：模板文件未找到

**症状**：日志显示 `TemplateNotFound`

**可能原因**：
- 模板文件路径问题
- 模板文件未提交到 Git

**解决**：
- 确认 `templates/` 目录在仓库中
- 检查 `templates/login.html` 和 `templates/register.html` 是否存在

### 错误 4：认证模块错误

**症状**：日志显示认证相关错误

**可能原因**：
- `user_auth_vercel.py` 导入失败
- 环境变量未设置

**解决**：
- 检查 `user_auth_vercel.py` 是否在仓库中
- 确认环境变量 `INVITE_CODES` 已设置

## 🔄 快速修复方案

### 方案 A：简化版本（如果问题持续）

创建一个最小化的 `api/index.py`：

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'message': '系统运行中'})

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})
```

先确保基础功能正常，再逐步添加功能。

### 方案 B：检查依赖

确认 `requirements.txt` 中的所有依赖都能在 Vercel 上安装：

```bash
# 在本地测试
pip install -r requirements.txt
```

### 方案 C：使用 Vercel 日志

1. 在 Vercel Dashboard 查看详细日志
2. 找到具体的错误信息
3. 根据错误信息针对性修复

## 📝 下一步操作

1. **查看 Vercel 日志**
   - 进入 Vercel Dashboard
   - 查看最新的部署日志
   - 找到具体的错误信息

2. **测试健康检查**
   - 访问 `/api/health` 端点
   - 查看返回结果

3. **检查环境变量**
   - 确认 `INVITE_CODES` 已设置
   - 重新部署

4. **如果仍有问题**
   - 将 Vercel 日志中的具体错误信息发给我
   - 我可以根据具体错误进行修复

## 🔗 有用的链接

- [Vercel 日志文档](https://vercel.com/docs/monitoring/logs)
- [Vercel 错误处理](https://vercel.com/docs/errors)
- [Flask 部署到 Vercel](https://vercel.com/docs/frameworks/flask)

---

**请查看 Vercel 日志，找到具体的错误信息，然后告诉我，我可以进行针对性修复！**





