#!/bin/bash
# 生成版本信息文件
# 在部署前运行此脚本，将当前 Git commit SHA 保存到 .git-version 文件

cd "$(dirname "$0")"

if [ -d .git ]; then
    # 获取当前 commit SHA
    COMMIT_SHA=$(git rev-parse HEAD 2>/dev/null)
    if [ -n "$COMMIT_SHA" ]; then
        echo "$COMMIT_SHA" > .git-version
        echo "✅ 版本信息已生成: $COMMIT_SHA"
        echo "   简短版本: ${COMMIT_SHA:0:7}"
    else
        echo "❌ 无法获取 Git commit SHA"
        echo "unknown" > .git-version
    fi
else
    echo "⚠️ 不是 Git 仓库，使用默认版本"
    echo "unknown" > .git-version
fi

