#!/usr/bin/env python3
"""
Polymarket 交易分析 Web 应用
Flask 后端，调用 script.py 生成分析结果
"""
import os
import uuid
import shutil
import threading
import time
from flask import Flask, render_template, request, jsonify, send_from_directory, make_response

from script import run_analysis
from slug_discovery import COIN_SLUGS, INTERVALS, discover_markets, generate_day_slugs, slug_to_time
import database as db

# 后台管理路径（从环境变量读取，默认随机生成）
# 生产环境请设置环境变量 ADMIN_PATH，避免使用默认值
import secrets
ADMIN_PATH = os.environ.get('ADMIN_PATH', secrets.token_hex(4))

app = Flask(__name__)

# 存放生成文件的目录
STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
os.makedirs(STATIC_DIR, exist_ok=True)

# 存放永久静态资源的目录
ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
os.makedirs(ASSETS_DIR, exist_ok=True)

# 存储查询任务状态
tasks = {}

# 自动清理配置
CLEANUP_INTERVAL = 300  # 每5分钟检查一次
TASK_EXPIRE_TIME = 1800  # 任务文件30分钟后过期


def auto_cleanup():
    """后台线程：自动清理过期的任务文件"""
    while True:
        time.sleep(CLEANUP_INTERVAL)
        try:
            now = time.time()
            # 遍历 static 目录下的所有任务文件夹
            for task_id in os.listdir(STATIC_DIR):
                task_dir = os.path.join(STATIC_DIR, task_id)
                if not os.path.isdir(task_dir):
                    continue
                # 检查文件夹修改时间
                mtime = os.path.getmtime(task_dir)
                if now - mtime > TASK_EXPIRE_TIME:
                    # 删除过期文件夹
                    shutil.rmtree(task_dir)
                    # 同时清理内存中的任务状态
                    if task_id in tasks:
                        del tasks[task_id]
                    print(f"[自动清理] 已删除过期任务: {task_id}")
        except Exception as e:
            print(f"[自动清理] 错误: {e}")


# 启动清理线程
cleanup_thread = threading.Thread(target=auto_cleanup, daemon=True)
cleanup_thread.start()


def get_or_create_user_id():
    """获取或创建用户ID（从Cookie）"""
    user_id = request.cookies.get('uid')
    if not user_id:
        user_id = str(uuid.uuid4())
    return user_id


def record_visit(page):
    """记录页面访问"""
    user_id = get_or_create_user_id()
    user_agent = request.headers.get('User-Agent', '')
    is_new = db.record_user(user_id)
    db.record_page_view(user_id, page, user_agent)
    return user_id, is_new


def make_response_with_cookie(response, user_id):
    """给响应添加用户ID Cookie"""
    if not request.cookies.get('uid'):
        response.set_cookie('uid', user_id, max_age=365*24*60*60, httponly=True, samesite='Lax')
    return response


@app.route('/')
def home():
    """主页 - 导航入口"""
    user_id, _ = record_visit('home')
    resp = make_response(render_template('home.html'))
    return make_response_with_cookie(resp, user_id)


@app.route('/simple')
def simple():
    """简单查询页面"""
    user_id, _ = record_visit('simple')
    resp = make_response(render_template('index.html'))
    return make_response_with_cookie(resp, user_id)


@app.route('/multi')
def multi():
    """多选项市场查询页面"""
    user_id, _ = record_visit('multi')
    resp = make_response(render_template('multi.html'))
    return make_response_with_cookie(resp, user_id)


@app.route('/trader')
def trader():
    """交易员账户分析页面"""
    user_id, _ = record_visit('trader')
    resp = make_response(render_template('trader.html'))
    return make_response_with_cookie(resp, user_id)


@app.route('/api/discover', methods=['POST'])
def api_discover():
    """
    Discover all markets for a coin + interval on a specific date.
    Used by the multi-option page for batch market discovery.
    请求体: {"coin": "BTC/ETH/SOL/XRP", "interval": "15min/hourly/...", "date": "YYYY-MM-DD", "lang": "zh/en"}
    返回: {"task_id": "任务ID"}
    """
    data = request.get_json()
    coin = data.get('coin', '').strip().upper()
    interval = data.get('interval', '').strip()
    date_str = data.get('date', '').strip()
    lang = data.get('lang', 'zh')

    if coin not in COIN_SLUGS:
        coins = ', '.join(COIN_SLUGS.keys())
        error_msg = f'Unsupported coin. Supported: {coins}' if lang == 'en' else f'不支持的币种，支持: {coins}'
        return jsonify({'error': error_msg}), 400
    if interval not in INTERVALS:
        error_msg = 'Please select an interval' if lang == 'en' else '请选择时间间隔'
        return jsonify({'error': error_msg}), 400
    if not date_str:
        error_msg = 'Please select a date' if lang == 'en' else '请选择日期'
        return jsonify({'error': error_msg}), 400

    task_id = str(uuid.uuid4())[:8]
    cancel_flag = {'cancelled': False, 'percent': 0}
    cycles = 86400 // INTERVALS[interval]['seconds']
    tasks[task_id] = {
        'status': 'running',
        'percent': 0,
        'cancel_flag': cancel_flag,
        'market': f'Discovery: {coin} {interval} {date_str}',
        'address': '',
        'result': None,
        'error': None
    }

    user_id = get_or_create_user_id()
    start_time = time.time()

    def run_task():
        try:
            def progress_cb(completed, total):
                cancel_flag['percent'] = int(completed / total * 95) if total > 0 else 0

            events = discover_markets(
                coin=coin,
                interval=interval,
                date_str=date_str,
                progress_callback=progress_cb,
                cancel_flag=cancel_flag,
                max_workers=15,
            )

            if cancel_flag.get('cancelled'):
                tasks[task_id]['status'] = 'cancelled'
                tasks[task_id]['error'] = 'Cancelled' if lang == 'en' else '已取消'
                return

            cancel_flag['percent'] = 100
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['result'] = {
                'coin': coin,
                'interval': interval,
                'date': date_str,
                'total_cycles': cycles,
                'discovered': len(events),
                'events': events,
            }

            duration = round(time.time() - start_time, 1)
            db.record_query(user_id, 'discover', f'Discover: {coin} {interval}', None, '', 'success', duration)

        except Exception as e:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = str(e)

    thread = threading.Thread(target=run_task)
    thread.start()
    return jsonify({'task_id': task_id})


