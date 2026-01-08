"""
A股量价分析选股软件 - Web应用
"""
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from stock_screener import StockScreener
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stock_screener_secret_key'
# 使用async_mode='threading'确保在后台线程中可以正常发送消息
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 全局变量存储分析任务
analysis_thread = None
analysis_running = False


class WebStockScreener(StockScreener):
    """支持WebSocket进度推送的选股器"""
    
    def __init__(self, socketio_instance):
        super().__init__()
        self.socketio = socketio_instance
        self.request_context = None
    
    def screen_all_stocks_web(self, limit=None, exclude_st=True, save_interval=100, 
                              conditions=None):
        """
        支持WebSocket推送的选股方法
        :param conditions: 选股条件字典
        """
        import time
        
        # 先发送"正在获取股票列表"的消息
        try:
            # 使用socketio的emit方法，确保在正确的上下文中
            from flask import has_app_context
            if has_app_context():
                socketio.emit('progress', {
                    'total': 0,
                    'current': 0,
                    'percentage': 0,
                    'elapsed': 0,
                    'remaining': 0,
                    'message': '正在获取股票列表...',
                    'found_count': 0
                }, namespace='/')
            else:
                print("警告：不在应用上下文中，无法发送消息")
            print("已发送'正在获取股票列表'消息")
        except Exception as e:
            print(f"发送进度消息失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 获取所有股票列表
        print("开始获取股票列表...")
        stock_list = self.data_fetcher.get_all_stocks()
        print(f"获取股票列表完成，共 {len(stock_list) if stock_list is not None else 0} 只")
        if stock_list is None or stock_list.empty:
            socketio.emit('error', {'message': '无法获取股票列表'})
            return []
        
        # 排除ST股票
        if exclude_st:
            stock_list = stock_list[~stock_list['name'].str.contains('ST')]
        
        # 限制数量
        if limit:
            stock_list = stock_list.head(limit)
        
        total = len(stock_list)
        
        # 立即发送总股票数，让前端先显示总数
        try:
            from flask import has_app_context
            if has_app_context():
                socketio.emit('progress', {
                    'total': total,
                    'current': 0,
                    'percentage': 0,
                    'elapsed': 0,
                    'remaining': 0,
                    'message': f'已获取 {total} 只股票，准备开始分析...',
                    'found_count': 0
                }, namespace='/')
            print(f"已发送总股票数: {total}")
        except Exception as e:
            print(f"发送总股票数失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 等待一小段时间，确保前端收到总数
        time.sleep(0.3)
        
        results = []
        start_time = time.time()
        
        for idx, row in stock_list.iterrows():
            if not analysis_running:
                socketio.emit('progress', {
                    'total': total,
                    'current': idx + 1,
                    'percentage': (idx + 1) / total * 100,
                    'message': '分析已取消'
                })
                break
            
            stock_code = row['code']
            stock_name = row['name']
            
            try:
                is_selected, detail = self.screen_stock(stock_code, stock_name, conditions=conditions)
                
                if is_selected:
                    results.append(detail)
                    # 立即发送找到的股票信息
                    try:
                        socketio.emit('stock_found', {
                            'code': stock_code,
                            'name': stock_name,
                            'price': float(current_price),
                            'startup_price': float(startup_price) if startup_price else None,
                            'reversal_date': str(reversal_date) if reversal_date else None,
                            'detail': detail
                        })
                    except Exception as e:
                        print(f"发送找到股票消息失败: {e}")
                
                # 计算进度
                elapsed = time.time() - start_time
                if idx > 0:
                    avg_time = elapsed / (idx + 1)
                    remaining = (total - idx - 1) * avg_time
                    remaining_min = int(remaining / 60)
                    remaining_sec = int(remaining % 60)
                else:
                    remaining_min = 0
                    remaining_sec = 0
                
                progress_pct = (idx + 1) / total * 100
                
                # 发送进度更新（每只股票都发送，确保实时性）
                try:
                    from flask import has_app_context
                    if has_app_context():
                        socketio.emit('progress', {
                            'total': total,
                            'current': idx + 1,
                            'percentage': progress_pct,
                            'elapsed': int(elapsed),
                            'remaining': remaining_min * 60 + remaining_sec,
                            'message': f'正在分析: {stock_code} {stock_name}',
                            'found_count': len(results)
                        }, namespace='/')
                except Exception as e:
                    print(f"发送进度更新失败: {e}")
                
                # 定期保存
                if (idx + 1) % save_interval == 0:
                    self.results = results
                    try:
                        socketio.emit('save_checkpoint', {
                            'count': idx + 1,
                            'found': len(results)
                        })
                    except Exception as e:
                        print(f"发送保存检查点失败: {e}")
                
                # 添加延迟（减少延迟，让进度更新更频繁）
                if (idx + 1) % 50 == 0:
                    time.sleep(0.5)
                else:
                    time.sleep(0.05)  # 减少延迟，提高更新频率
                    
            except Exception as e:
                try:
                    socketio.emit('error', {
                        'message': f'分析 {stock_code} ({stock_name}) 时出错: {str(e)}'
                    })
                except:
                    pass
                print(f"分析 {stock_code} ({stock_name}) 时出错: {e}")
                continue
        
        total_time = time.time() - start_time
        try:
            socketio.emit('complete', {
                'total': total,
                'found': len(results),
                'time': int(total_time)
            })
        except Exception as e:
            print(f"发送完成消息失败: {e}")
        
        self.results = results
        return results


@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')


@app.route('/<filename>')
def download_file(filename):
    """下载文件"""
    from flask import send_file
    import os
    if filename.endswith('.xlsx') and os.path.exists(filename):
        return send_file(filename, as_attachment=True)
    return "文件不存在", 404


@app.route('/api/start', methods=['POST'])
def start_analysis():
    """开始分析"""
    global analysis_thread, analysis_running, current_screener
    
    if analysis_running:
        return jsonify({'error': '分析正在进行中'}), 400
    
    data = request.json
    limit = data.get('limit')
    exclude_st = data.get('exclude_st', True)
    conditions = data.get('conditions', {})
    
    # 创建选股器
    current_screener = WebStockScreener(socketio)
    
    # 启动分析线程
    analysis_running = True
    analysis_thread = threading.Thread(
        target=run_analysis,
        args=(current_screener, limit, exclude_st, conditions)
    )
    analysis_thread.daemon = True
    analysis_thread.start()
    
    return jsonify({'status': 'started'})


def run_analysis(screener, limit, exclude_st, conditions):
    """运行分析的包装函数"""
    global analysis_running
    try:
        # 在应用上下文中运行，确保WebSocket可以正常工作
        with app.app_context():
            screener.screen_all_stocks_web(limit=limit, exclude_st=exclude_st, save_interval=100, conditions=conditions)
    except Exception as e:
        print(f"分析过程出错: {e}")
        import traceback
        traceback.print_exc()
        try:
            socketio.emit('error', {'message': f'分析出错: {str(e)}'})
        except:
            pass
    finally:
        analysis_running = False


@app.route('/api/stop', methods=['POST'])
def stop_analysis():
    """停止分析"""
    global analysis_running
    analysis_running = False
    socketio.emit('stopped', {'message': '分析已停止'})
    return jsonify({'status': 'stopped'})


@app.route('/api/results', methods=['GET'])
def get_results():
    """获取结果"""
    global current_screener
    if current_screener and hasattr(current_screener, 'results'):
        return jsonify({'results': current_screener.results})
    return jsonify({'results': []})


@app.route('/api/export', methods=['POST'])
def export_results():
    """导出结果到Excel"""
    global current_screener
    try:
        if current_screener and hasattr(current_screener, 'results') and current_screener.results:
            import pandas as pd
            from datetime import datetime
            
            df = pd.DataFrame(current_screener.results)
            filename = f'选股结果_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            filepath = filename
            
            df.to_excel(filepath, index=False, engine='openpyxl')
            
            return jsonify({
                'status': 'success',
                'filename': filename,
                'message': f'已导出 {len(current_screener.results)} 只股票到 {filename}'
            })
        else:
            return jsonify({'status': 'error', 'message': '没有结果可导出'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'导出失败: {str(e)}'}), 500


@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    print(f'客户端已连接: {request.sid}')
    emit('connected', {'message': '已连接到服务器'})


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开"""
    print('客户端断开连接')


if __name__ == '__main__':
    print("=" * 80)
    print("A股量价分析选股软件 - Web版")
    print("=" * 80)
    print("访问地址: http://localhost:5000")
    print("=" * 80)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)

