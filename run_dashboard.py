"""
启动仪表盘服务
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.dashboard.app import run_dashboard

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='启动竞品监控仪表盘')
    parser.add_argument('--host', default='0.0.0.0', help='主机地址 (默认: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000, help='端口号 (默认: 5000)')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     TOPUPlive 竞品监控仪表盘                                  ║
║                                                              ║
║     访问地址: http://{args.host}:{args.port}                    ║
║     调试模式: {'开启' if args.debug else '关闭'}                          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    run_dashboard(host=args.host, port=args.port, debug=args.debug)