@app.route('/api/trader/analyze', methods=['POST'])
def trader_analyze():
    """
    分析交易员在某类市场的全天交易记录
    请求体: {"address": "钱包地址", "market_type": "15min/hourly/daily/custom", "keyword": "自定义关键词", "date": "YYYY-MM-DD", "lang": "zh/en", "coin": "BTC/ETH/SOL/XRP (optional)"}
    When coin is provided, uses slug discovery to find all markets for that coin+interval+date,
    then cross-references with the trader's activity.
    返回: {"task_id": "任务ID"}
    """
    import requests as req
    import re
    import datetime as dt
    import json

    data = request.get_json()
    address = data.get('address', '').strip()
    market_type = data.get('market_type', '').strip()
    keyword = data.get('keyword', '').strip()
    date_str = data.get('date', '').strip()
    lang = data.get('lang', 'zh')
    coin = data.get('coin', '').strip().upper()

    if not address or not address.startswith('0x') or len(address) != 42:
        error_msg = 'Please enter a valid wallet address' if lang == 'en' else '请输入有效的钱包地址'
        return jsonify({'error': error_msg}), 400

    # Discovery mode: coin + interval + date
    use_discovery = bool(coin and coin in COIN_SLUGS and market_type in INTERVALS)

    if use_discovery and not date_str:
        error_msg = 'Please select a date for market discovery' if lang == 'en' else '使用市场发现功能请选择日期'
        return jsonify({'error': error_msg}), 400

    # Build search keyword from market type
    type_keywords = {
        '1min': '1 Minute',
        '5min': '5 Minutes',
        '15min': '15 Minutes',
        '30min': '30 Minutes',
        'hourly': 'Hourly',
        'daily': 'Up or Down',
    }

    search_keyword = keyword if market_type == 'custom' and keyword else type_keywords.get(market_type, '')
    if not use_discovery and not search_keyword:
        error_msg = 'Please select a market type or enter a keyword' if lang == 'en' else '请选择市场类型或输入关键词'
        return jsonify({'error': error_msg}), 400

    # Parse date filter
    date_filter = None
    if date_str:
        try:
            date_filter = dt.datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            pass

    task_id = str(uuid.uuid4())[:8]
    cancel_flag = {'cancelled': False, 'percent': 0}
    label = f'{coin} {market_type}' if use_discovery else search_keyword
    tasks[task_id] = {
        'status': 'running',
        'percent': 0,
        'cancel_flag': cancel_flag,
        'market': f'Trader Analysis: {label}',
        'address': address,
        'result': None,
        'error': None
    }

    user_id = get_or_create_user_id()
    start_time = time.time()

    def run_task():
        try:
            if use_discovery:
                _run_discovery_analysis(task_id, cancel_flag, address, coin, market_type, date_str, lang, user_id, start_time)
            else:
                _run_activity_analysis(task_id, cancel_flag, address, market_type, search_keyword, date_filter, date_str, lang, user_id, start_time)
        except Exception as e:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = str(e)
            duration = round(time.time() - start_time, 1)
            db.record_query(user_id, 'trader', f'Trader: {label}', None, address, 'error', duration)

    thread = threading.Thread(target=run_task)
    thread.start()

    return jsonify({'task_id': task_id})


