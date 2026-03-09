"""
用户反馈分析模块
提取评价关键词、进行情感分析、识别反馈趋势
"""

import os
import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import timedelta
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class ReviewAnalyzer:
    """用户反馈分析器"""
    
    # 关键词分类
    KEYWORD_CATEGORIES = {
        'delivery': {
            'name': '发货/到账速度',
            'positive': ['fast', 'quick', 'instant', 'immediate', 'smooth', '顺利', '快', '及时', '秒到'],
            'negative': ['slow', 'delay', 'late', 'pending', '慢', '延迟', '等很久', '不到账']
        },
        'price': {
            'name': '价格/性价比',
            'positive': ['cheap', 'affordable', 'good price', 'worth', '便宜', '实惠', '划算', '超值'],
            'negative': ['expensive', 'overpriced', '贵', '不值', '坑', '骗']
        },
        'service': {
            'name': '客服服务',
            'positive': ['helpful', 'friendly', 'responsive', 'professional', 'helpful', '好', '耐心', '专业'],
            'negative': ['rude', 'unhelpful', 'no response', 'bad service', '差', '不理人', '态度差']
        },
        'trust': {
            'name': '信任/安全',
            'positive': ['legit', 'trusted', 'safe', 'reliable', 'secure', '正规', '靠谱', '安全'],
            'negative': ['scam', 'fraud', 'fake', 'suspicious', '骗子', '假', '盗号', '风险']
        },
        'experience': {
            'name': '购买体验',
            'positive': ['easy', 'smooth', 'convenient', 'simple', '方便', '简单', '顺畅'],
            'negative': ['complicated', 'difficult', 'confusing', '麻烦', '复杂', '难用', '卡']
        }
    }
    
    # 情感词库
    SENTIMENT_WORDS = {
        'positive': [
            'good', 'great', 'excellent', 'amazing', 'awesome', 'perfect', 'love', 'best',
            'recommend', 'satisfied', 'happy', 'pleased', 'smooth', 'easy', 'fast',
            '好', '棒', '赞', '满意', '推荐', '喜欢', '完美', '不错'
        ],
        'negative': [
            'bad', 'terrible', 'awful', 'worst', 'hate', 'disappointed', 'frustrated',
            'annoying', 'useless', 'waste', 'scam', 'fraud', 'fake', 'slow',
            '差', '烂', '失望', '垃圾', '坑', '骗', '气死', '后悔'
        ]
    }
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.paths_config = config.get('paths', {})
        
    def analyze(self, parsed_data: Dict[str, Any], date_str: str) -> Dict[str, Any]:
        """
        分析用户反馈
        
        Args:
            parsed_data: 解析后的数据
            date_str: 日期字符串
            
        Returns:
            反馈分析结果
        """
        results = {
            'date': date_str,
            'reviews_by_site': {},
            'reviews_by_game': {},
            'keyword_analysis': {},
            'sentiment_summary': {},
            'trending_issues': [],
            'trustpilot_data': {}  # 新增：Trustpilot评价数据
        }
        
        # 首先提取Trustpilot数据（作为评价基准）
        trustpilot_data = self._extract_trustpilot_data(parsed_data)
        results['trustpilot_data'] = trustpilot_data
        
        # 收集所有评价数据
        all_reviews = []
        
        for site_name, pages in parsed_data.items():
            site_reviews = []
            
            for page_key, data in pages.items():
                # 跳过Trustpilot页面（已单独处理）
                if data.get('type') == 'trustpilot_review':
                    continue
                    
                if not page_key.startswith('product'):
                    continue
                    
                game = data.get('game', '')
                
                # 只使用Trustpilot数据作为评价基准
                # 网站自身页面的评价数据不再使用
                site_name_upper = site_name.upper()
                # 支持多种站点名称匹配（如 LDShop 可以匹配 LDSHOP）
                tp_key = None
                for key in trustpilot_data.keys():
                    if key == site_name_upper or key.replace(' ', '') == site_name_upper.replace(' ', ''):
                        tp_key = key
                        break
                
                if tp_key:
                    tp_data = trustpilot_data[tp_key]
                    rating = tp_data.get('rating')
                    review_count = tp_data.get('review_count')
                    review_source = 'trustpilot'
                else:
                    # 没有Trustpilot数据时，评价数据为空
                    rating = None
                    review_count = None
                    review_source = 'none'
                    
                # 构建评价记录
                review_record = {
                    'site': site_name,
                    'game': game,
                    'rating': rating,
                    'review_count': review_count,
                    'review_source': review_source,  # 标记数据来源
                    'text': '',  # 从页面文本中提取评价内容
                    'keywords': [],
                    'sentiment': 'neutral'
                }
                
                # 提取关键词
                keywords = self._extract_keywords(data)
                review_record['keywords'] = keywords
                
                # 情感分析
                sentiment = self._analyze_sentiment(data, keywords)
                review_record['sentiment'] = sentiment
                
                if game:
                    if game not in results['reviews_by_game']:
                        results['reviews_by_game'][game] = []
                    results['reviews_by_game'][game].append(review_record)
                    
                site_reviews.append(review_record)
                all_reviews.append(review_record)
                
            if site_reviews:
                results['reviews_by_site'][site_name] = site_reviews
                
        # 关键词分析
        results['keyword_analysis'] = self._analyze_keywords(all_reviews)
        
        # 情感汇总（包含Trustpilot数据）
        results['sentiment_summary'] = self._summarize_sentiment(all_reviews, trustpilot_data)
        
        # 趋势问题识别
        results['trending_issues'] = self._identify_trending_issues(results['reviews_by_game'])
        
        return results
        
    def _extract_trustpilot_data(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从解析数据中提取Trustpilot评价数据
        
        Args:
            parsed_data: 解析后的数据
            
        Returns:
            Trustpilot数据字典，按站点名称索引
        """
        trustpilot_data = {}
        
        for site_name, pages in parsed_data.items():
            for page_key, data in pages.items():
                if data.get('type') == 'trustpilot_review':
                    site_name_from_data = data.get('site_name', '').upper()
                    if site_name_from_data:
                        trustpilot_data[site_name_from_data] = {
                            'rating': data.get('rating'),
                            'review_count': data.get('review_count'),
                            'trust_score': data.get('trust_score'),
                            'rating_distribution': data.get('rating_distribution', {}),
                            'url': data.get('url', '')
                        }
                        logger.info(f"提取到Trustpilot数据: {site_name_from_data}, "
                                   f"评分: {data.get('rating')}, 评价数: {data.get('review_count')}")
        
        return trustpilot_data
        
    def _extract_keywords(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取关键词"""
        keywords = []
        text = data.get('text', '').lower()
        
        for category_key, category_info in self.KEYWORD_CATEGORIES.items():
            # 检查正面关键词
            for word in category_info['positive']:
                if word in text:
                    keywords.append({
                        'category': category_key,
                        'category_name': category_info['name'],
                        'word': word,
                        'sentiment': 'positive'
                    })
                    
            # 检查负面关键词
            for word in category_info['negative']:
                if word in text:
                    keywords.append({
                        'category': category_key,
                        'category_name': category_info['name'],
                        'word': word,
                        'sentiment': 'negative'
                    })
                    
        return keywords
        
    def _analyze_sentiment(self, data: Dict[str, Any], 
                          keywords: List[Dict]) -> str:
        """分析情感倾向"""
        text = data.get('text', '').lower()
        rating = data.get('rating')
        
        # 基于评分判断
        if rating is not None:
            if rating >= 4:
                return 'positive'
            elif rating <= 2:
                return 'negative'
                
        # 基于关键词判断
        positive_count = sum(1 for k in keywords if k['sentiment'] == 'positive')
        negative_count = sum(1 for k in keywords if k['sentiment'] == 'negative')
        
        # 基于情感词判断
        for word in self.SENTIMENT_WORDS['positive']:
            if word in text:
                positive_count += 1
                
        for word in self.SENTIMENT_WORDS['negative']:
            if word in text:
                negative_count += 1
                
        # 综合判断
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
            
    def _analyze_keywords(self, reviews: List[Dict]) -> Dict[str, Any]:
        """分析关键词统计"""
        analysis = {
            'top_keywords': [],
            'category_distribution': defaultdict(lambda: {'positive': 0, 'negative': 0}),
            'keyword_trends': {}
        }
        
        keyword_counter = Counter()
        
        for review in reviews:
            for keyword in review.get('keywords', []):
                word = keyword['word']
                category = keyword['category']
                sentiment = keyword['sentiment']
                
                keyword_counter[word] += 1
                analysis['category_distribution'][category][sentiment] += 1
                
        # 高频关键词
        analysis['top_keywords'] = [
            {'word': word, 'count': count}
            for word, count in keyword_counter.most_common(10)
        ]
        
        analysis['category_distribution'] = dict(analysis['category_distribution'])
        
        return analysis
        
    def _summarize_sentiment(self, reviews: List[Dict], 
                              trustpilot_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        汇总情感分析
        
        Args:
            reviews: 评价列表
            trustpilot_data: Trustpilot数据字典
        """
        summary = {
            'total_reviews': len(reviews),
            'sentiment_distribution': {'positive': 0, 'negative': 0, 'neutral': 0},
            'average_rating': 0,
            'rating_by_site': {},
            'rating_by_game': {},
            'trustpilot_summary': {}  # 新增：Trustpilot数据汇总
        }
        
        ratings = []
        
        for review in reviews:
            sentiment = review.get('sentiment', 'neutral')
            summary['sentiment_distribution'][sentiment] += 1
            
            rating = review.get('rating')
            if rating:
                ratings.append(rating)
                
            # 按站点统计
            site = review.get('site', '')
            if site:
                if site not in summary['rating_by_site']:
                    summary['rating_by_site'][site] = []
                if rating:
                    summary['rating_by_site'][site].append(rating)
                    
            # 按游戏统计
            game = review.get('game', '')
            if game:
                if game not in summary['rating_by_game']:
                    summary['rating_by_game'][game] = []
                if rating:
                    summary['rating_by_game'][game].append(rating)
                    
        # 计算平均分
        if ratings:
            summary['average_rating'] = round(sum(ratings) / len(ratings), 2)
            
        # 计算各站点平均分（优先使用Trustpilot数据）
        for site, site_ratings in summary['rating_by_site'].items():
            site_upper = site.upper()
            if trustpilot_data and site_upper in trustpilot_data:
                # 使用Trustpilot数据
                tp_rating = trustpilot_data[site_upper].get('rating')
                if tp_rating:
                    summary['rating_by_site'][site] = tp_rating
            elif site_ratings:
                summary['rating_by_site'][site] = round(sum(site_ratings) / len(site_ratings), 2)
                
        # 计算各游戏平均分
        for game, game_ratings in summary['rating_by_game'].items():
            if game_ratings:
                summary['rating_by_game'][game] = round(sum(game_ratings) / len(game_ratings), 2)
        
        # 添加Trustpilot数据汇总
        if trustpilot_data:
            summary['trustpilot_summary'] = {
                site: {
                    'rating': data.get('rating'),
                    'review_count': data.get('review_count'),
                    'trust_score': data.get('trust_score'),
                    'url': data.get('url', '')
                }
                for site, data in trustpilot_data.items()
            }
                
        return summary
        
    def _identify_trending_issues(self, reviews_by_game: Dict[str, List]) -> List[Dict]:
        """识别趋势性问题"""
        issues = []
        
        for game, reviews in reviews_by_game.items():
            # 统计各分类的负面反馈
            category_negatives = defaultdict(int)
            
            for review in reviews:
                for keyword in review.get('keywords', []):
                    if keyword['sentiment'] == 'negative':
                        category_negatives[keyword['category']] += 1
                        
            # 找出问题最多的分类
            if category_negatives:
                top_issue = max(category_negatives.items(), key=lambda x: x[1])
                if top_issue[1] >= 2:  # 至少2次提及
                    category_name = self.KEYWORD_CATEGORIES.get(
                        top_issue[0], {}
                    ).get('name', top_issue[0])
                    
                    issues.append({
                        'game': game,
                        'issue_category': top_issue[0],
                        'issue_name': category_name,
                        'mention_count': top_issue[1],
                        'severity': 'high' if top_issue[1] >= 5 else 'medium'
                    })
                    
        # 按严重程度排序
        issues.sort(key=lambda x: x['mention_count'], reverse=True)
        
        return issues[:5]  # 返回前5个问题
        
    def export_to_csv(self, review_results: Dict[str, Any], 
                     output_path: str) -> str:
        """
        导出反馈分析数据到CSV
        
        Args:
            review_results: 反馈分析结果
            output_path: 输出文件路径
            
        Returns:
            输出文件路径
        """
        import csv
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # 写入表头
            writer.writerow([
                '站点', '游戏', '评分', '评价数', '情感倾向', '关键词', '关键词类别'
            ])
            
            # 写入数据
            for site_name, reviews in review_results.get('reviews_by_site', {}).items():
                for review in reviews:
                    keywords = review.get('keywords', [])
                    keyword_str = ', '.join([k['word'] for k in keywords])
                    category_str = ', '.join([k['category_name'] for k in keywords])
                    
                    writer.writerow([
                        site_name,
                        review.get('game', ''),
                        review.get('rating', ''),
                        review.get('review_count', ''),
                        review.get('sentiment', ''),
                        keyword_str,
                        category_str
                    ])
                    
        logger.info(f"反馈分析数据已导出: {output_path}")
        return output_path
