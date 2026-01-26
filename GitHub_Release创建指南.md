# 📤 GitHub Release 创建指南（详细步骤）

## ⚠️ 常见错误

**错误信息**：`tag name can't be blank, tag name is not well-formed`

**原因**：Tag name 格式不正确或为空

---

## ✅ 正确步骤

### 步骤 1：访问 Releases 页面

访问：https://github.com/jet20002025-hash/daniugu/releases

### 步骤 2：创建新 Release

点击 **"Draft a new release"** 或 **"Create a new release"**

### 步骤 3：填写 Tag（重要！）

**Tag name 格式要求**：
- ✅ 必须以字母或数字开头
- ✅ 可以包含：字母、数字、连字符（-）、下划线（_）、点号（.）
- ✅ 不能包含空格
- ✅ 不能为空

**推荐的 Tag name**：
```
data-20260126
```
或
```
v1.0.0-data
```
或
```
stock-data-20260126
```

**⚠️ 不要使用**：
- ❌ `data 20260126`（包含空格）
- ❌ `20260126`（纯数字开头可能有问题，建议加前缀）
- ❌ `data/2026/01/26`（包含斜杠）

### 步骤 4：选择或创建 Tag

**选项 A：选择现有 Tag**
- 如果 Tag 已存在，从下拉菜单选择

**选项 B：创建新 Tag**
- 在输入框中输入新的 Tag name（如 `data-20260126`）
- GitHub 会自动创建这个 Tag

### 步骤 5：填写 Release title

```
股票数据包 - 2026-01-26
```

### 步骤 6：填写 Description（可选）

```
股票数据压缩包

- 文件大小: 527 MB
- 压缩率: 61.7%
- 包含目录:
  - cache/ (35,937 个文件)
  - stock_data/ (10,938 个文件)
- 总计: 46,875 个文件
- 上传时间: 2026-01-26
```

### 步骤 7：上传文件

1. 将文件拖拽到 **"Attach binaries by dropping them here or selecting them"** 区域
2. 或点击 **"selecting them"** 选择文件
3. 文件路径：`/Users/zwj/股票分析/stock_data_20260126_121817.tar.gz`

### 步骤 8：发布

点击 **"Publish release"** 按钮

---

## 📋 完整示例

### Tag name
```
data-20260126
```

### Release title
```
股票数据包 - 2026-01-26
```

### Description
```
股票数据压缩包

文件信息：
- 大小: 527 MB
- 格式: tar.gz
- 压缩率: 61.7%

包含数据：
- cache/ 目录: 35,937 个文件
- stock_data/ 目录: 10,938 个文件
- 总计: 46,875 个文件

上传时间: 2026-01-26
```

### 上传文件
```
stock_data_20260126_121817.tar.gz
```

---

## 🔍 验证

发布成功后，你应该看到：

1. **Release 页面**显示新发布的 Release
2. **Assets 部分**显示上传的文件
3. **下载链接**可以复制（例如）：
   ```
   https://github.com/jet20002025-hash/daniugu/releases/download/data-20260126/stock_data_20260126_121817.tar.gz
   ```

---

## 💡 提示

### 如果 Tag 已存在

如果 `data-20260126` 这个 Tag 已经存在，可以：

1. **使用不同的 Tag name**：
   ```
   data-20260126-v2
   ```
   或
   ```
   stock-data-20260126
   ```

2. **或者删除旧的 Tag**（如果不需要）：
   - 访问 Tags 页面：https://github.com/jet20002025-hash/daniugu/tags
   - 删除旧的 Tag
   - 然后重新创建 Release

---

## ✅ 完成后的下一步

发布成功后：

1. **复制下载链接**（在 Assets 部分）
2. **在 Render Dashboard 设置环境变量**：
   - Key: `STOCK_DATA_URL`
   - Value: `你复制的下载链接`
3. **重新部署 Render 服务**

---

## 🐛 如果还是失败

如果按照上述步骤仍然失败，请检查：

1. **Tag name 格式**：确保没有空格、特殊字符
2. **网络连接**：确保可以访问 GitHub
3. **文件大小**：确保文件没有超过 GitHub 的限制（通常 2GB）
4. **权限**：确保你有仓库的写入权限

如果问题仍然存在，请告诉我具体的错误信息。