def _run_discovery_analysis(task_id, cancel_flag, address, coin, interval, date_str, lang, user_id, start_time):
    """Discovery mode: find all markets via slug generation, then analyze trader's trades."""
    import requests as req
    import datetime as dt

    cancel_flag['percent'] = 2

    # Phase 1: Discover all markets (0-40%)
    def progress_cb(completed, total):
        if total > 0:
            cancel_flag['percent'] = 2 + int(completed / total * 38)

    events = discover_markets(
        coin=coin,
        interval=interval,
        date_str=date_str,
        progress_callback=progress_cb,
        cancel_flag=cancel_flag,
        max_workers=15,
    )

    if cancel_flag.get('cancelled'):
        tasks[task_id]['status'] = 'cancelled'
        tasks[task_id]['error'] = 'Cancelled' if lang == 'en' else '已取消'
        return

    if not events:
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['error'] = (
            f'No markets found for {coin} {interval} on {date_str}'
            if lang == 'en'
            else f'未找到 {coin} {interval} 在 {date_str} 的市场'
        )
        return

    cancel_flag['percent'] = 40

    # Collect all condition IDs from discovered events
    all_condition_ids = {}  # cid -> event info
    for ev in events:
        for m in ev.get('markets', []):
            cid = m.get('condition_id', '')
            if cid:
                all_condition_ids[cid] = {
                    'event_slug': ev['slug'],
                    'event_title': ev['title'],
                    'time_label': ev.get('time_label', ''),
                    'question': m.get('question', ''),
                    'outcomes': m.get('outcomes', '["Yes", "No"]'),
                    'closed': m.get('closed', False),
                }

    # Phase 2: Fetch trader's activities (40-55%)
    cancel_flag['percent'] = 42
    all_activities = []
    offset = 0
    page_limit = 500
    max_pages = 10

    for page_num in range(max_pages):
        if cancel_flag.get('cancelled'):
            tasks[task_id]['status'] = 'cancelled'
            tasks[task_id]['error'] = 'Cancelled' if lang == 'en' else '已取消'
            return

        try:
            activity_resp = req.get('https://data-api.polymarket.com/activity', params={
                'user': address,
                'limit': page_limit,
                'offset': offset,
            }, timeout=30)

            if activity_resp.status_code != 200:
                break

            batch = activity_resp.json()
            if not isinstance(batch, list) or len(batch) == 0:
                break

            all_activities.extend(batch)
            if len(batch) < page_limit:
                break
            offset += page_limit
        except Exception as e:
            print(f"[Trader Discovery] Activity fetch error page {page_num}: {e}")
            break

        cancel_flag['percent'] = 42 + (page_num + 1) * 1

    cancel_flag['percent'] = 55

    # Get username
    username = ''
    trade_activities = [a for a in all_activities if a.get('type') == 'TRADE']
    if trade_activities:
        username = trade_activities[0].get('name', '') or trade_activities[0].get('pseudonym', '') or ''

    # Group trader's trades by conditionId
    trades_by_cid = {}
    for a in trade_activities:
        cid = a.get('conditionId', '')
        if cid and cid in all_condition_ids:
            if cid not in trades_by_cid:
                trades_by_cid[cid] = []
            trades_by_cid[cid].append(a)

    # Phase 3: Analyze each discovered market (55-95%)
    market_results = []
    total_events = len(events)

    for ev_idx, ev in enumerate(events):
        if cancel_flag.get('cancelled'):
            tasks[task_id]['status'] = 'cancelled'
            tasks[task_id]['error'] = 'Cancelled' if lang == 'en' else '已取消'
            return

        event_title = ev['title']
        time_label = ev.get('time_label', '')
        event_slug = ev['slug']

        # Collect trades across all sub-markets for this event
        event_trades = []
        event_cids = []
        for m in ev.get('markets', []):
            cid = m.get('condition_id', '')
            if cid:
                event_cids.append(cid)
                if cid in trades_by_cid:
                    event_trades.extend(trades_by_cid[cid])

        trade_count = len(event_trades)

        # Compute stats if trader has trades
        buy_cost = 0.0
        sell_revenue = 0.0
        net_exposure = 0.0
        pnl = None
        is_resolved = False
        resolved_side = None
        outcome_0_name = 'Up'
        outcome_1_name = 'Down'
        remaining_0 = 0.0
        remaining_1 = 0.0
        first_time = None
        last_time = None

        if event_trades:
            buy_cost_0 = 0.0
            sell_cost_0 = 0.0
            buy_cost_1 = 0.0
            sell_cost_1 = 0.0
            buy_shares_0 = 0.0
            sell_shares_0 = 0.0
            buy_shares_1 = 0.0
            sell_shares_1 = 0.0
            outcome_names = {}

            for t_item in event_trades:
                side = t_item.get('side', '').upper()
                size = float(t_item.get('size', 0))
                price = float(t_item.get('price', 0))
                cost = size * price
                outcome_idx = int(t_item.get('outcomeIndex', 0))
                outcome_name = t_item.get('outcome', '')
                ts = int(t_item.get('timestamp', 0))

                if outcome_name and outcome_idx not in outcome_names:
                    outcome_names[outcome_idx] = outcome_name

                if first_time is None or ts < first_time:
                    first_time = ts
                if last_time is None or ts > last_time:
                    last_time = ts

                if side == 'BUY':
                    buy_cost += cost
                    if outcome_idx == 0:
                        buy_shares_0 += size
                        buy_cost_0 += cost
                    else:
                        buy_shares_1 += size
                        buy_cost_1 += cost
                elif side == 'SELL':
                    sell_revenue += cost
                    if outcome_idx == 0:
                        sell_shares_0 += size
                        sell_cost_0 += cost
                    else:
                        sell_shares_1 += size
                        sell_cost_1 += cost

            remaining_0 = buy_shares_0 - sell_shares_0
            remaining_1 = buy_shares_1 - sell_shares_1
            net_exposure = (buy_cost_0 - sell_cost_0) + (buy_cost_1 - sell_cost_1)
            outcome_0_name = outcome_names.get(0, 'Up')
            outcome_1_name = outcome_names.get(1, 'Down')

        # Check resolution status via CLOB API (use first condition ID)
        for cid in event_cids:
            try:
                market_resp = req.get(f'https://clob.polymarket.com/markets/{cid}', timeout=5)
                if market_resp.status_code == 200:
                    market_info = market_resp.json()
                    is_resolved = market_info.get('closed', False)
                    if is_resolved and trade_count > 0:
                        tokens = market_info.get('tokens', [])
                        for token in tokens:
                            if token.get('winner', False):
                                resolved_side = token.get('outcome', '')
                                break
                        if resolved_side:
                            if resolved_side.lower() in [outcome_0_name.lower(), 'yes', 'up']:
                                final_value = remaining_0 * 1.0
                            else:
                                final_value = remaining_1 * 1.0
                            pnl = final_value - net_exposure
                    break  # Only need to check one sub-market for resolution
            except Exception:
                pass

        time_range = time_label
        if first_time and last_time:
            t_start = dt.datetime.fromtimestamp(first_time).strftime('%H:%M:%S')
            t_end = dt.datetime.fromtimestamp(last_time).strftime('%H:%M:%S')
            time_range = f'{time_label} ({t_start}-{t_end})'

        market_results.append({
            'condition_id': event_cids[0] if event_cids else '',
            'title': event_title,
            'event_slug': event_slug,
            'time_label': time_label,
            'trade_count': trade_count,
            'buy_cost': round(buy_cost, 2),
            'sell_revenue': round(sell_revenue, 2),
            'net_exposure': round(net_exposure, 2),
            'remaining_0': round(remaining_0, 2),
            'remaining_1': round(remaining_1, 2),
            'outcome_0_name': outcome_0_name,
            'outcome_1_name': outcome_1_name,
            'is_resolved': is_resolved,
            'resolved_side': resolved_side,
            'pnl': round(pnl, 2) if pnl is not None else None,
            'time_range': time_range,
            'traded': trade_count > 0,
        })

        cancel_flag['percent'] = 55 + int((ev_idx + 1) / total_events * 40)

    cancel_flag['percent'] = 95

    # Aggregate stats
    traded_markets = [m for m in market_results if m['traded']]
    total_trades = sum(m['trade_count'] for m in traded_markets)
    total_buy_cost = sum(m['buy_cost'] for m in traded_markets)
    total_sell_revenue = sum(m['sell_revenue'] for m in traded_markets)
    total_net_exposure = sum(m['net_exposure'] for m in traded_markets)

    settled_markets = [m for m in traded_markets if m['is_resolved'] and m['pnl'] is not None]
    unsettled_traded = [m for m in traded_markets if not m['is_resolved'] or m['pnl'] is None]

    total_pnl = sum(m['pnl'] for m in settled_markets) if settled_markets else None
    wins = sum(1 for m in settled_markets if m['pnl'] > 0)
    losses = sum(1 for m in settled_markets if m['pnl'] < 0)
    breakeven = sum(1 for m in settled_markets if m['pnl'] == 0)
    win_rate = (wins / len(settled_markets) * 100) if settled_markets else None

    cycles = 86400 // INTERVALS[interval]['seconds']

    cancel_flag['percent'] = 100
    tasks[task_id]['status'] = 'completed'
    tasks[task_id]['result'] = {
        'mode': 'discovery',
        'summary': {
            'address': address,
            'username': username,
            'market_type': interval,
            'coin': coin,
            'keyword': f'{coin} {interval}',
            'date': date_str,
            'total_cycles': cycles,
            'discovered_markets': len(events),
            'traded_markets': len(traded_markets),
            'total_markets': len(traded_markets),
            'total_trades': total_trades,
            'total_buy_cost': round(total_buy_cost, 2),
            'total_sell_revenue': round(total_sell_revenue, 2),
            'total_net_exposure': round(total_net_exposure, 2),
            'total_pnl': round(total_pnl, 2) if total_pnl is not None else None,
            'settled_count': len(settled_markets),
            'unsettled_count': len(unsettled_traded),
            'wins': wins,
            'losses': losses,
            'breakeven': breakeven,
            'win_rate': round(win_rate, 1) if win_rate is not None else None,
        },
        'markets': market_results,
    }

    duration = round(time.time() - start_time, 1)
    db.record_query(user_id, 'trader', f'Trader: {coin} {interval}', None, address, 'success', duration)


