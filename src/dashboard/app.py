"""
数据可视化仪表盘
Flask Web应用，展示竞品监控数据
"""

import os
import sys
import json
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify, request

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config_loader import get_config
from src.analyzer.price_trend import PriceTrendAnalyzer
from src.analyzer.promotion_analyzer import PromotionAnalyzer
from src.analyzer.review_analyzer import ReviewAnalyzer

logger = logging.getLogger(__name__)

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')

# 加载配置
config = get_config('./config')

# 初始化分析器
price_trend_analyzer = PriceTrendAnalyzer(config)
promotion_analyzer = PromotionAnalyzer(config)
review_analyzer = ReviewAnalyzer(config)


@app.route('/')
def index():
    """首页 - 仪表盘概览"""
    return render_template('index.html')


@app.route('/api/price-trends')
def api_price_trends():
    """API: 获取价格趋势数据"""
    days = request.args.get('days', 7, type=int)
    game = request.args.get('game', None)
    
    date_str = datetime.now().strftime('%Y-%m-%d')
    trends = price_trend_analyzer.analyze_trends(date_str, days)
    
    # 如果指定了游戏，只返回该游戏的数据
    if game and game in trends.get('game_trends', {}):
        return jsonify({
            'game': game,
            'trend': trends['game_trends'][game],
            'competitiveness': trends.get('competitiveness', {}).get(game, {})
        })
    
    return jsonify(trends)


@app.route('/api/price-comparison')
def api_price_comparison():
    """API: 获取今日价格对比数据"""
    from src.analyzer.price_comparison import PriceComparisonAnalyzer
    
    analyzer = PriceComparisonAnalyzer(config)
    date_str = datetime.now().strftime('%Y-%m-%d')
    parsed_data = analyzer.load_parsed_data(date_str)
    comparisons = analyzer.analyze(parsed_data, date_str)
    
    return jsonify({
        'date': date_str,
        'comparisons': comparisons
    })


@app.route('/api/promotions')
def api_promotions():
    """API: 获取促销分析数据"""
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    from src.analyzer.price_comparison import PriceComparisonAnalyzer
    analyzer = PriceComparisonAnalyzer(config)
    parsed_data = analyzer.load_parsed_data(date_str)
    
    promotions = promotion_analyzer.analyze(parsed_data, date_str)
    
    return jsonify(promotions)


@app.route('/api/reviews')
def api_reviews():
    """API: 获取用户反馈分析数据"""
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    from src.analyzer.price_comparison import PriceComparisonAnalyzer
    analyzer = PriceComparisonAnalyzer(config)
    parsed_data = analyzer.load_parsed_data(date_str)
    
    reviews = review_analyzer.analyze(parsed_data, date_str)
    
    return jsonify(reviews)


@app.route('/api/historical-data')
def api_historical_data():
    """API: 获取历史数据用于图表"""
    game = request.args.get('game', '')
    days = request.args.get('days', 30, type=int)
    
    if not game:
        return jsonify({'error': '请指定游戏名称'}), 400
    
    end_date = datetime.now()
    historical_data = []
    
    for i in range(days):
        current_date = end_date - timedelta(days=i)
        date_str = current_date.strftime('%Y-%m-%d')
        
        # 加载该日期的价格数据
        parsed_data = price_trend_analyzer._load_parsed_data(date_str)
        
        day_data = {'date': date_str, 'prices': {}}
        
        for site_name, pages in parsed_data.items():
            for page_key, data in pages.items():
                if data.get('game') == game:
                    prices = data.get('prices', [])
                    if prices:
                        min_price = min(prices, key=lambda x: float(x.get('value', 0) or 0))
                        day_data['prices'][site_name] = {
                            'price': float(min_price.get('value', 0)),
                            'raw': min_price.get('raw', '')
                        }
                        
        if day_data['prices']:
            historical_data.append(day_data)
            
    # 按日期排序
    historical_data.sort(key=lambda x: x['date'])
    
    return jsonify({
        'game': game,
        'days': days,
        'data': historical_data
    })


@app.route('/api/games')
def api_games():
    """API: 获取监控的游戏列表"""
    target_games = config.get('target_games', [])
    games = [{'name': g['name'], 'aliases': g.get('aliases', [])} for g in target_games]
    return jsonify(games)


@app.route('/api/sites')
def api_sites():
    """API: 获取监控的站点列表"""
    competitors = config.get('competitors', [])
    sites = [{'name': c['name'], 'domain': c['domain'], 'is_own': c.get('is_own_site', False)} 
             for c in competitors]
    return jsonify(sites)


@app.route('/price-trends')
def price_trends_page():
    """价格趋势页面"""
    return render_template('price_trends.html')


@app.route('/price-comparison')
def price_comparison_page():
    """价格对比页面"""
    return render_template('price_comparison.html')


@app.route('/promotions')
def promotions_page():
    """促销策略页面"""
    return render_template('promotions.html')


@app.route('/reviews')
def reviews_page():
    """用户反馈页面"""
    return render_template('reviews.html')


def run_dashboard(host='0.0.0.0', port=5000, debug=False):
    """运行仪表盘服务"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info(f"启动仪表盘服务: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_dashboard(debug=True)
