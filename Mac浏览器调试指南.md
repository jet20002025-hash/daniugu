# Mac浏览器开发者工具打开方法

## Safari浏览器

### 方法1：快捷键
- **打开开发者工具**：`Option + Command + I` 或 `Option + Command + C`
- **显示菜单栏**：如果看不到菜单栏，按 `Control + F2` 或点击屏幕顶部

### 方法2：通过菜单
1. 点击顶部菜单栏的 **Safari**
2. 选择 **设置**（Preferences）
3. 点击 **高级**（Advanced）标签
4. 勾选 **在菜单栏中显示"开发"菜单**（Show Develop menu in menu bar）
5. 然后点击菜单栏的 **开发**（Develop）
6. 选择 **显示Web检查器**（Show Web Inspector）

## Chrome浏览器

### 快捷键
- **打开开发者工具**：`Command + Option + I`
- **只打开Console**：`Command + Option + J`
- **只打开Elements**：`Command + Option + C`

### 通过菜单
1. 点击右上角三个点（⋮）
2. 选择 **更多工具**（More Tools）
3. 选择 **开发者工具**（Developer Tools）

## Firefox浏览器

### 快捷键
- **打开开发者工具**：`Command + Option + I`
- **只打开Console**：`Command + Option + K`

### 通过菜单
1. 点击右上角三条横线（☰）
2. 选择 **更多工具**（More Tools）
3. 选择 **Web开发者工具**（Web Developer Tools）

## 查看调试信息的关键步骤

### 1. 打开Console标签（查看JavaScript错误）
- 在开发者工具中，点击 **Console** 标签
- 查看是否有红色错误信息
- 这些错误会告诉你前端代码哪里出问题了

### 2. 打开Network标签（查看API请求）
- 点击 **Network** 标签
- 刷新页面（F5 或 Cmd+R）
- 查看所有网络请求：
  - 红色 = 请求失败
  - 黄色 = 请求警告
  - 灰色 = 请求被取消
- 点击具体的请求（如 `/api/user_info`）查看详情：
  - **Headers**：请求头信息
  - **Response**：服务器返回的内容
  - **Timing**：请求耗时

### 3. 查看登录相关的API请求
重点关注这些请求：
- `/api/login` - 登录请求
- `/api/check_login` - 检查登录状态
- `/api/user_info` - 获取用户信息

### 4. 如果看不到菜单栏
- 按 `Control + F2` 激活菜单栏
- 或者点击屏幕最顶部（即使看不到菜单栏，点击那里也能激活）

## 快速诊断步骤

1. **打开Chrome浏览器**（推荐，调试工具最完善）
2. **按 `Command + Option + I`** 打开开发者工具
3. **切换到Console标签**，查看是否有错误
4. **切换到Network标签**，刷新页面
5. **查找失败的请求**（红色标记）
6. **点击失败的请求**，查看错误详情

## 如果快捷键不起作用

可能是系统快捷键冲突，可以：
1. 系统设置 → 键盘 → 快捷键
2. 检查是否有冲突的快捷键
3. 或者直接通过菜单打开开发者工具
