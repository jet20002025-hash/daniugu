# 大牛股分析系统

股票分析系统，用于分析大牛股特征并寻找潜在投资机会。

## 功能特性

- 📊 大牛股特征分析
- 🔍 全市场股票扫描
- 📈 买点识别
- 💰 卖点预测
- 📉 周K线分析
- 🔄 反转个股搜索

## 技术栈

- Python 3.9+
- Flask
- Pandas
- NumPy
- akshare（股票数据）

## 部署

### 阿里云服务器部署

详细部署步骤请参考：[阿里云服务器部署指南.md](./阿里云服务器部署指南.md)

### 快速部署

```bash
# 1. 上传代码到服务器
scp -r * root@你的服务器IP:/var/www/stock-analyzer/

# 2. SSH 连接服务器
ssh root@你的服务器IP

# 3. 执行部署脚本
cd /var/www/stock-analyzer
bash 服务器部署脚本.sh
```

## 配置

- 域名：daniugu.online
- GitHub：https://github.com/jet20002025-hash/daniugu

## 使用说明

详细使用说明请参考：[WEB使用说明.md](./WEB使用说明.md)

## License

MIT
