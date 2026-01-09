#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将本地邀请码同步到 Vercel 持久化存储
"""
import json
import os

def load_local_invite_codes():
    """从本地文件加载邀请码"""
    try:
        with open('invite_codes.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ 未找到 invite_codes.json 文件")
        return {}
    except Exception as e:
        print(f"❌ 读取本地邀请码失败: {e}")
        return {}

def sync_to_upstash_redis(codes):
    """同步到 Upstash Redis"""
    redis_url = os.environ.get('UPSTASH_REDIS_REST_URL')
    redis_token = os.environ.get('UPSTASH_REDIS_REST_TOKEN')
    
    if not redis_url or not redis_token:
        print("⚠️ Upstash Redis 环境变量未配置")
        return False
    
    try:
        import requests
        
        # 将邀请码转换为 JSON 字符串
        codes_json = json.dumps(codes, ensure_ascii=False)
        
        # 使用 Upstash Redis REST API 保存数据
        response = requests.post(
            f"{redis_url}/set/invite_codes",
            headers={
                "Authorization": f"Bearer {redis_token}",
                "Content-Type": "application/json"
            },
            json=codes_json,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ 邀请码已同步到 Upstash Redis")
            return True
        else:
            print(f"❌ 同步到 Upstash Redis 失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 同步到 Upstash Redis 失败: {e}")
        return False

def sync_to_vercel_kv(codes):
    """同步到 Vercel KV"""
    try:
        from vercel_kv import kv
        
        # 将邀请码转换为 JSON 字符串
        codes_json = json.dumps(codes, ensure_ascii=False)
        
        # 保存到 Vercel KV
        kv.set('invite_codes', codes_json)
        
        print("✅ 邀请码已同步到 Vercel KV")
        return True
    except ImportError:
        print("⚠️ Vercel KV 未配置或不可用")
        return False
    except Exception as e:
        print(f"❌ 同步到 Vercel KV 失败: {e}")
        return False

def generate_env_var_string(codes):
    """生成环境变量字符串（用逗号分隔）"""
    code_list = [code for code in codes.keys()]
    return ','.join(code_list)

def main():
    print("=" * 60)
    print("🔄 同步本地邀请码到 Vercel")
    print("=" * 60)
    
    # 加载本地邀请码
    local_codes = load_local_invite_codes()
    
    if not local_codes:
        print("❌ 本地没有邀请码，请先使用 create_invite_code.py 生成邀请码")
        return
    
    print(f"\n📋 找到 {len(local_codes)} 个本地邀请码:")
    for code in local_codes.keys():
        print(f"   - {code}")
    
    print("\n" + "=" * 60)
    print("📝 同步方式选择:")
    print("=" * 60)
    print("1. 同步到 Upstash Redis（如果已配置）")
    print("2. 同步到 Vercel KV（如果已配置）")
    print("3. 生成环境变量字符串（用于 Vercel 环境变量配置）")
    print("4. 全部尝试")
    
    choice = input("\n请选择 (1-4，直接回车表示全部尝试): ").strip() or "4"
    
    success_count = 0
    
    if choice == "1" or choice == "4":
        if sync_to_upstash_redis(local_codes):
            success_count += 1
    
    if choice == "2" or choice == "4":
        if sync_to_vercel_kv(local_codes):
            success_count += 1
    
    if choice == "3" or choice == "4":
        env_str = generate_env_var_string(local_codes)
        print("\n" + "=" * 60)
        print("📋 Vercel 环境变量配置:")
        print("=" * 60)
        print(f"变量名: INVITE_CODES")
        print(f"变量值: {env_str}")
        print("\n💡 在 Vercel Dashboard 中配置:")
        print("   1. 进入项目设置 → Environment Variables")
        print("   2. 添加环境变量:")
        print(f"      Name: INVITE_CODES")
        print(f"      Value: {env_str}")
        print("   3. 选择环境: Production, Preview, Development")
        print("   4. 点击 Save")
        print("   5. 重新部署项目")
        print("=" * 60)
        success_count += 1
    
    if success_count > 0:
        print(f"\n✅ 同步完成（成功 {success_count} 项）")
    else:
        print("\n❌ 同步失败，请检查配置")

if __name__ == '__main__':
    main()

