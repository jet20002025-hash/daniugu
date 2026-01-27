#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 GitHub 获取缓存数据的最小模块。
只做一件事：下载 STOCK_DATA_URL 指向的 tar.gz，解压到项目目录。
可被 Vercel/Render 启动时或单独流程「先获取」缓存，再跑主应用。
"""
import gzip
import os
import tarfile

try:
    import requests
except ImportError:
    requests = None

# 最近一次失败时的错误信息，供 cache_debug 等展示
_last_error = None


def fetch_github_cache(
    skip_if_exists=True,
    url=None,
    root_dir=None,
    timeout=300,
    generate_stock_list=True,
):
    """
    从 GitHub 拉取并解压股票缓存。

    :param skip_if_exists: 若 cache/ 或 stock_data/ 已有内容则跳过，返回 True
    :param url: 数据包 URL，默认 os.environ.get('STOCK_DATA_URL')
    :param root_dir: 解压目标目录，默认为本文件所在目录（项目根）
    :param timeout: 下载超时秒数
    :param generate_stock_list: 解压后若缺少 stock_list_all.json 是否从 K 线生成
    :return: True 表示缓存已就绪（跳过或下载成功），False 表示失败
    """
    root = (root_dir or os.path.dirname(os.path.abspath(__file__))).rstrip(os.sep)
    cache_dir = os.path.join(root, "cache")
    stock_data_dir = os.path.join(root, "stock_data")
    data_url = url or os.environ.get("STOCK_DATA_URL")

    global _last_error
    _last_error = None
    if not data_url:
        return False

    if skip_if_exists:
        if os.path.exists(cache_dir) and os.listdir(cache_dir):
            return True
        if os.path.exists(stock_data_dir) and os.listdir(stock_data_dir):
            return True

    if requests is None:
        return False

    # 流式解压：边下载边解压到 root，不落盘整份 .tar.gz，避免 Vercel /tmp 磁盘满
    try:
        resp = requests.get(data_url, stream=True, timeout=timeout)
        resp.raise_for_status()
        resp.raw.decode_content = False  # 保留 gzip 原始字节，由下方 gzip.GzipFile 解压
        gzip_stream = gzip.GzipFile(fileobj=resp.raw)
        with tarfile.open(fileobj=gzip_stream, mode="r|") as tar:
            for member in tar:
                tar.extract(member, root)
    except Exception as e:
        _last_error = str(e)
        return False

    if generate_stock_list:
        stock_list_path = os.path.join(cache_dir, "stock_list_all.json")
        if os.path.exists(cache_dir) and not os.path.exists(stock_list_path):
            try:
                _cwd = os.getcwd()
                os.chdir(root)
                try:
                    from generate_stock_list_from_files import (
                        generate_stock_list_from_kline_files,
                    )
                    generate_stock_list_from_kline_files()
                finally:
                    os.chdir(_cwd)
            except Exception:
                pass
    return True  # 下载并解压成功


if __name__ == "__main__":
    # 确保在项目根目录执行
    _root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(_root)
    ok = fetch_github_cache(skip_if_exists=True, root_dir=_root)
    print("缓存已就绪" if ok else "获取失败")
    raise SystemExit(0 if ok else 1)
