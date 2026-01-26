# 📤 上传数据包到 GitHub Releases 指南

## 🚀 方法一：自动上传（推荐）

### 步骤 1：创建数据压缩包

```bash
cd /Users/zwj/股票分析
python3 upload_stock_data.py
```

脚本会自动：
1. 检查 `cache/` 和 `stock_data/` 目录
2. 创建压缩包 `stock_data_YYYYMMDD_HHMMSS.tar.gz`
3. 显示压缩后大小

### 步骤 2：设置 GitHub Token

```bash
export GITHUB_TOKEN="你的GitHub_Token"
```

**如何获取 GitHub Token：**
1. 访问 https://github.com/settings/tokens
2. 点击 **"Generate new token (classic)"**
3. 勾选 `repo` 权限（需要完整仓库访问权限）
4. 生成并复制 Token

### 步骤 3：上传到 GitHub Releases

**选项 A：使用 `upload_stock_data.py`（交互式）**

```bash
python3 upload_stock_data.py
# 选择选项 1（GitHub Releases）
```

**选项 B：使用 `upload_to_github.py`（非交互式）**

```bash
# 先创建压缩包（如果还没有）
python3 upload_stock_data.py

# 然后上传
python3 upload_to_github.py
```

### 步骤 4：获取下载 URL

上传成功后，脚本会显示下载 URL，例如：
```
📥 下载 URL: https://github.com/jet20002025-hash/daniugu/releases/download/data-20260126/stock_data_20260126_120000.tar.gz
```

复制这个 URL，用于配置 Vercel 环境变量。

---

## 📋 方法二：手动上传（如果自动上传失败）

### 步骤 1：创建数据压缩包

```bash
cd /Users/zwj/股票分析
python3 upload_stock_data.py
```

### 步骤 2：访问 GitHub Releases 页面

访问：https://github.com/jet20002025-hash/daniugu/releases

### 步骤 3：创建新 Release

点击 **"Draft a new release"** 或 **"Create a new release"**

### 步骤 4：填写 Release 信息

**Tag name（重要！）：**
```
data-20260126
```
⚠️ **注意**：
- ✅ 格式：`data-YYYYMMDD`
- ✅ 不能包含空格
- ✅ 不能为空
- ❌ 不要使用：`data 20260126`（有空格）

**Release title：**
```
股票数据包 - 2026-01-26
```

**Description（可选）：**
```
股票数据压缩包

- 文件大小: XXX MB
- 压缩率: XX%
- 包含目录:
  - cache/ (日K线和周K线数据)
  - stock_data/ (股票基础数据)
- 上传时间: 2026-01-26
```

### 步骤 5：上传文件

1. 将压缩包文件拖拽到 **"Attach binaries"** 区域
   - 文件路径：`/Users/zwj/股票分析/stock_data_YYYYMMDD_HHMMSS.tar.gz`
2. 或点击 **"selecting them"** 选择文件

### 步骤 6：发布 Release

点击 **"Publish release"** 按钮

### 步骤 7：获取下载 URL

发布成功后：
1. 在 Release 页面的 **Assets** 部分找到上传的文件
2. 右键点击文件 → **"复制链接地址"**
3. 或直接复制显示的下载链接

**下载 URL 格式：**
```
https://github.com/jet20002025-hash/daniugu/releases/download/data-YYYYMMDD/stock_data_YYYYMMDD_HHMMSS.tar.gz
```

---

## ⚙️ 配置 Vercel 环境变量

上传成功后，在 Vercel Dashboard 中设置环境变量：

1. 访问 Vercel Dashboard：https://vercel.com/dashboard
2. 选择项目 `daniugu`
3. 进入 **Settings** → **Environment Variables**
4. 添加环境变量：

| Key | Value |
|-----|-------|
| `STOCK_DATA_URL` | `你复制的下载URL` |

**示例：**
```
STOCK_DATA_URL=https://github.com/jet20002025-hash/daniugu/releases/download/data-20260126/stock_data_20260126_120000.tar.gz
```

5. 保存后，Vercel 会自动重新部署

---

## 🔍 验证上传

### 检查 Release 页面

访问：https://github.com/jet20002025-hash/daniugu/releases

应该看到：
- ✅ 新创建的 Release（标签：`data-YYYYMMDD`）
- ✅ Assets 部分显示上传的文件
- ✅ 文件大小正确

### 测试下载链接

在浏览器中打开下载 URL，应该能直接下载文件。

---

## 🐛 常见问题

### 问题 1：GitHub Token 权限不足

**错误信息：** `Bad credentials` 或 `Resource not accessible by integration`

**解决方案：**
1. 确保 Token 有 `repo` 权限（完整仓库访问权限）
2. 如果使用 GitHub App，需要确保有 Releases 写入权限
3. 重新生成 Token 并设置环境变量

### 问题 2：Tag name 格式错误

**错误信息：** `tag name can't be blank, tag name is not well-formed`

**解决方案：**
- ✅ 使用格式：`data-YYYYMMDD`（如 `data-20260126`）
- ❌ 不要使用空格：`data 20260126`
- ❌ 不要使用特殊字符：`data/2026/01/26`

### 问题 3：文件太大

**错误信息：** `File exceeds maximum size`

**解决方案：**
- GitHub Releases 单个文件限制：**2GB**
- 如果超过，可以：
  1. 分多个文件上传
  2. 使用其他云存储（AWS S3、Cloudflare R2 等）

### 问题 4：上传超时

**解决方案：**
- 检查网络连接
- 使用稳定的网络环境
- 如果文件很大，考虑使用命令行工具 `gh`：
  ```bash
  gh release upload data-20260126 stock_data_*.tar.gz --repo jet20002025-hash/daniugu
  ```

---

## 📝 完整示例流程

```bash
# 1. 创建压缩包
cd /Users/zwj/股票分析
python3 upload_stock_data.py

# 2. 设置 GitHub Token
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"

# 3. 上传到 GitHub Releases
python3 upload_to_github.py

# 4. 复制显示的下载 URL
# 例如：https://github.com/jet20002025-hash/daniugu/releases/download/data-20260126/stock_data_20260126_120000.tar.gz

# 5. 在 Vercel Dashboard 设置环境变量
# STOCK_DATA_URL = 复制的URL

# 6. 重新部署 Vercel
```

---

## ✅ 完成！

上传成功后：
- ✅ GitHub Releases 中有新的数据包
- ✅ Vercel 环境变量已配置
- ✅ Vercel 会在启动时自动下载数据包

下次需要更新数据时，重复上述步骤即可。
