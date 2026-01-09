# 🔧 Vercel 邀请码配置说明

## ❌ 问题描述

在 Vercel 环境中注册时，使用本地生成的邀请码（如 `gVshGk`, `7RKNQU` 等）提示"邀请码无效"。

## 🔍 原因分析

1. **本地环境**：邀请码存储在 `invite_codes.json` 文件中
2. **Vercel 环境**：邀请码从以下位置读取（按优先级）：
   - Upstash Redis（如果已配置）
   - Vercel KV（如果已配置）
   - 环境变量 `INVITE_CODES`（如果已配置）
   - 默认值 `'ADMIN2024,VIP2024'`（如果以上都没有配置）

3. **问题**：本地生成的邀请码没有同步到 Vercel 环境，所以 Vercel 环境中只有默认的 `ADMIN2024` 和 `VIP2024` 两个邀请码。

## ✅ 解决方案

### 方案一：配置 Vercel 环境变量（推荐，最简单）

#### 步骤 1：获取所有邀请码

当前可用的邀请码（共 10 个）：
```
gVshGk,7RKNQU,YAwbpT,jFmWyg,bUudRj,MRZ2Nn,ZAq7wr,7nWHCG,vsxBmJ,23kNsZ
```

#### 步骤 2：在 Vercel Dashboard 中配置环境变量

1. **访问 Vercel Dashboard**
   - 打开 https://vercel.com/dashboard
   - 登录你的账号

2. **选择项目**
   - 找到并点击项目 `daniugu`

3. **进入环境变量设置**
   - 点击顶部的 **Settings** 标签
   - 在左侧菜单中选择 **Environment Variables**

4. **添加环境变量**
   - 点击 **"Add New"** 按钮
   - 填写以下内容：
     - **Key**: `INVITE_CODES`
     - **Value**: `gVshGk,7RKNQU,YAwbpT,jFmWyg,bUudRj,MRZ2Nn,ZAq7wr,7nWHCG,vsxBmJ,23kNsZ`
   - **环境选择**：勾选所有环境
     - ✅ Production
     - ✅ Preview
     - ✅ Development
   - 点击 **"Save"** 保存

5. **重新部署项目**
   - 进入 **Deployments** 标签
   - 找到最新的部署记录
   - 点击右侧的 **"..."** 菜单
   - 选择 **"Redeploy"**
   - 确认重新部署

#### 验证配置

部署完成后，邀请码应该可以正常使用了。

---

### 方案二：使用 Upstash Redis 持久化存储（推荐，更灵活）

如果你已经配置了 Upstash Redis，可以使用同步脚本将邀请码保存到 Redis：

#### 步骤 1：配置 Upstash Redis 环境变量

在 Vercel Dashboard 中添加以下环境变量：
- `UPSTASH_REDIS_REST_URL`: 你的 Upstash Redis REST URL
- `UPSTASH_REDIS_REST_TOKEN`: 你的 Upstash Redis REST Token

#### 步骤 2：运行同步脚本

```bash
# 在本地运行同步脚本
python3 sync_invite_codes_to_vercel.py

# 选择选项 1：同步到 Upstash Redis
```

#### 步骤 3：重新部署项目

在 Vercel Dashboard 中重新部署项目。

---

### 方案三：使用 Vercel KV 持久化存储

如果你已经配置了 Vercel KV，可以使用同步脚本将邀请码保存到 KV：

#### 步骤 1：确保 Vercel KV 已配置

在 Vercel Dashboard 中：
- 进入项目设置 → Storage
- 创建或连接 Vercel KV 数据库

#### 步骤 2：运行同步脚本

```bash
# 在本地运行同步脚本
python3 sync_invite_codes_to_vercel.py

# 选择选项 2：同步到 Vercel KV
```

#### 步骤 3：重新部署项目

在 Vercel Dashboard 中重新部署项目。

---

## 📝 注意事项

1. **邀请码大小写**：邀请码在验证时会统一转换为大写，所以无论输入大写还是小写都可以。

2. **环境变量格式**：多个邀请码用逗号分隔，不要有空格，例如：
   ```
   ✅ 正确: gVshGk,7RKNQU,YAwbpT
   ❌ 错误: gVshGk, 7RKNQU, YAwbpT  （有空格）
   ```

3. **添加新邀请码**：
   - 在本地使用 `python3 create_invite_code.py generate 10 1` 生成新邀请码
   - 更新 Vercel 环境变量 `INVITE_CODES`，添加新的邀请码（用逗号分隔）
   - 重新部署项目

4. **持久化存储优先级**：
   - 如果配置了 Upstash Redis 或 Vercel KV，系统会优先从持久化存储读取邀请码
   - 环境变量 `INVITE_CODES` 只在持久化存储为空时作为初始值使用

---

## 🔄 生成新的邀请码

如果需要生成新的邀请码：

```bash
# 生成 10 个新的邀请码
python3 create_invite_code.py generate 10 1

# 查看所有邀请码
python3 create_invite_code.py list
```

然后更新 Vercel 环境变量 `INVITE_CODES`，包含所有可用的邀请码。

---

## 🐛 故障排查

如果配置后仍然提示"邀请码无效"：

1. **检查环境变量是否配置正确**
   - 在 Vercel Dashboard 中确认 `INVITE_CODES` 环境变量已添加
   - 确认环境变量值格式正确（用逗号分隔，无空格）

2. **检查是否已重新部署**
   - 环境变量修改后必须重新部署才能生效
   - 在 Vercel Dashboard 中确认最新的部署记录

3. **检查持久化存储**
   - 如果配置了 Upstash Redis 或 Vercel KV，检查存储中是否有邀请码数据
   - 如果没有，运行同步脚本将邀请码保存到持久化存储

4. **检查后端日志**
   - 在 Vercel Dashboard 中查看 Function Logs
   - 查看是否有错误信息或警告信息

---

## 📞 联系支持

如果以上方法都无法解决问题，请提供以下信息：
- Vercel 部署日志
- 环境变量配置截图
- 使用的邀请码（可以脱敏）