def _run_activity_analysis(task_id, cancel_flag, address, market_type, search_keyword, date_filter, date_str, lang, user_id, start_time):
    """Activity-based analysis: search trader's activities by keyword pattern matching."""
    import requests as req
    import re
    import datetime as dt

    cancel_flag['percent'] = 5

    # Step 1: Fetch user activities with pagination
    all_activities = []
    offset = 0
    page_limit = 500
    max_pages = 10

    for page_num in range(max_pages):
        if cancel_flag.get('cancelled'):
            tasks[task_id]['status'] = 'cancelled'
            tasks[task_id]['error'] = 'Cancelled' if lang == 'en' else '已取消'
            return

        try:
            activity_url = f'https://data-api.polymarket.com/activity'
            activity_resp = req.get(activity_url, params={
                'user': address,
                'limit': page_limit,
                'offset': offset,
            }, timeout=30)

            if activity_resp.status_code != 200:
                break

            batch = activity_resp.json()
            if not isinstance(batch, list) or len(batch) == 0:
                break

            all_activities.extend(batch)
            if len(batch) < page_limit:
                break
            offset += page_limit
        except Exception as e:
            print(f"[Trader] Activity fetch error page {page_num}: {e}")
            break

        cancel_flag['percent'] = 5 + (page_num + 1) * 3

    if not all_activities:
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['error'] = 'No activity found for this address' if lang == 'en' else '未找到该地址的交易活动'
        return

    cancel_flag['percent'] = 30

    # Step 2: Filter activities by type and keyword
    trade_activities = [a for a in all_activities if a.get('type') == 'TRADE']

    type_patterns = {
        '1min': [r'1\s*Minute'],
        '5min': [r'5\s*Minutes?'],
        '15min': [r'15\s*Minutes?'],
        '30min': [r'30\s*Minutes?'],
        'hourly': [r'Hourly', r'Hour'],
        'daily': [r'Up or Down\s*[-–]\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)'],
    }

    if market_type == 'custom':
        patterns = [re.escape(search_keyword)]
    else:
        patterns = type_patterns.get(market_type, [re.escape(search_keyword)])

    compiled_patterns = [re.compile(p, re.IGNORECASE) for p in patterns]

    def matches_type(title):
        if not title:
            return False
        return any(p.search(title) for p in compiled_patterns)

    filtered = [a for a in trade_activities if matches_type(a.get('title', ''))]

    if date_filter:
        day_start = int(date_filter.timestamp())
        day_end = int((date_filter + dt.timedelta(days=1)).timestamp())
        filtered = [a for a in filtered if day_start <= int(a.get('timestamp', 0)) < day_end]

    if not filtered:
        tasks[task_id]['status'] = 'error'
        no_match_msg = (
            f'No trades found matching "{search_keyword}"'
            if lang == 'en'
            else f'未找到匹配 "{search_keyword}" 的交易记录'
        )
        if date_str:
            no_match_msg += f' ({date_str})'
        tasks[task_id]['error'] = no_match_msg
        return

    cancel_flag['percent'] = 40

    # Step 3: Group by conditionId
    markets_data = {}
    for a in filtered:
        cid = a.get('conditionId', '')
        if not cid:
            continue
        if cid not in markets_data:
            markets_data[cid] = {
                'condition_id': cid,
                'title': a.get('title', 'Unknown'),
                'trades': [],
            }
        markets_data[cid]['trades'].append(a)

    cancel_flag['percent'] = 50

    # Step 4: For each market, compute stats
    market_results = []
    total_markets = len(markets_data)

    for idx, (cid, mdata) in enumerate(markets_data.items()):
        if cancel_flag.get('cancelled'):
            tasks[task_id]['status'] = 'cancelled'
            tasks[task_id]['error'] = 'Cancelled' if lang == 'en' else '已取消'
            return

        trades = mdata['trades']
        trades.sort(key=lambda x: int(x.get('timestamp', 0)))

        trade_count = len(trades)
        title = mdata['title']

        buy_cost = 0.0
        sell_revenue = 0.0
        buy_shares_0 = 0.0
        sell_shares_0 = 0.0
        buy_shares_1 = 0.0
        sell_shares_1 = 0.0
        buy_cost_0 = 0.0
        sell_cost_0 = 0.0
        buy_cost_1 = 0.0
        sell_cost_1 = 0.0

        outcome_names = {}
        first_time = None
        last_time = None

        for t_item in trades:
            side = t_item.get('side', '').upper()
            size = float(t_item.get('size', 0))
            price = float(t_item.get('price', 0))
            cost = size * price
            outcome_idx = int(t_item.get('outcomeIndex', 0))
            outcome_name = t_item.get('outcome', '')
            ts = int(t_item.get('timestamp', 0))

            if outcome_name and outcome_idx not in outcome_names:
                outcome_names[outcome_idx] = outcome_name

            if first_time is None or ts < first_time:
                first_time = ts
            if last_time is None or ts > last_time:
                last_time = ts

            if side == 'BUY':
                buy_cost += cost
                if outcome_idx == 0:
                    buy_shares_0 += size
                    buy_cost_0 += cost
                else:
                    buy_shares_1 += size
                    buy_cost_1 += cost
            elif side == 'SELL':
                sell_revenue += cost
                if outcome_idx == 0:
                    sell_shares_0 += size
                    sell_cost_0 += cost
                else:
                    sell_shares_1 += size
                    sell_cost_1 += cost

        remaining_0 = buy_shares_0 - sell_shares_0
        remaining_1 = buy_shares_1 - sell_shares_1
        net_exposure = (buy_cost_0 - sell_cost_0) + (buy_cost_1 - sell_cost_1)

        outcome_0_name = outcome_names.get(0, 'Yes')
        outcome_1_name = outcome_names.get(1, 'No')

        is_resolved = False
        resolved_side = None
        pnl = None

        try:
            market_resp = req.get(f'https://clob.polymarket.com/markets/{cid}', timeout=5)
            if market_resp.status_code == 200:
                market_info = market_resp.json()
                is_resolved = market_info.get('closed', False)
                if is_resolved:
                    tokens = market_info.get('tokens', [])
                    if tokens:
                        for token in tokens:
                            winner = token.get('winner', False)
                            if winner:
                                token_outcome = token.get('outcome', '')
                                resolved_side = token_outcome
                                break

                    if resolved_side:
                        if resolved_side.lower() in [outcome_0_name.lower(), 'yes']:
                            final_value = remaining_0 * 1.0
                        else:
                            final_value = remaining_1 * 1.0
                        pnl = final_value - net_exposure
        except Exception:
            pass

        time_range = ''
        if first_time and last_time:
            t_start = dt.datetime.fromtimestamp(first_time).strftime('%H:%M:%S')
            t_end = dt.datetime.fromtimestamp(last_time).strftime('%H:%M:%S')
            t_date = dt.datetime.fromtimestamp(first_time).strftime('%Y-%m-%d')
            time_range = f'{t_date} {t_start} - {t_end}'

        market_results.append({
            'condition_id': cid,
            'title': title,
            'trade_count': trade_count,
            'buy_cost': round(buy_cost, 2),
            'sell_revenue': round(sell_revenue, 2),
            'net_exposure': round(net_exposure, 2),
            'remaining_0': round(remaining_0, 2),
            'remaining_1': round(remaining_1, 2),
            'outcome_0_name': outcome_0_name,
            'outcome_1_name': outcome_1_name,
            'is_resolved': is_resolved,
            'resolved_side': resolved_side,
            'pnl': round(pnl, 2) if pnl is not None else None,
            'time_range': time_range,
        })

        cancel_flag['percent'] = 50 + int((idx + 1) / total_markets * 40)

    cancel_flag['percent'] = 90

    # Step 5: Aggregate stats
    total_trades = sum(m['trade_count'] for m in market_results)
    total_buy_cost = sum(m['buy_cost'] for m in market_results)
    total_sell_revenue = sum(m['sell_revenue'] for m in market_results)
    total_net_exposure = sum(m['net_exposure'] for m in market_results)

    settled_markets = [m for m in market_results if m['is_resolved'] and m['pnl'] is not None]
    unsettled_markets = [m for m in market_results if not m['is_resolved'] or m['pnl'] is None]

    total_pnl = sum(m['pnl'] for m in settled_markets) if settled_markets else None
    wins = sum(1 for m in settled_markets if m['pnl'] > 0)
    losses = sum(1 for m in settled_markets if m['pnl'] < 0)
    breakeven = sum(1 for m in settled_markets if m['pnl'] == 0)
    win_rate = (wins / len(settled_markets) * 100) if settled_markets else None

    username = ''
    if filtered:
        username = filtered[0].get('name', '') or filtered[0].get('pseudonym', '') or ''

    market_results.sort(key=lambda m: m.get('time_range', ''))

    cancel_flag['percent'] = 100
    tasks[task_id]['status'] = 'completed'
    tasks[task_id]['result'] = {
        'summary': {
            'address': address,
            'username': username,
            'market_type': market_type,
            'keyword': search_keyword,
            'date': date_str or 'All',
            'total_markets': len(market_results),
            'total_trades': total_trades,
            'total_buy_cost': round(total_buy_cost, 2),
            'total_sell_revenue': round(total_sell_revenue, 2),
            'total_net_exposure': round(total_net_exposure, 2),
            'total_pnl': round(total_pnl, 2) if total_pnl is not None else None,
            'settled_count': len(settled_markets),
            'unsettled_count': len(unsettled_markets),
            'wins': wins,
            'losses': losses,
            'breakeven': breakeven,
            'win_rate': round(win_rate, 1) if win_rate is not None else None,
        },
        'markets': market_results,
    }

    duration = round(time.time() - start_time, 1)
    db.record_query(user_id, 'trader', f'Trader: {search_keyword}', None, address, 'success', duration)


