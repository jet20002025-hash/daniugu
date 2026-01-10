# ⚡ Vercel 邀请码配置快速指南

## ❌ 问题：邀请码无效

**原因**：Vercel 环境中没有配置这些邀请码，系统只使用默认值 `ADMIN2024,VIP2024`。

## ✅ 解决方案（3步完成）

### 步骤 1：获取邀请码列表

所有可用的邀请码（共 10 个，用逗号分隔）：
```
gVshGk,7RKNQU,YAwbpT,jFmWyg,bUudRj,MRZ2Nn,ZAq7wr,7nWHCG,vsxBmJ,23kNsZ
```

### 步骤 2：在 Vercel Dashboard 配置

1. **访问 Vercel Dashboard**
   - 打开：https://vercel.com/dashboard
   - 登录你的账号

2. **进入项目设置**
   - 找到并点击项目 `daniugu`
   - 点击顶部的 **Settings**（设置）标签
   - 在左侧菜单中选择 **Environment Variables**（环境变量）

3. **添加环境变量**
   - 点击 **"Add New"** 按钮
   - 填写：
     - **Key**（变量名）: `INVITE_CODES`
     - **Value**（变量值）: `gVshGk,7RKNQU,YAwbpT,jFmWyg,bUudRj,MRZ2Nn,ZAq7wr,7nWHCG,vsxBmJ,23kNsZ`
     - **Environment**（环境）: 勾选所有环境
       - ✅ Production（生产环境）
       - ✅ Preview（预览环境）
       - ✅ Development（开发环境）
   - 点击 **"Save"**（保存）按钮

### 步骤 3：重新部署

**重要**：环境变量修改后，必须重新部署才能生效！

1. 点击顶部的 **Deployments**（部署）标签
2. 找到最新的部署记录（通常在最上面）
3. 点击该部署记录右侧的 **"..."** 菜单
4. 选择 **"Redeploy"**（重新部署）
5. 确认重新部署

## ✅ 验证

部署完成后：
1. 等待几分钟（让部署完成）
2. 刷新注册页面
3. 使用邀请码 `YAwbpT`（或任何其他邀请码）注册
4. 应该可以成功注册了！

## 📋 所有可用邀请码

1. `gVshGk`
2. `7RKNQU`
3. `YAwbpT` ← 你使用的这个
4. `jFmWyg`
5. `bUudRj`
6. `MRZ2Nn`
7. `ZAq7wr`
8. `7nWHCG`
9. `vsxBmJ`
10. `23kNsZ`

**所有邀请码**（用于环境变量）：
```
gVshGk,7RKNQU,YAwbpT,jFmWyg,bUudRj,MRZ2Nn,ZAq7wr,7nWHCG,vsxBmJ,23kNsZ
```

## ⚠️ 注意事项

1. **邀请码不区分大小写**：你可以输入 `YAwbpT` 或 `yawbpt` 都可以，系统会自动转换为大写进行比较。

2. **环境变量格式**：多个邀请码用逗号分隔，**不要有空格**，例如：
   ```
   ✅ 正确: gVshGk,7RKNQU,YAwbpT
   ❌ 错误: gVshGk, 7RKNQU, YAwbpT  （有空格）
   ```

3. **必须重新部署**：环境变量修改后，**必须重新部署**才能生效。如果不重新部署，即使配置了环境变量，系统仍会使用旧的默认值。

4. **检查部署状态**：在 Vercel Dashboard 中，确保最新部署的状态是 **"Ready"** 或 **"Ready (Deployed)"**。

## 🔍 故障排查

如果配置后仍然提示"邀请码无效"：

1. **检查环境变量是否配置正确**
   - 在 Vercel Dashboard → Settings → Environment Variables
   - 确认 `INVITE_CODES` 变量已添加
   - 确认值中包含 `YAwbpT`

2. **检查是否已重新部署**
   - 在 Vercel Dashboard → Deployments
   - 确认最新的部署是在环境变量配置**之后**的
   - 如果部署时间在配置之前，需要重新部署

3. **检查部署日志**
   - 在 Vercel Dashboard → Deployments → 最新部署 → Function Logs
   - 查看是否有错误信息

4. **清除浏览器缓存**
   - 按 `Ctrl + Shift + Delete` (Windows/Linux) 或 `Cmd + Shift + Delete` (Mac)
   - 清除缓存后，刷新页面再试

## 📝 配置截图说明

如果你需要帮助，可以截图以下内容：

1. **Vercel 环境变量配置**：
   - Settings → Environment Variables
   - 显示 `INVITE_CODES` 变量的配置

2. **部署记录**：
   - Deployments 标签
   - 显示最新的部署记录和时间

3. **注册页面**：
   - 显示"邀请码无效"的错误提示
   - 显示输入的邀请码

---

**总结**：在 Vercel Dashboard 中配置 `INVITE_CODES` 环境变量，包含所有邀请码（用逗号分隔），然后重新部署即可！



