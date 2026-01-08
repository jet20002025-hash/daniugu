"""
暴涨股票分析 - Web界面
"""
from flask import Flask, render_template, request, jsonify
from surge_stock_analyzer import SurgeStockAnalyzer
import threading
import pandas as pd
import numpy as np
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'surge_stock_analyzer_secret_key'

analyzer = SurgeStockAnalyzer()
analysis_running = False
scan_results = []  # 存储扫描结果


@app.route('/')
def index():
    """主页面"""
    return render_template('surge_analysis.html')


@app.route('/api/add_stock', methods=['POST'])
def add_stock():
    """添加暴涨股票"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': '请求数据为空'}), 400
            
        stock_code = data.get('stock_code')
        stock_name = data.get('stock_name')
        surge_date = data.get('surge_date')  # 可选
        
        if not stock_code or not stock_name:
            return jsonify({'error': '股票代码和名称不能为空'}), 400
        
        print(f"收到添加股票请求: {stock_code} {stock_name}")
        
        features = analyzer.add_surge_stock(stock_code, stock_name, surge_date)
        if features:
            print(f"✅ 成功添加 {stock_code} {stock_name}，提取了 {len(features)} 个特征")
            # 确保features可以序列化为JSON
            # 导入必要的模块
            import pandas as pd
            import numpy as np
            from datetime import datetime
            
            features_json = {}
            for key, value in features.items():
                if isinstance(value, (pd.Timestamp, datetime)):
                    features_json[key] = str(value)
                elif isinstance(value, (np.integer, np.int64)):
                    features_json[key] = int(value)
                elif isinstance(value, (np.floating, np.float64)):
                    features_json[key] = float(value)
                elif isinstance(value, np.ndarray):
                    features_json[key] = value.tolist()
                elif pd.isna(value):
                    features_json[key] = None
                else:
                    features_json[key] = value
            
            return jsonify({
                'status': 'success',
                'message': f'已添加 {stock_name}',
                'features': features_json
            })
        else:
            # 提供更详细的错误信息
            error_msg = f'无法添加股票 {stock_name}({stock_code})。可能的原因：\n'
            error_msg += '1. 股票代码不正确\n'
            error_msg += '2. 该股票一个月内涨幅未翻倍（<100%），不符合暴涨条件\n'
            error_msg += '3. 数据不足（需要至少50天历史数据）\n'
            error_msg += '请查看服务器控制台的详细错误信息'
            return jsonify({'error': error_msg}), 400
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"添加股票时出错: {error_msg}")
        print(f"错误详情: {error_trace}")
        return jsonify({'error': f'服务器错误: {error_msg}'}), 500


@app.route('/api/analyze', methods=['POST'])
def analyze_features():
    """分析共同特征"""
    try:
        print("开始分析共同特征...")
        common_features = analyzer.analyze_common_features()
        if common_features:
            # 确保所有值都可以序列化为JSON
            features_json = {}
            for key, stats in common_features.items():
                stats_json = {}
                for stat_key, stat_value in stats.items():
                    # 转换numpy类型为Python原生类型
                    if isinstance(stat_value, (np.integer, np.int64, np.int32)):
                        stats_json[stat_key] = int(stat_value)
                    elif isinstance(stat_value, (np.floating, np.float64, np.float32)):
                        stats_json[stat_key] = float(stat_value)
                    elif isinstance(stat_value, np.ndarray):
                        stats_json[stat_key] = stat_value.tolist()
                    elif pd.isna(stat_value):
                        stats_json[stat_key] = None
                    else:
                        stats_json[stat_key] = stat_value
                features_json[key] = stats_json
            
            # 为每只已添加的股票提取买点信息
            stocks_with_buy_points = []
            for stock in analyzer.surge_stocks:
                stock_code = stock.get('股票代码')
                stock_name = stock.get('股票名称')
                surge_date = stock.get('暴涨日期')
                
                if stock_code and stock_name:
                    try:
                        # 获取该股票的买点（使用暴涨日期作为参考）
                        buy_points = analyzer.find_best_buy_points(stock_code, stock_name)
                        
                        stock_info = {
                            '股票代码': stock_code,
                            '股票名称': stock_name,
                            '暴涨日期': str(surge_date) if surge_date else 'N/A',
                            '买点数量': len(buy_points) if buy_points else 0
                        }
                        
                        # 如果有买点，优先选择最佳买点（买入后一个月内翻倍的）
                        if buy_points and len(buy_points) > 0:
                            # 优先选择最佳买点（买入后一个月内翻倍的）
                            best_buy_points = [p for p in buy_points if p.get('是否最佳买点', False)]
                            if best_buy_points:
                                best_point = best_buy_points[0]  # 选择最佳买点中的第一个
                            else:
                                best_point = buy_points[0]  # 如果没有最佳买点，选择匹配度最高的
                            
                            performance = best_point.get('买入后表现') or {}
                            performance_json = {}
                            if performance:
                                for perf_key, perf_value in performance.items():
                                    if isinstance(perf_value, (pd.Timestamp, datetime)):
                                        performance_json[perf_key] = str(perf_value)
                                    elif isinstance(perf_value, (np.integer, np.int64, np.int32)):
                                        performance_json[perf_key] = int(perf_value)
                                    elif isinstance(perf_value, (np.floating, np.float64, np.float32)):
                                        performance_json[perf_key] = float(perf_value)
                                    elif isinstance(perf_value, (np.bool_, bool)):
                                        # 处理numpy bool类型
                                        performance_json[perf_key] = bool(perf_value)
                                    elif pd.isna(perf_value):
                                        performance_json[perf_key] = None
                                    else:
                                        performance_json[perf_key] = perf_value
                            
                            stock_info['最佳买点'] = {
                                '日期': str(best_point['日期']) if best_point.get('日期') else 'N/A',
                                '价格': float(best_point['价格']) if best_point.get('价格') else 0,
                                '匹配度': float(best_point['匹配度']) if best_point.get('匹配度') else 0,
                                '买入后表现': performance_json,
                                '是否最佳买点': bool(best_point.get('是否最佳买点', False))  # 买入后一个月内翻倍才算最佳买点
                            }
                        
                        stocks_with_buy_points.append(stock_info)
                    except Exception as e:
                        print(f"处理股票 {stock_code} {stock_name} 的买点时出错: {e}")
                        stocks_with_buy_points.append({
                            '股票代码': stock_code,
                            '股票名称': stock_name,
                            '暴涨日期': str(surge_date) if surge_date else 'N/A',
                            '买点数量': 0,
                            '错误': str(e)
                        })
            
            return jsonify({
                'status': 'success',
                'features': features_json,
                'stocks_with_buy_points': stocks_with_buy_points  # 添加每只股票的买点信息
            })
        else:
            return jsonify({'error': '没有股票数据或分析失败'}), 400
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"分析特征时出错: {error_msg}")
        print(f"错误详情: {error_trace}")
        return jsonify({'error': f'服务器错误: {error_msg}'}), 500


@app.route('/api/find_buy_point', methods=['POST'])
def find_buy_point():
    """寻找买点"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': '请求数据为空'}), 400
            
        stock_code = data.get('stock_code')
        stock_name = data.get('stock_name')
        
        if not stock_code or not stock_name:
            return jsonify({'error': '股票代码和名称不能为空'}), 400
        
        print(f"寻找买点: {stock_code} {stock_name}")
        
        buy_points = analyzer.find_best_buy_points(stock_code, stock_name)
        if buy_points:
            # 确保日期可以序列化为JSON
            buy_points_json = []
            for point in buy_points[:10]:
                # 处理买入后表现
                performance = point.get('买入后表现', {})
                performance_json = {}
                if performance:
                    for key, value in performance.items():
                        if isinstance(value, (pd.Timestamp, datetime)):
                            performance_json[key] = str(value)
                        elif isinstance(value, (np.integer, np.int64)):
                            performance_json[key] = int(value)
                        elif isinstance(value, (np.floating, np.float64)):
                            performance_json[key] = float(value)
                        elif pd.isna(value):
                            performance_json[key] = None
                        else:
                            performance_json[key] = value
                
                point_json = {
                    '日期': str(point['日期']) if point.get('日期') else 'N/A',
                    '价格': float(point['价格']) if point.get('价格') else 0,
                    '匹配度': float(point['匹配度']) if point.get('匹配度') else 0,
                    '特征': point.get('特征', {}),
                    '买入后表现': performance_json  # 添加买入后表现
                }
                buy_points_json.append(point_json)
            
            return jsonify({
                'status': 'success',
                'buy_points': buy_points_json
            })
        else:
            return jsonify({'error': '未找到买点'}), 400
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"寻找买点时出错: {error_msg}")
        print(f"错误详情: {error_trace}")
        return jsonify({'error': f'服务器错误: {error_msg}'}), 500