@app.route('/api/multi/markets', methods=['POST'])
def get_multi_markets():
    """
    获取 Event 下的所有子市场，并检查用户是否有持仓或交易
    请求体: {"url": "event URL", "address": "钱包地址"}
    返回: {"event_title": "事件标题", "markets": [...]}
    
    v2.0 更新: 增加链上持仓查询，解决 Neg-Risk Convert 持仓无法显示的问题
    v2.1 更新: 增加链上事件查询，返回 Split/Merge/Redeem 统计
    v3.28 更新: 链上事件查询拆分到 /api/multi/chain-events，本接口不再查询链上事件
    """
    import re
    import requests as req
    
    # 导入链上查询函数
    try:
        from neg_risk import get_user_market_positions, get_user_chain_events
        HAS_ONCHAIN_QUERY = True
    except ImportError:
        HAS_ONCHAIN_QUERY = False
    
    data = request.get_json()
    event_url = data.get('url', '').strip()
    address = data.get('address', '').strip()
    
    if not event_url:
        return jsonify({'error': '请输入市场 URL'}), 400
    if not address or not address.startswith('0x') or len(address) != 42:
        return jsonify({'error': '请输入有效的钱包地址'}), 400
    
    # 从 URL 提取 event slug
    match = re.search(r'polymarket\.com/event/([^/\?]+)', event_url)
    if not match:
        return jsonify({'error': '无效的 Polymarket URL，请输入事件页面的链接'}), 400
    
    event_slug = match.group(1)
    
    try:
        # 通过 slug 获取 event 信息
        event_resp = req.get(f'https://gamma-api.polymarket.com/events?slug={event_slug}', timeout=15)
        event_resp.raise_for_status()
        events = event_resp.json()
        
        if not events:
            return jsonify({'error': '未找到该事件'}), 404
        
        event = events[0]
        event_title = event.get('title', '未知事件')
        markets = event.get('markets', [])
        
        if not markets:
            return jsonify({'error': '该事件下没有子市场'}), 404
        
        # 先获取用户所有活动（包括 neg-risk 交易）
        user_activities = []
        try:
            activity_resp = req.get(f'https://data-api.polymarket.com/activity?user={address}&limit=500', timeout=30)
            if activity_resp.status_code == 200:
                user_activities = activity_resp.json() if isinstance(activity_resp.json(), list) else []
        except:
            pass
        
        # 按 conditionId 建立活动索引
        activity_by_condition = {}
        for a in user_activities:
            cid = a.get('conditionId', '')
            if cid and a.get('type') == 'TRADE':
                if cid not in activity_by_condition:
                    activity_by_condition[cid] = []
                activity_by_condition[cid].append(a)
        
        # 检查每个市场
        result_markets = []
        for market in markets:
            condition_id = market.get('conditionId', '')
            question = market.get('question', market.get('groupItemTitle', '未知'))
            
            trade_count = 0
            yes_shares = 0.0
            no_shares = 0.0
            has_position = False
            
            # 方法1: 检查 activity API 结果
            if condition_id in activity_by_condition:
                trade_count = len(activity_by_condition[condition_id])
            
            # 方法2: 如果 activity 没有，尝试 trades API
            if trade_count == 0:
                try:
                    trades_resp = req.get('https://data-api.polymarket.com/trades', params={
                        'market': condition_id,
                        'user': address,
                        'limit': 1
                    }, timeout=10)
                    
                    trades = trades_resp.json() if trades_resp.status_code == 200 else []
                    trade_count = len(trades) if isinstance(trades, list) else 0
                    
                    if trade_count > 0:
                        count_resp = req.get('https://data-api.polymarket.com/trades', params={
                            'market': condition_id,
                            'user': address,
                            'limit': 500
                        }, timeout=15)
                        all_trades = count_resp.json() if count_resp.status_code == 200 else []
                        trade_count = len(all_trades) if isinstance(all_trades, list) else 0
                except:
                    pass
            
            # 方法3 (v2.0 新增): 查询链上持仓余额
            # 即使没有交易记录，也可能通过 Convert 获得持仓
            if HAS_ONCHAIN_QUERY:
                try:
                    positions = get_user_market_positions(address, condition_id)
                    yes_shares = positions.get('yes', 0.0)
                    no_shares = positions.get('no', 0.0)
                    has_position = yes_shares > 0 or no_shares > 0
                except Exception as e:
                    print(f"[链上查询] 查询 {condition_id[:20]}... 失败: {e}")
            
            # 只要有交易记录或有持仓，就显示该市场
            if trade_count > 0 or has_position:
                market_slug = market.get('slug', '')
                result_markets.append({
                    'question': question,
                    'condition_id': condition_id,
                    'trade_count': trade_count,
                    'is_resolved': market.get('closed', False),
                    'outcomes': market.get('outcomes', '["Yes", "No"]'),
                    'slug': market_slug,
                    'yes_shares': yes_shares,
                    'no_shares': no_shares,
                    'has_position': has_position,
                })
        
        # v3.28: 链上事件查询已拆分到 /api/multi/chain-events
        # 这里只返回子市场列表，不再查询链上事件
        
        return jsonify({
            'event_title': event_title,
            'event_slug': event_slug,
            'markets': result_markets,
        })
        
    except Exception as e:
        return jsonify({'error': f'获取市场信息失败: {str(e)}'}), 500


