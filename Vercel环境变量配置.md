# 🔧 Vercel 环境变量配置

## 📋 必需的环境变量

### INVITE_CODES

**用途**：存储可用的邀请码列表

**配置方法**：
1. 进入 Vercel Dashboard
2. 选择项目 → Settings → Environment Variables
3. 点击 "Add New"
4. 填写：
   - **Key**: `INVITE_CODES`
   - **Value**: `ADMIN2024,VIP2024,NEWCODE2024`（用逗号分隔）
   - **Environment**: 选择所有环境（Production, Preview, Development）
5. 点击 "Save"

**示例值**：
```
ADMIN2024,VIP2024,NEWCODE2024,DEMO2024
```

**说明**：
- 多个邀请码用逗号分隔
- 不区分大小写（会自动转换为大写）
- 每个邀请码默认只能使用 1 次

## 🔄 自动设置的环境变量

Vercel 会自动设置以下环境变量（无需手动配置）：

- `VERCEL=1` - 标识 Vercel 环境
- `VERCEL_ENV` - 环境类型（production/preview/development）

这些变量用于：
- 自动选择使用 `user_auth_vercel.py`（内存存储）
- 禁用自动训练（避免超时）

## 📝 配置步骤

### 步骤 1：添加环境变量

1. 登录 [Vercel Dashboard](https://vercel.com/dashboard)
2. 选择你的项目
3. 进入 **Settings** → **Environment Variables**
4. 添加 `INVITE_CODES` 变量

### 步骤 2：重新部署

环境变量添加后，需要重新部署才能生效：

1. 进入 **Deployments** 标签
2. 找到最新的部署
3. 点击 **"..."** → **"Redeploy"**
4. 或等待下次自动部署

## ✅ 验证配置

部署后，访问网站：
1. 访问 `/register` 页面
2. 尝试使用环境变量中配置的邀请码注册
3. 如果成功，说明配置正确

## 🔒 安全建议

1. **不要提交邀请码到 Git**
   - 邀请码应只存储在环境变量中
   - `.gitignore` 已配置排除相关文件

2. **定期更换邀请码**
   - 定期更新 `INVITE_CODES` 环境变量
   - 移除已使用的邀请码

3. **使用强邀请码**
   - 使用复杂的邀请码（如：`VIP2024-ABC123-XYZ789`）
   - 避免使用简单的邀请码

## 🐛 常见问题

### 问题 1：邀请码无效

**原因**：环境变量未配置或未重新部署

**解决**：
1. 检查环境变量是否正确配置
2. 重新部署项目
3. 确认环境变量在所有环境中都设置了

### 问题 2：注册后数据丢失

**原因**：当前使用内存存储，重启后数据会丢失

**解决**：
- 这是预期行为（演示版本）
- 生产环境应使用 Vercel KV 或数据库

---

**配置完成后，重新部署即可使用！**