@app.route('/api/scan', methods=['POST'])
def scan_stocks():
    """扫描所有股票"""
    global analysis_running
    
    if analysis_running:
        return jsonify({'error': '扫描正在进行中'}), 400
    
    data = request.json
    limit = data.get('limit', 100)  # 默认扫描100只
    
    analysis_running = True
    
    def run_scan():
        global analysis_running, scan_results
        try:
            candidates = analyzer.scan_all_stocks(limit=limit)
            # 序列化结果，确保可以JSON化
            candidates_json = []
            for candidate in candidates:
                candidate_json = {}
                for key, value in candidate.items():
                    if key == '买入后表现':
                        # 处理买入后表现
                        performance = value or {}
                        performance_json = {}
                        if performance:
                            for perf_key, perf_value in performance.items():
                                if isinstance(perf_value, (pd.Timestamp, datetime)):
                                    performance_json[perf_key] = str(perf_value)
                                elif isinstance(perf_value, (np.integer, np.int64)):
                                    performance_json[perf_key] = int(perf_value)
                                elif isinstance(perf_value, (np.floating, np.float64, np.float32)):
                                    performance_json[perf_key] = float(perf_value)
                                elif isinstance(perf_value, (np.bool_, bool)):
                                    # 处理numpy bool类型，转换为Python原生bool
                                    performance_json[perf_key] = bool(perf_value)
                                elif pd.isna(perf_value):
                                    performance_json[perf_key] = None
                                elif isinstance(perf_value, np.ndarray):
                                    performance_json[perf_key] = perf_value.tolist()
                                else:
                                    # 尝试转换为Python原生类型
                                    try:
                                        if isinstance(perf_value, (int, float)):
                                            performance_json[perf_key] = float(perf_value)
                                        else:
                                            performance_json[perf_key] = str(perf_value)
                                    except:
                                        performance_json[perf_key] = str(perf_value)
                        candidate_json[key] = performance_json
                    elif isinstance(value, (pd.Timestamp, datetime)):
                        candidate_json[key] = str(value)
                    elif isinstance(value, (np.integer, np.int64)):
                        candidate_json[key] = int(value)
                    elif isinstance(value, (np.floating, np.float64)):
                        candidate_json[key] = float(value)
                    elif pd.isna(value):
                        candidate_json[key] = None
                    else:
                        candidate_json[key] = value
                candidates_json.append(candidate_json)
            
            # 保存到全局变量供前端获取
            scan_results = candidates_json
            print(f"扫描完成，找到 {len(candidates_json)} 只符合条件的股票")
        except Exception as e:
            import traceback
            print(f"扫描出错: {e}")
            print(traceback.format_exc())
            scan_results = []
        finally:
            analysis_running = False
    
    # 在后台线程运行
    thread = threading.Thread(target=run_scan)
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'started', 'message': '扫描已开始'})