@app.route('/api/multi/chain-events', methods=['POST'])
def get_multi_chain_events():
    """
    v3.28 新增: 异步查询链上事件
    请求体: {"url": "event URL", "address": "钱包地址"}
    返回: {"chain_events": {...}, "extra_markets": [...]}
    """
    import re
    import requests as req
    
    # 导入链上查询函数
    try:
        from neg_risk import get_user_market_positions, get_user_chain_events
        HAS_ONCHAIN_QUERY = True
    except ImportError:
        return jsonify({'error': '链上查询模块不可用'}), 500
    
    data = request.get_json()
    event_url = data.get('url', '').strip()
    address = data.get('address', '').strip()
    
    if not event_url or not address:
        return jsonify({'error': '缺少必要参数'}), 400
    
    # 从 URL 提取 event slug
    match = re.search(r'polymarket\.com/event/([^/\?]+)', event_url)
    if not match:
        return jsonify({'error': '无效的 URL'}), 400
    
    event_slug = match.group(1)
    
    try:
        # 获取 event 的子市场列表（用于 condition_id 映射）
        event_resp = req.get(f'https://gamma-api.polymarket.com/events?slug={event_slug}', timeout=15)
        event_resp.raise_for_status()
        events = event_resp.json()
        
        if not events:
            return jsonify({'error': '未找到该事件'}), 404
        
        markets = events[0].get('markets', [])
        
        # 构建 condition_id -> market_name 映射
        cid_to_market_name = {}
        cid_to_market_info = {}  # 额外保存完整市场信息
        for m in markets:
            m_cid = m.get('conditionId', '').lower()
            m_question = m.get('question', m.get('groupItemTitle', ''))
            # 提取简短名称（如温度范围）
            if m_question:
                import re as re_module
                temp_match = re_module.search(r'(\d+-\d+|≤?\d+|≥?\d+)\s*°?F?', m_question)
                if temp_match:
                    cid_to_market_name[m_cid] = temp_match.group(1) + '°F'
                else:
                    cid_to_market_name[m_cid] = m_question[:30] + ('...' if len(m_question) > 30 else '')
            cid_to_market_info[m_cid] = m
        
        # 查询链上事件
        chain_events_summary = {
            'split': 0,
            'merge': 0,
            'redeem': 0,
            'convert': 0,
            'events': []
        }
        
        chain_event_conditions = {}  # condition_id -> {'split': n, 'merge': n, ...}
        
        chain_events = get_user_chain_events(address)
        for e in chain_events:
            event_type = e.get('type', '')
            event_cid = e.get('details', {}).get('condition_id', '')
            event_cid_lower = event_cid.lower() if event_cid else ''
            
            # 只统计属于当前 Event 的链上操作
            if event_cid_lower not in cid_to_market_name:
                continue
            
            if event_type in chain_events_summary:
                chain_events_summary[event_type] += 1
            
            if event_cid:
                event_cid_norm = event_cid_lower
                if event_cid_norm not in chain_event_conditions:
                    chain_event_conditions[event_cid_norm] = {'split': 0, 'merge': 0, 'redeem': 0, 'convert': 0}
                if event_type in chain_event_conditions[event_cid_norm]:
                    chain_event_conditions[event_cid_norm][event_type] += 1
            
            # 保存事件详情（最多50个）
            if len(chain_events_summary['events']) < 50:
                market_name = cid_to_market_name.get(event_cid_lower, '')
                chain_events_summary['events'].append({
                    'type': event_type,
                    'tx_hash': e.get('tx_hash', ''),
                    'amount': e.get('details', {}).get('amount', 0),
                    'description': e.get('details', {}).get('description', ''),
                    'timestamp': e.get('timestamp', 0),
                    'condition_id': event_cid,
                    'market_name': market_name,
                })
        
        # 返回有链上操作但可能没有交易记录的市场（供前端补充显示）
        extra_markets = []
        for market_cid, chain_ops in chain_event_conditions.items():
            total_ops = sum(chain_ops.values())
            if total_ops > 0 and market_cid in cid_to_market_info:
                m_info = cid_to_market_info[market_cid]
                # 查询持仓
                yes_shares = 0.0
                no_shares = 0.0
                has_position = False
                try:
                    positions = get_user_market_positions(address, market_cid)
                    yes_shares = positions.get('yes', 0.0)
                    no_shares = positions.get('no', 0.0)
                    has_position = yes_shares > 0 or no_shares > 0
                except:
                    pass
                
                extra_markets.append({
                    'question': m_info.get('question', m_info.get('groupItemTitle', '未知')),
                    'condition_id': m_info.get('conditionId', ''),
                    'trade_count': 0,
                    'is_resolved': m_info.get('closed', False),
                    'outcomes': m_info.get('outcomes', '["Yes", "No"]'),
                    'slug': m_info.get('slug', ''),
                    'yes_shares': yes_shares,
                    'no_shares': no_shares,
                    'has_position': has_position,
                    'chain_ops': chain_ops,
                })
        
        return jsonify({
            'chain_events': chain_events_summary,
            'extra_markets': extra_markets,
        })
        
    except Exception as e:
        return jsonify({'error': f'查询链上事件失败: {str(e)}'}), 500


