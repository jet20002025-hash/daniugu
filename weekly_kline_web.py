"""
周线K线图Web应用
所有K线数据和分析都基于周线
"""
from flask import Flask, render_template, jsonify, request
from data_fetcher import DataFetcher
from technical_analysis import TechnicalAnalysis
import pandas as pd
import numpy as np
from datetime import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'weekly-kline-secret-key'

fetcher = DataFetcher()
tech_analysis = TechnicalAnalysis()

def convert_to_json_serializable(obj):
    """将复杂对象转换为JSON可序列化格式"""
    if obj is None:
        return None
    elif isinstance(obj, (pd.Timestamp, pd.DatetimeIndex)):
        return obj.strftime('%Y-%m-%d') if pd.notna(obj) else None
    elif isinstance(obj, pd.Series):
        return [convert_to_json_serializable(x) for x in obj.tolist()]
    elif isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        return float(obj) if not pd.isna(obj) else None
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return [convert_to_json_serializable(x) for x in obj.tolist()]
    elif pd.isna(obj):
        return None
    elif isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d')
    elif isinstance(obj, (list, tuple)):
        return [convert_to_json_serializable(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: convert_to_json_serializable(v) for k, v in obj.items()}
    # 处理其他可能的numpy类型
    elif hasattr(obj, 'item'):  # numpy标量类型
        try:
            return obj.item()
        except (ValueError, AttributeError):
            return str(obj)
    return obj

@app.route('/')
def index():
    """主页面"""
    return render_template('weekly_kline.html')

@app.route('/favicon.ico')
def favicon():
    """处理favicon请求，返回204 No Content"""
    return '', 204

@app.route('/api/search_stock', methods=['POST'])
def search_stock():
    """搜索股票"""
    try:
        data = request.json
        keyword = data.get('keyword', '').strip()
        
        if not keyword:
            return jsonify({'error': '请输入股票代码或名称'}), 400
        
        # 获取所有股票列表
        stock_list = fetcher.get_all_stocks()
        if stock_list is None or len(stock_list) == 0:
            return jsonify({'error': '无法获取股票列表'}), 500
        
        # 搜索匹配的股票
        results = []
        keyword_upper = keyword.upper()
        for idx, row in stock_list.iterrows():
            code = str(row['code'])
            name = str(row['name'])
            if keyword_upper in code or keyword_upper in name.upper():
                results.append({
                    'code': code,
                    'name': name
                })
                if len(results) >= 20:  # 最多返回20个结果
                    break
        
        return jsonify({'stocks': results})
    except Exception as e:
        return jsonify({'error': f'搜索失败: {str(e)}'}), 500

@app.route('/api/weekly_kline', methods=['POST'])
def get_weekly_kline():
    """获取周K线数据"""
    try:
        import time
        start_time = time.time()
        
        data = request.json
        stock_code = data.get('code', '').strip()
        
        if not stock_code:
            return jsonify({'error': '请输入股票代码'}), 400
        
        print(f"[{time.strftime('%H:%M:%S')}] 开始获取 {stock_code} 的周K线数据...")
        
        # 获取周K线数据
        try:
            weekly_df = fetcher.get_weekly_kline(stock_code)
            print(f"[{time.strftime('%H:%M:%S')}] 周K线数据获取完成，共 {len(weekly_df) if weekly_df is not None else 0} 条")
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"[{time.strftime('%H:%M:%S')}] 获取周K线数据失败: {e}")
            print(error_detail)
            # 返回更详细的错误信息
            error_msg = f'获取周K线数据失败: {str(e)}'
            if 'timeout' in str(e).lower() or '超时' in str(e):
                error_msg = '数据获取超时，请稍后重试'
            return jsonify({'error': error_msg}), 500
        
        if weekly_df is None or len(weekly_df) == 0:
            return jsonify({'error': '无法获取周K线数据'}), 500
        
        # 计算技术指标（基于周线）
        # MA5, MA10, MA20, MA60, MA120（周线）
        ma5 = tech_analysis.calculate_ma(weekly_df, period=5) if len(weekly_df) >= 5 else None
        ma10 = tech_analysis.calculate_ma(weekly_df, period=10) if len(weekly_df) >= 10 else None
        ma20 = tech_analysis.calculate_ma(weekly_df, period=20) if len(weekly_df) >= 20 else None
        ma60 = tech_analysis.calculate_ma(weekly_df, period=60) if len(weekly_df) >= 60 else None
        ma120 = tech_analysis.calculate_ma(weekly_df, period=120) if len(weekly_df) >= 120 else None
        
        # 计算成交量移动平均线
        volume_col = '周成交量' if '周成交量' in weekly_df.columns else '成交量'
        volume_ma5 = None
        volume_ma20 = None
        if volume_col in weekly_df.columns:
            if len(weekly_df) >= 5:
                volume_ma5 = weekly_df[volume_col].rolling(window=5).mean()
            if len(weekly_df) >= 20:
                volume_ma20 = weekly_df[volume_col].rolling(window=20).mean()
        
        # 准备K线数据（ECharts格式：[日期, [开盘, 收盘, 最低, 最高], 成交量]）
        kline_data = []
        dates = []
        volumes = []
        ma5_data = []
        ma10_data = []
        ma20_data = []
        ma60_data = []
        ma120_data = []
        volume_ma5_data = []
        volume_ma20_data = []
        
        # 使用整数索引而不是iterrows()的索引，避免索引不匹配问题
        for i in range(len(weekly_df)):
            row = weekly_df.iloc[i]
            date = convert_to_json_serializable(row['日期'])
            dates.append(date)
            
            # K线数据：[开盘, 收盘, 最低, 最高]
            # 获取原始数据，确保使用正确的列名
            try:
                open_price = convert_to_json_serializable(row['开盘'])
                close_price = convert_to_json_serializable(row['收盘'])
                low_price = convert_to_json_serializable(row['最低'])
                high_price = convert_to_json_serializable(row['最高'])
            except KeyError as e:
                # 如果列名不存在，输出所有列名用于调试
                print(f"[错误] K线[{i}]列名错误: {e}")
                print(f"[调试] 可用列名: {list(row.index)}")
                # 尝试使用位置索引
                if len(row) >= 4:
                    open_price = convert_to_json_serializable(row.iloc[1])  # 开盘
                    close_price = convert_to_json_serializable(row.iloc[2])  # 收盘
                    high_price = convert_to_json_serializable(row.iloc[3])  # 最高
                    low_price = convert_to_json_serializable(row.iloc[4])  # 最低
                else:
                    open_price = close_price = low_price = high_price = 0
            
            # 数据验证：确保最低价 <= min(开盘,收盘)，最高价 >= max(开盘,收盘)
            try:
                open_val = float(open_price) if open_price else 0
                close_val = float(close_price) if close_price else 0
                low_val = float(low_price) if low_price else 0
                high_val = float(high_price) if high_price else 0
                
                min_oc = min(open_val, close_val)
                max_oc = max(open_val, close_val)
                
                # 如果数据不符合逻辑，输出详细信息（前5条）
                if i < 5:
                    print(f"[调试] K线[{i}]: 开盘={open_price}, 收盘={close_price}, 最低={low_price}, 最高={high_price}")
                    print(f"[调试] K线[{i}]: min(开盘,收盘)={min_oc:.2f}, max(开盘,收盘)={max_oc:.2f}")
                    print(f"[调试] K线[{i}]: 最低价是否符合逻辑: {low_val <= min_oc}, 最高价是否符合逻辑: {high_val >= max_oc}")
                
                # 如果数据不符合逻辑，可能是列顺序或数据本身有问题
                if low_val > min_oc or high_val < max_oc:
                    if i < 5:
                        print(f"[警告] K线[{i}]数据异常: 最低价{low_val:.2f} > min(开盘{open_val:.2f},收盘{close_val:.2f}) 或 最高价{high_val:.2f} < max(开盘{open_val:.2f},收盘{close_val:.2f})")
            except (ValueError, TypeError) as e:
                print(f"[错误] K线[{i}]数据转换失败: {e}")
            
            # 确保返回顺序：[开盘, 收盘, 最低, 最高]
            kline_item = [
                open_price,   # 开盘
                close_price,  # 收盘
                low_price,    # 最低
                high_price    # 最高
            ]
            kline_data.append(kline_item)
            
            # 成交量 - 确保转换为Python原生类型
            try:
                volume = row.get('周成交量', row.get('成交量', 0))
                
                # 如果是Series，取第一个值
                if isinstance(volume, pd.Series):
                    volume = volume.iloc[0] if len(volume) > 0 else 0
                
                # 确保是标量值后再判断NaN
                if hasattr(volume, 'item'):  # numpy标量类型
                    try:
                        volume = volume.item()
                    except (ValueError, AttributeError):
                        volume = float(volume) if isinstance(volume, (np.floating, np.float64)) else int(volume)
                
                # 判断是否为NaN（必须是标量值）
                if isinstance(volume, (pd.Series, pd.DataFrame)):
                    volume = 0
                elif pd.isna(volume):
                    volume = 0
                elif isinstance(volume, (np.integer, np.int64, np.int32)):
                    volume = int(volume)
                elif isinstance(volume, (np.floating, np.float64, np.float32)):
                    volume = float(volume)
                
                volumes.append(convert_to_json_serializable(volume))
            except Exception as e:
                # 如果出错，使用默认值0
                volumes.append(0)
            
            # 均线数据
            if ma5 is not None and i < len(ma5):
                ma5_value = ma5.iloc[i]
                if pd.notna(ma5_value):
                    ma5_data.append(convert_to_json_serializable(ma5_value))
                else:
                    ma5_data.append(None)
            else:
                ma5_data.append(None)
            
            if ma10 is not None and i < len(ma10):
                ma10_value = ma10.iloc[i]
                if pd.notna(ma10_value):
                    ma10_data.append(convert_to_json_serializable(ma10_value))
                else:
                    ma10_data.append(None)
            else:
                ma10_data.append(None)
            
            if ma20 is not None and i < len(ma20):
                ma20_value = ma20.iloc[i]
                if pd.notna(ma20_value):
                    ma20_data.append(convert_to_json_serializable(ma20_value))
                else:
                    ma20_data.append(None)
            else:
                ma20_data.append(None)
            
            if ma60 is not None and i < len(ma60):
                ma60_value = ma60.iloc[i]
                if pd.notna(ma60_value):
                    ma60_data.append(convert_to_json_serializable(ma60_value))
                else:
                    ma60_data.append(None)
            else:
                ma60_data.append(None)
            
            # MA120数据
            if ma120 is not None and i < len(ma120):
                ma120_value = ma120.iloc[i]
                if pd.notna(ma120_value):
                    ma120_data.append(convert_to_json_serializable(ma120_value))
                else:
                    ma120_data.append(None)
            else:
                ma120_data.append(None)
            
            # 成交量均线数据
            try:
                if volume_ma5 is not None and i < len(volume_ma5):
                    volume_ma5_value = volume_ma5.iloc[i]
                    # 确保是标量值
                    if isinstance(volume_ma5_value, pd.Series):
                        volume_ma5_value = volume_ma5_value.iloc[0] if len(volume_ma5_value) > 0 else None
                    if pd.notna(volume_ma5_value):
                        volume_ma5_data.append(convert_to_json_serializable(volume_ma5_value))
                    else:
                        volume_ma5_data.append(None)
                else:
                    volume_ma5_data.append(None)
            except Exception:
                volume_ma5_data.append(None)
            
            try:
                if volume_ma20 is not None and i < len(volume_ma20):
                    volume_ma20_value = volume_ma20.iloc[i]
                    # 确保是标量值
                    if isinstance(volume_ma20_value, pd.Series):
                        volume_ma20_value = volume_ma20_value.iloc[0] if len(volume_ma20_value) > 0 else None
                    if pd.notna(volume_ma20_value):
                        volume_ma20_data.append(convert_to_json_serializable(volume_ma20_value))
                    else:
                        volume_ma20_data.append(None)
                else:
                    volume_ma20_data.append(None)
            except Exception:
                volume_ma20_data.append(None)
        
        # 获取股票名称
        stock_list = fetcher.get_all_stocks()
        stock_name = stock_code
        if stock_list is not None:
            stock_row = stock_list[stock_list['code'] == stock_code]
            if len(stock_row) > 0:
                stock_name = stock_row.iloc[0]['name']
        
        # 获取当前价格和市值
        current_price = weekly_df.iloc[-1]['收盘'] if len(weekly_df) > 0 else None
        market_cap = fetcher.get_market_cap(stock_code)
        
        # 确保所有数据都经过JSON序列化转换
        result = {
            'code': str(stock_code),  # 确保是字符串
            'name': str(stock_name),  # 确保是字符串
            'dates': [convert_to_json_serializable(d) for d in dates],
            'kline': [[convert_to_json_serializable(v) for v in k] for k in kline_data],
            'volumes': [convert_to_json_serializable(v) for v in volumes],
            'ma5': [convert_to_json_serializable(v) for v in ma5_data],
            'ma10': [convert_to_json_serializable(v) for v in ma10_data],
            'ma20': [convert_to_json_serializable(v) for v in ma20_data],
            'ma60': [convert_to_json_serializable(v) for v in ma60_data],
            'ma120': [convert_to_json_serializable(v) for v in ma120_data],
            'volume_ma5': [convert_to_json_serializable(v) for v in volume_ma5_data],
            'volume_ma20': [convert_to_json_serializable(v) for v in volume_ma20_data],
            'current_price': convert_to_json_serializable(current_price),
            'market_cap': convert_to_json_serializable(market_cap),
            'total_weeks': int(len(weekly_df))  # 确保是Python int类型
        }
        
        elapsed_time = time.time() - start_time
        print(f"[{time.strftime('%H:%M:%S')}] {stock_code} 数据处理完成，耗时 {elapsed_time:.2f}秒")
        
        return jsonify(result)
    except Exception as e:
        import traceback
        error_msg = f'获取周K线数据失败: {str(e)}\n{traceback.format_exc()}'
        print(f"[{time.strftime('%H:%M:%S')}] 错误: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/api/weekly_indicators', methods=['POST'])
def get_weekly_indicators():
    """获取周线技术指标"""
    try:
        data = request.json
        stock_code = data.get('code', '').strip()
        
        if not stock_code:
            return jsonify({'error': '请输入股票代码'}), 400
        
        # 获取周K线数据
        weekly_df = fetcher.get_weekly_kline(stock_code)
        if weekly_df is None or len(weekly_df) == 0:
            return jsonify({'error': '无法获取周K线数据'}), 500
        
        # 计算各种技术指标（基于周线）
        indicators = {}
        
        # 当前价格
        current_price = float(weekly_df.iloc[-1]['收盘'])
        indicators['当前价格'] = current_price
        
        # 均线
        if len(weekly_df) >= 5:
            ma5 = tech_analysis.calculate_ma(weekly_df, period=5)
            if ma5 is not None and len(ma5) > 0:
                ma5_value = ma5.iloc[-1]
                if pd.notna(ma5_value):
                    indicators['MA5'] = float(ma5_value)
                    if indicators['MA5'] > 0:
                        indicators['价格相对MA5'] = float((current_price - indicators['MA5']) / indicators['MA5'] * 100)
                    else:
                        indicators['价格相对MA5'] = None
                else:
                    indicators['MA5'] = None
                    indicators['价格相对MA5'] = None
        
        if len(weekly_df) >= 10:
            ma10 = tech_analysis.calculate_ma(weekly_df, period=10)
            if ma10 is not None and len(ma10) > 0:
                ma10_value = ma10.iloc[-1]
                if pd.notna(ma10_value):
                    indicators['MA10'] = float(ma10_value)
                    if indicators['MA10'] > 0:
                        indicators['价格相对MA10'] = float((current_price - indicators['MA10']) / indicators['MA10'] * 100)
                    else:
                        indicators['价格相对MA10'] = None
                else:
                    indicators['MA10'] = None
                    indicators['价格相对MA10'] = None
        
        if len(weekly_df) >= 20:
            ma20 = tech_analysis.calculate_ma(weekly_df, period=20)
            if ma20 is not None and len(ma20) > 0:
                ma20_value = ma20.iloc[-1]
                if pd.notna(ma20_value):
                    indicators['MA20'] = float(ma20_value)
                    if indicators['MA20'] > 0:
                        indicators['价格相对MA20'] = float((current_price - indicators['MA20']) / indicators['MA20'] * 100)
                    else:
                        indicators['价格相对MA20'] = None
                else:
                    indicators['MA20'] = None
                    indicators['价格相对MA20'] = None
        
        if len(weekly_df) >= 60:
            ma60 = tech_analysis.calculate_ma(weekly_df, period=60)
            if ma60 is not None and len(ma60) > 0:
                ma60_value = ma60.iloc[-1]
                if pd.notna(ma60_value):
                    indicators['MA60'] = float(ma60_value)
                    if indicators['MA60'] > 0:
                        indicators['价格相对MA60'] = float((current_price - indicators['MA60']) / indicators['MA60'] * 100)
                    else:
                        indicators['价格相对MA60'] = None
                else:
                    indicators['MA60'] = None
                    indicators['价格相对MA60'] = None
        
        # 成交量相关
        if '周成交量' in weekly_df.columns or '成交量' in weekly_df.columns:
            volume_col = '周成交量' if '周成交量' in weekly_df.columns else '成交量'
            recent_volume_series = weekly_df[volume_col].tail(5)
            avg_volume_series = weekly_df[volume_col].tail(20) if len(weekly_df) >= 20 else weekly_df[volume_col]
            
            # 确保转换为标量值
            try:
                if len(recent_volume_series) > 0:
                    recent_volume_mean = recent_volume_series.mean()
                    # 如果返回的是Series，取第一个值；如果是标量，直接使用
                    if isinstance(recent_volume_mean, pd.Series):
                        recent_volume = float(recent_volume_mean.iloc[0]) if len(recent_volume_mean) > 0 else None
                    else:
                        recent_volume = float(recent_volume_mean) if pd.notna(recent_volume_mean) else None
                    if recent_volume is not None and pd.isna(recent_volume):
                        recent_volume = None
                else:
                    recent_volume = None
            except Exception:
                recent_volume = None
            
            try:
                if len(avg_volume_series) > 0:
                    avg_volume_mean = avg_volume_series.mean()
                    # 如果返回的是Series，取第一个值；如果是标量，直接使用
                    if isinstance(avg_volume_mean, pd.Series):
                        avg_volume = float(avg_volume_mean.iloc[0]) if len(avg_volume_mean) > 0 else None
                    else:
                        avg_volume = float(avg_volume_mean) if pd.notna(avg_volume_mean) else None
                    if avg_volume is not None and pd.isna(avg_volume):
                        avg_volume = None
                else:
                    avg_volume = None
            except Exception:
                avg_volume = None
            
            indicators['最近5周均量'] = recent_volume
            indicators['最近20周均量'] = avg_volume
            if recent_volume is not None and avg_volume is not None and avg_volume > 0:
                indicators['成交量放大倍数'] = float(recent_volume / avg_volume)
            else:
                indicators['成交量放大倍数'] = None
        
        # 价格变化
        if len(weekly_df) >= 5:
            price_5_weeks_ago = float(weekly_df.iloc[-5]['收盘'])
            indicators['5周涨幅'] = float((current_price - price_5_weeks_ago) / price_5_weeks_ago * 100)
        
        if len(weekly_df) >= 20:
            price_20_weeks_ago = float(weekly_df.iloc[-20]['收盘'])
            indicators['20周涨幅'] = float((current_price - price_20_weeks_ago) / price_20_weeks_ago * 100)
        
        # 波动率
        if len(weekly_df) >= 20:
            try:
                returns = weekly_df['收盘'].pct_change().dropna()
                if len(returns) > 0:
                    volatility_std = returns.std()
                    # 如果返回的是Series，取第一个值；如果是标量，直接使用
                    if isinstance(volatility_std, pd.Series):
                        volatility = float(volatility_std.iloc[0]) if len(volatility_std) > 0 else None
                    else:
                        volatility = float(volatility_std) if pd.notna(volatility_std) else None
                    
                    if volatility is not None:
                        indicators['波动率'] = float(volatility * 100)
                    else:
                        indicators['波动率'] = None
                else:
                    indicators['波动率'] = None
            except Exception:
                indicators['波动率'] = None
        
        # 最高最低
        if len(weekly_df) >= 20:
            recent_high_series = weekly_df['最高'].tail(20)
            recent_low_series = weekly_df['最低'].tail(20)
            
            try:
                if len(recent_high_series) > 0:
                    recent_high_max = recent_high_series.max()
                    # 如果返回的是Series，取第一个值；如果是标量，直接使用
                    if isinstance(recent_high_max, pd.Series):
                        recent_high = float(recent_high_max.iloc[0]) if len(recent_high_max) > 0 else None
                    else:
                        recent_high = float(recent_high_max) if pd.notna(recent_high_max) else None
                else:
                    recent_high = None
            except Exception:
                recent_high = None
            
            try:
                if len(recent_low_series) > 0:
                    recent_low_min = recent_low_series.min()
                    # 如果返回的是Series，取第一个值；如果是标量，直接使用
                    if isinstance(recent_low_min, pd.Series):
                        recent_low = float(recent_low_min.iloc[0]) if len(recent_low_min) > 0 else None
                    else:
                        recent_low = float(recent_low_min) if pd.notna(recent_low_min) else None
                else:
                    recent_low = None
            except Exception:
                recent_low = None
            
            indicators['20周最高'] = recent_high
            indicators['20周最低'] = recent_low
            
            if recent_high is not None and current_price > 0:
                indicators['距离20周最高'] = float((recent_high - current_price) / current_price * 100)
            else:
                indicators['距离20周最高'] = None
            
            if recent_low is not None and current_price > 0:
                indicators['距离20周最低'] = float((current_price - recent_low) / current_price * 100)
            else:
                indicators['距离20周最低'] = None
        
        return jsonify(indicators)
    except Exception as e:
        import traceback
        error_msg = f'获取技术指标失败: {str(e)}\n{traceback.format_exc()}'
        return jsonify({'error': error_msg}), 500

if __name__ == '__main__':
    print("=" * 80)
    print("周线K线图Web应用")
    print("=" * 80)
    # macOS + Werkzeug reloader/debugger 组合容易触发 selectors.kevent 的 TypeError
    # 这里默认使用 waitress（更稳），并允许通过环境变量 WEEKLY_KLINE_PORT 配置端口
    import os
    port = int(os.environ.get("WEEKLY_KLINE_PORT", "5001"))
    print(f"访问地址: http://localhost:{port}")
    print("所有K线数据和分析都基于周线")
    print("=" * 80)
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=port, threads=8)
    except ImportError:
        # 兜底：关闭 reloader/debug，避免 kevent 问题
        app.run(host="0.0.0.0", port=port, debug=False, threaded=True, use_reloader=False)