@app.route('/api/get_scan_results', methods=['GET'])
def get_scan_results():
    """获取扫描结果"""
    global scan_results, analysis_running
    return jsonify({
        'status': 'running' if analysis_running else 'completed',
        'results': scan_results,
        'count': len(scan_results)
    })


@app.route('/api/get_stocks', methods=['GET'])
def get_stocks():
    """获取已添加的暴涨股票"""
    try:
        # 确保日期可以序列化为JSON
        stocks_json = []
        for stock in analyzer.surge_stocks:
            stock_json = {}
            for key, value in stock.items():
                if isinstance(value, (pd.Timestamp, datetime)):
                    stock_json[key] = str(value)
                elif isinstance(value, (np.integer, np.floating)):
                    stock_json[key] = float(value)
                elif isinstance(value, np.ndarray):
                    stock_json[key] = value.tolist()
                else:
                    stock_json[key] = value
            stocks_json.append(stock_json)
        
        return jsonify({
            'stocks': stocks_json,
            'count': len(analyzer.surge_stocks)
        })
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"获取股票列表时出错: {error_msg}")
        print(f"错误详情: {error_trace}")
        return jsonify({'error': f'服务器错误: {error_msg}'}), 500


if __name__ == '__main__':
    print("=" * 80)
    print("暴涨股票特征学习分析系统 - Web版")
    print("=" * 80)
    print("访问地址: http://localhost:5001")
    print("=" * 80)
    app.run(host='0.0.0.0', port=5001, debug=True)