@app.route('/api/multi/analyze', methods=['POST'])
def multi_analyze():
    """
    分析指定子市场
    请求体: {"condition_id": "xxx", "address": "钱包地址", "market_title": "市场标题", "is_resolved": bool, "outcomes": "json_str", "event_slug": "xxx"}
    返回: {"task_id": "任务ID"}
    """
    data = request.get_json()
    condition_id = data.get('condition_id', '').strip()
    address = data.get('address', '').strip()
    market_title = data.get('market_title', '未知市场')
    is_resolved = data.get('is_resolved', False)
    outcomes = data.get('outcomes', '["Yes", "No"]')
    lang = data.get('lang', 'zh')  # 默认中文
    event_slug = data.get('event_slug', '')  # 新增：用于来源分析
    
    if not condition_id:
        error_msg = 'Missing condition_id' if lang == 'en' else '缺少 condition_id'
        return jsonify({'error': error_msg}), 400
    if not address or not address.startswith('0x') or len(address) != 42:
        error_msg = 'Please enter a valid wallet address' if lang == 'en' else '请输入有效的钱包地址'
        return jsonify({'error': error_msg}), 400
    
    # 生成任务ID
    task_id = str(uuid.uuid4())[:8]
    
    # 创建任务目录
    task_dir = os.path.join(STATIC_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    
    # 初始化任务状态
    cancel_flag = {'cancelled': False, 'percent': 0}
    tasks[task_id] = {
        'status': 'running',
        'percent': 0,
        'cancel_flag': cancel_flag,
        'market': market_title,
        'address': address,
        'result': None,
        'error': None
    }
    
    # 获取用户ID和市场URL用于统计
    user_id = get_or_create_user_id()
    market_url = data.get('market_url', None)  # 前端传入完整URL
    start_time = time.time()
    
    # 在后台线程执行分析
    def run_task():
        try:
            from script import run_analysis_by_condition_id
            
            chart_file, report_file, trades_file, error = run_analysis_by_condition_id(
                condition_id=condition_id,
                user_address=address,
                market_title=market_title,
                resolved_arg='AUTO',
                output_dir=task_dir,
                cancel_flag=cancel_flag,
                is_resolved=is_resolved,
                outcomes_str=outcomes,
                lang=lang,
                event_slug=event_slug  # 新增：用于来源分析
            )
            
            duration = round(time.time() - start_time, 1)
            
            if cancel_flag.get('cancelled'):
                tasks[task_id]['status'] = 'cancelled'
                tasks[task_id]['error'] = '查询已取消'
                db.record_query(user_id, 'multi', market_title, market_url, address, 'cancelled', duration)
                return
            
            if error:
                tasks[task_id]['status'] = 'error'
                tasks[task_id]['error'] = error
                db.record_query(user_id, 'multi', market_title, market_url, address, 'error', duration)
                return
            
            # 读取报告内容
            report_content = ''
            if report_file and os.path.exists(report_file):
                with open(report_file, 'r', encoding='utf-8') as f:
                    report_content = f.read()
            
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['result'] = {
                'chart': os.path.basename(chart_file) if chart_file else None,
                'report': os.path.basename(report_file) if report_file else None,
                'trades': os.path.basename(trades_file) if trades_file else None,
                'report_content': report_content
            }
            
            db.record_query(user_id, 'multi', market_title, market_url, address, 'success', duration)
            
        except Exception as e:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = str(e)
            db.record_query(user_id, 'multi', market_title, market_url, address, 'error', None)
    
    thread = threading.Thread(target=run_task)
    thread.start()
    
    return jsonify({'task_id': task_id})


@app.route('/api/query', methods=['POST'])
def query():
    """
    开始查询
    请求体: {"market": "市场名称", "address": "钱包地址", "lang": "zh/en"}
    返回: {"task_id": "任务ID"}
    """
    import requests as req
    
    data = request.get_json()
    market = data.get('market', '').strip()
    address = data.get('address', '').strip()
    lang = data.get('lang', 'zh')  # 默认中文
    
    if not market:
        error_msg = 'Please enter market name' if lang == 'en' else '请输入市场名称'
        return jsonify({'error': error_msg}), 400
    if not address or not address.startswith('0x') or len(address) != 42:
        error_msg = 'Please enter a valid wallet address (0x...)' if lang == 'en' else '请输入有效的钱包地址 (0x...)'
        return jsonify({'error': error_msg}), 400
    
    # 预先搜索市场获取 URL（用于统计）
    market_url = None
    try:
        search_resp = req.get('https://gamma-api.polymarket.com/public-search', params={'q': market}, timeout=10)
        if search_resp.status_code == 200:
            search_data = search_resp.json()
            events = search_data.get('events', [])
            if events:
                event = events[0]
                event_slug = event.get('slug', '')
                if event_slug:
                    market_url = f'https://polymarket.com/event/{event_slug}'
    except Exception as e:
        print(f"[统计] 获取市场URL失败: {e}")  # 打印错误便于调试
    
    # 生成任务ID
    task_id = str(uuid.uuid4())[:8]
    
    # 创建任务目录
    task_dir = os.path.join(STATIC_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    
    # 初始化任务状态
    cancel_flag = {'cancelled': False, 'percent': 0}
    tasks[task_id] = {
        'status': 'running',
        'percent': 0,
        'cancel_flag': cancel_flag,
        'market': market,
        'address': address,
        'result': None,
        'error': None
    }
    
    # 获取用户ID用于统计
    user_id = get_or_create_user_id()
    start_time = time.time()
    
    # 在后台线程执行查询
    def run_task():
        try:
            chart_file, report_file, trades_file, error = run_analysis(
                market_query=market,
                user_address=address,
                resolved_arg='AUTO',
                output_dir=task_dir,
                cancel_flag=cancel_flag,
                lang=lang
            )
            
            duration = round(time.time() - start_time, 1)
            
            if cancel_flag.get('cancelled'):
                tasks[task_id]['status'] = 'cancelled'
                tasks[task_id]['error'] = 'Query cancelled' if lang == 'en' else '查询已取消'
                db.record_query(user_id, 'simple', market, market_url, address, 'cancelled', duration)
                return
            
            if error:
                tasks[task_id]['status'] = 'error'
                tasks[task_id]['error'] = error
                db.record_query(user_id, 'simple', market, market_url, address, 'error', duration)
                return
            
            # 读取报告内容
            report_content = ''
            if report_file and os.path.exists(report_file):
                with open(report_file, 'r', encoding='utf-8') as f:
                    report_content = f.read()
            
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['result'] = {
                'chart': os.path.basename(chart_file) if chart_file else None,
                'report': os.path.basename(report_file) if report_file else None,
                'trades': os.path.basename(trades_file) if trades_file else None,
                'report_content': report_content
            }
            
            # 记录成功查询
            db.record_query(user_id, 'simple', market, market_url, address, 'success', duration)
            
        except Exception as e:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = str(e)
            db.record_query(user_id, 'simple', market, market_url, address, 'error', None)
    
    thread = threading.Thread(target=run_task)
    thread.start()
    
    return jsonify({'task_id': task_id})


@app.route('/api/status/<task_id>')
def status(task_id):
    """
    查询任务状态
    返回: {"status": "running/completed/error/cancelled", "percent": 0-100, ...}
    """
    if task_id not in tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    task = tasks[task_id]
    cancel_flag = task.get('cancel_flag', {})
    
    response = {
        'status': task['status'],
        'percent': cancel_flag.get('percent', 0),
        'market': task['market'],
        'address': task['address']
    }
    
    if task['status'] == 'completed':
        response['result'] = task['result']
    elif task['status'] == 'error':
        response['error'] = task['error']
    elif task['status'] == 'cancelled':
        response['error'] = task['error']
    
    return jsonify(response)


@app.route('/api/cancel/<task_id>', methods=['POST'])
def cancel(task_id):
    """取消查询任务"""
    if task_id not in tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    task = tasks[task_id]
    if task['status'] == 'running':
        cancel_flag = task.get('cancel_flag', {})
        cancel_flag['cancelled'] = True
        return jsonify({'message': '已发送取消请求'})
    
    return jsonify({'message': '任务已结束，无法取消'})


@app.route('/static/<task_id>/<filename>')
def serve_file(task_id, filename):
    """提供生成的文件下载"""
    task_dir = os.path.join(STATIC_DIR, task_id)
    return send_from_directory(task_dir, filename)


@app.route('/assets/<filename>')
def serve_assets(filename):
    """提供永久静态资源"""
    return send_from_directory(ASSETS_DIR, filename)


@app.route('/api/cleanup/<task_id>', methods=['POST'])
def cleanup(task_id):
    """清理任务文件"""
    if task_id in tasks:
        del tasks[task_id]
    
    task_dir = os.path.join(STATIC_DIR, task_id)
    if os.path.exists(task_dir):
        shutil.rmtree(task_dir)
    
    return jsonify({'message': '已清理'})


# ===== 后台统计页面 =====

@app.route(f'/{ADMIN_PATH}')
def admin_panel():
    """后台统计页面"""
    return render_template('admin.html')


@app.route(f'/{ADMIN_PATH}/api/stats')
def admin_stats():
    """获取统计数据"""
    stats = db.get_all_stats()
    return jsonify(stats)


@app.route(f'/{ADMIN_PATH}/api/queries')
def admin_queries():
    """获取查询记录（分页）"""
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    offset = (page - 1) * limit
    
    queries = db.get_recent_queries(limit=limit, offset=offset)
    total = db.get_total_queries()
    
    return jsonify({
        'queries': queries,
        'total': total,
        'page': page,
        'limit': limit,
        'total_pages': (total + limit - 1) // limit
    })


if __name__ == '__main__':
    print('=' * 50)
    print('Polymarket 交易分析 Web 应用')
    print('访问 http://127.0.0.1:5000 开始使用')
    print(f'后台统计: http://127.0.0.1:5000/{ADMIN_PATH}')
    print('=' * 50)
    app.run(debug=True, host='127.0.0.1', port=5000)
