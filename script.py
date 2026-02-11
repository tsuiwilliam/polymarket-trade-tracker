import os
import sys
import json
import datetime
import re
import time
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import matplotlib.patheffects as pe
import matplotlib.ticker as ticker

# Neg-Risk 模块导入
try:
    from neg_risk import (
        extract_event_slug_from_url,
        enrich_trades_batch,
        records_to_legacy_format,
    )
    NEG_RISK_MODULE_AVAILABLE = True
except ImportError:
    NEG_RISK_MODULE_AVAILABLE = False
    print("[WARNING] neg_risk 模块未找到，来源分析功能不可用")

# ---------------------------------------------------
# 中文字体配置
# ---------------------------------------------------
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['mathtext.fontset'] = 'custom'
plt.rcParams['mathtext.rm'] = 'Microsoft YaHei'
plt.rcParams['mathtext.it'] = 'Microsoft YaHei'
plt.rcParams['mathtext.bf'] = 'Microsoft YaHei'

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------
STYLES = {
    ("Buy", "Up"):   ("#008f00", "x", "买入 YES"),   # strong green
    ("Sell", "Up"):  ("#00c800", "o", "卖出 YES"),   # vivid lime
    ("Buy", "Down"): ("#d000d0", "x", "买入 NO"),    # strong magenta
    ("Sell", "Down"):("#d40000", "o", "卖出 NO")     # strong red
}

# ---------------------------------------------------
# 国际化文本配置
# ---------------------------------------------------
I18N_TEXTS = {
    'zh': {
        # 报告文本
        'wallet_address': '钱包地址',
        'username': '用户名',
        'market': '市场',
        'market_status': '市场状态',
        'settled': '已结算',
        'unsettled': '未结算',
        'settlement_direction': '结算方向',
        'trade_count': '交易次数',
        'time_range': '时间范围',
        'price_range': '价格范围',
        'to': '至',
        'settlement_position': '结算时持仓',
        'current_position': '当前持仓',
        'remaining_shares': '剩余 {name} 份额',
        'final_value': '最终价值',
        'total_spent': '总支出 (净敞口)',
        'final_pnl': '最终盈亏',
        'buy_sell_summary': '买入/卖出汇总',
        'buy': '买入',
        'sell': '卖出',
        'shares': '份',
        'cumulative_buy': '累计买入',
        'cumulative': '累计',
        'exposure_peak': '敞口峰值 (交易序号: 从早到晚)',
        'dollar_peak': '美元峰值',
        'share_peak': '份额峰值',
        'at_trade': '于第 {n} 笔交易',
        'final_exposure': '最终敞口',
        'exposure': '敞口',
        'net_exposure': '净敞口',
        'maker_taker_stats': 'Maker/Taker 统计',
        'maker_filled': 'MAKER (挂单成交)',
        'taker_filled': 'TAKER (吃单成交)',
        'unknown': 'UNKNOWN (未知)',
        'trades': '笔',
        'trade_records': '交易记录 (按时间排序)',
        'header_seq': '序号',
        'header_time': '时间',
        'header_type': '类型',
        'header_direction': '方向',
        'header_price': '价格(分)',
        'header_shares': '份额',
        'header_cost': '成本($)',
        'header_role': '角色',
        # 图表文本
        'chart_title': '{market} 交易记录',
        'price_cents': '价格 (美分)',
        'cumulative_buy_chart': '累计买入 (份额 + 美元)',
        'cumulative_buy_shares': '累计买入量 (份)',
        'cumulative_buy_cost': '累计买入成本 ($)',
        'dollar_exposure': '美元敞口',
        'share_exposure': '份额敞口',
        'exposure_dollar': '敞口 ($)',
        'exposure_share': '份额',
        'peak': '峰值',
        'dollar_peak_chart': '{name} 峰值 $',
        'share_peak_chart': '{name} 峰值',
        'buy_volume': '买入 {name} 量',
        'settlement_result': '市场结算: {name}',
        'unsettled_status': '市场状态: 未结算',
        # 错误消息
        'no_market_found': '未找到匹配的市场',
        'no_trades': '该用户在此市场没有交易记录',
        'parse_failed': '解析交易失败',
        'cancelled': '用户已中断当前查询',
        # 交易来源统计
        'source_stats': '持仓变动来源统计',
        'source_direct': 'Direct (直接交易)',
        'source_neg_risk': 'Neg-Risk (转换)',
        'source_split': 'Split (拆分)',
        'source_merge': 'Merge (合并)',
        'source_transfer': 'Transfer (转账)',
        'source_redeem': 'Redeem (赎回)',
        'source_unknown': 'Unknown (未知)',
        'header_source': '来源',
    },
    'en': {
        # Report text
        'wallet_address': 'Wallet Address',
        'username': 'Username',
        'market': 'Market',
        'market_status': 'Market Status',
        'settled': 'Settled',
        'unsettled': 'Unsettled',
        'settlement_direction': 'Settlement',
        'trade_count': 'Trade Count',
        'time_range': 'Time Range',
        'price_range': 'Price Range',
        'to': 'to',
        'settlement_position': 'Position at Settlement',
        'current_position': 'Current Position',
        'remaining_shares': 'Remaining {name} Shares',
        'final_value': 'Final Value',
        'total_spent': 'Total Spent (Net Exposure)',
        'final_pnl': 'Final P&L',
        'buy_sell_summary': 'Buy/Sell Summary',
        'buy': 'Buy',
        'sell': 'Sell',
        'shares': 'sh',
        'cumulative_buy': 'Cumulative Buy',
        'cumulative': 'Cumulative',
        'exposure_peak': 'Exposure Peak (Trade #: chronological)',
        'dollar_peak': 'Dollar Peak',
        'share_peak': 'Share Peak',
        'at_trade': 'at Trade #{n}',
        'final_exposure': 'Final Exposure',
        'exposure': 'Exposure',
        'net_exposure': 'Net Exposure',
        'maker_taker_stats': 'Maker/Taker Stats',
        'maker_filled': 'MAKER (Limit Order)',
        'taker_filled': 'TAKER (Market Order)',
        'unknown': 'UNKNOWN',
        'trades': 'trades',
        'trade_records': 'Trade Records (Chronological)',
        'header_seq': '#',
        'header_time': 'Time',
        'header_type': 'Type',
        'header_direction': 'Side',
        'header_price': 'Price(¢)',
        'header_shares': 'Shares',
        'header_cost': 'Cost($)',
        'header_role': 'Role',
        # Chart text
        'chart_title': '{market} Trade Records',
        'price_cents': 'Price (Cents)',
        'cumulative_buy_chart': 'Cumulative Buy (Shares + $)',
        'cumulative_buy_shares': 'Cumulative Buy (Shares)',
        'cumulative_buy_cost': 'Cumulative Buy Cost ($)',
        'dollar_exposure': 'Dollar Exposure',
        'share_exposure': 'Share Exposure',
        'exposure_dollar': 'Exposure ($)',
        'exposure_share': 'Shares',
        'peak': 'Peak',
        'dollar_peak_chart': '{name} Peak $',
        'share_peak_chart': '{name} Peak',
        'buy_volume': 'Buy {name} Vol',
        'settlement_result': 'Settlement: {name}',
        'unsettled_status': 'Status: Unsettled',
        # Error messages
        'no_market_found': 'No matching market found',
        'no_trades': 'No trades found for this user in this market',
        'parse_failed': 'Failed to parse trades',
        'cancelled': 'Query cancelled by user',
        # Trade source stats
        'source_stats': 'Position Change Source Stats',
        'source_direct': 'Direct Trade',
        'source_neg_risk': 'Neg-Risk (Conversion)',
        'source_split': 'Split',
        'source_merge': 'Merge',
        'source_transfer': 'Transfer',
        'source_redeem': 'Redeem',
        'source_unknown': 'Unknown',
        'header_source': 'Source',
    }
}

def get_text(key, lang='zh', **kwargs):
    """获取国际化文本"""
    text = I18N_TEXTS.get(lang, I18N_TEXTS['zh']).get(key, key)
    # 替换参数
    for k, v in kwargs.items():
        text = text.replace('{' + k + '}', str(v))
    return text

SEARCH_URL = "https://gamma-api.polymarket.com/public-search"
TRADES_URL = "https://data-api.polymarket.com/trades"
PRICE_RESOLUTION_THRESHOLD = 0.5

# CTF Exchange 合约地址 (需要排除)
CTF_EXCHANGE_ADDRESSES = {
    "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E".lower(),  # 旧版 Binary
    "0xC5d563A36AE78145C45a50134d48A1215220f80a".lower(),  # 新版 Multi-outcome
}

# OrderFilled 事件签名
ORDER_FILLED_TOPIC = "0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6"

# Polygon RPC (env configurable, default: public endpoint)
POLYGON_RPC_URL = os.environ.get('POLY_RPC_URL', 'https://polygon-rpc.com')


def get_maker_taker_role(tx_hash, user_address):
    """
    通过链上 OrderFilled 事件判断用户是 maker 还是 taker
    返回: "MAKER", "TAKER", 或 "UNKNOWN"
    """
    if not tx_hash or not user_address:
        return "UNKNOWN"
    
    user_addr_lower = user_address.lower()
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionReceipt",
            "params": [tx_hash],
            "id": 1
        }
        resp = requests.post(POLYGON_RPC_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        result = data.get("result")
        if result is None:
            return "UNKNOWN"
        
        logs = result.get("logs", [])
        
        for log in logs:
            topics = log.get("topics", [])
            if not topics or topics[0].lower() != ORDER_FILLED_TOPIC.lower():
                continue
            
            # OrderFilled 事件: topics[1]=orderHash, topics[2]=maker, topics[3]=taker
            if len(topics) < 4:
                continue
            
            # 解析 maker 和 taker 地址 (去掉前导0)
            maker_raw = topics[2]
            taker_raw = topics[3]
            
            # 地址格式: 0x000000000000000000000000{address}
            maker = "0x" + maker_raw[-40:].lower()
            taker = "0x" + taker_raw[-40:].lower()
            
            # 排除 CTF Exchange 作为对手方的事件
            if maker in CTF_EXCHANGE_ADDRESSES or taker in CTF_EXCHANGE_ADDRESSES:
                continue
            
            # 判断用户角色
            if taker == user_addr_lower:
                return "TAKER"
            if maker == user_addr_lower:
                return "MAKER"
        
        return "UNKNOWN"
        
    except Exception as e:
        print(f"查询链上事件失败 ({tx_hash[:10]}...): {e}")
        return "UNKNOWN"


class CancelledError(Exception):
    """查询被用户取消"""
    pass


def batch_get_maker_taker_roles(trades, user_address, cancel_flag=None):
    """
    批量获取所有交易的 maker/taker 角色 (使用 JSON-RPC batch 请求)
    trades: 交易列表，每个交易需要有 transactionHash 字段
    cancel_flag: 可选的取消标志字典 {"cancelled": bool}
    返回: {tx_hash: role} 字典
    """
    roles = {}
    user_addr_lower = user_address.lower()

    # 收集唯一的 tx_hash
    unique_hashes = list(set(t.get("transactionHash") for t in trades if t.get("transactionHash")))

    if not unique_hashes:
        return roles

    print(f"正在批量查询 {len(unique_hashes)} 笔交易的 maker/taker 角色...")

    # eth_getTransactionReceipt = 15 CU each
    # Alchemy free tier: 500 CU/s → target 90% = 450 CU/s = 30 receipts/s
    # batch_size=15 @ 0.5s delay = 30/s = 450 CU/s
    batch_size = 15
    batch_delay = 0.5  # seconds between batches

    for batch_start in range(0, len(unique_hashes), batch_size):
        # 检查是否取消
        if cancel_flag:
            if cancel_flag.get("cancelled"):
                raise CancelledError("用户已中断当前查询")
            # 更新进度百分比 (Maker/Taker 查询阶段占 20%-80%)
            progress = batch_start * 60 // len(unique_hashes)  # 0-60
            cancel_flag["percent"] = 20 + progress  # 20-80

        batch_hashes = unique_hashes[batch_start:batch_start + batch_size]

        # 构建批量请求
        batch_payload = [
            {
                "jsonrpc": "2.0",
                "method": "eth_getTransactionReceipt",
                "params": [tx_hash],
                "id": i
            }
            for i, tx_hash in enumerate(batch_hashes)
        ]

        try:
            # 带重试的请求 (with exponential backoff on 429)
            results = None
            for retry in range(4):
                resp = requests.post(POLYGON_RPC_URL, json=batch_payload, timeout=30)

                # Handle 429 rate limit with exponential backoff
                if resp.status_code == 429:
                    wait = 2 ** (retry + 1)  # 2s, 4s, 8s, 16s
                    print(f"  RPC rate limited (429), waiting {wait}s...")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                results = resp.json()

                # 检查返回是否为有效的 list
                if isinstance(results, list) and len(results) == len(batch_hashes):
                    break

                # 返回异常，等待后重试
                time.sleep(batch_delay)

            if results is None:
                raise ValueError("RPC 请求全部被限流 (429)")

            if not isinstance(results, list):
                raise ValueError(f"RPC 返回格式错误: {type(results)}")

            # 构建 id -> tx_hash 映射
            id_to_hash = {i: tx_hash for i, tx_hash in enumerate(batch_hashes)}

            # 处理每个响应 (使用 id 匹配，因为响应顺序可能不同)
            for result in results:
                rid = result.get("id")
                tx_hash = id_to_hash.get(rid)
                if tx_hash is None:
                    continue
                receipt = result.get("result")

                if receipt is None:
                    roles[tx_hash] = "UNKNOWN"
                    continue

                role = "UNKNOWN"
                logs = receipt.get("logs", [])

                for log in logs:
                    topics = log.get("topics", [])
                    if not topics or topics[0].lower() != ORDER_FILLED_TOPIC.lower():
                        continue
                    if len(topics) < 4:
                        continue

                    maker = "0x" + topics[2][-40:].lower()
                    taker = "0x" + topics[3][-40:].lower()

                    if maker in CTF_EXCHANGE_ADDRESSES or taker in CTF_EXCHANGE_ADDRESSES:
                        continue

                    if taker == user_addr_lower:
                        role = "TAKER"
                        break
                    if maker == user_addr_lower:
                        role = "MAKER"
                        break

                roles[tx_hash] = role

        except Exception as e:
            print(f"批量查询失败: {e}")
            # 失败的批次全部标记为 UNKNOWN
            for tx_hash in batch_hashes:
                if tx_hash not in roles:
                    roles[tx_hash] = "UNKNOWN"

        # 显示进度
        done = min(batch_start + batch_size, len(unique_hashes))
        print(f"  进度: {done}/{len(unique_hashes)} ({done * 100 // len(unique_hashes)}%)")

        # Rate-limit between batches to stay under Alchemy CU/s limit
        if batch_start + batch_size < len(unique_hashes):
            time.sleep(batch_delay)

    return roles


def generate_safe_filename(market_title, user_address):
    """生成安全的文件名前缀"""
    safe_title = re.sub(r'[<>:"/\\|?*]', '', market_title)
    safe_title = safe_title.replace(' ', '_')[:50]
    short_addr = user_address[:8] if user_address else "unknown"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{safe_title}_{short_addr}_{timestamp}"

# ---------------------------------------------------
# REPORT GENERATION
# ---------------------------------------------------
def write_stats_report(
    report_path,
    target_market,
    resolved_side,
    trade_count,
    remaining_yes,
    remaining_no,
    final_value,
    total_spent,
    pnl,
    yes_buy_sh,
    yes_buy_cost,
    yes_sell_sh,
    yes_sell_cost,
    no_buy_sh,
    no_buy_cost,
    no_sell_sh,
    no_sell_cost,
    cum_yes_total,
    cum_no_total,
    cum_yes_cost_total,
    cum_no_cost_total,
    yes_curve,
    no_curve,
    net_curve,
    yes_sh_curve,
    no_sh_curve,
    net_sh_curve,
    prices,
    trades,
    user_address="",
    username="",
    outcome_0_name="Up",
    outcome_1_name="Down",
    is_resolved=True,
    lang='zh',
    source_stats=None,  # 新增: 交易来源统计 {'direct': n, 'neg_risk': n, ...}
):
    # Safety checks for empty data
    if len(yes_curve) > 0:
        yes_peak_idx = int(np.argmax(yes_curve))
        no_peak_idx = int(np.argmax(no_curve))
        yes_sh_peak_idx = int(np.argmax(yes_sh_curve))
        no_sh_peak_idx = int(np.argmax(no_sh_curve))
        
        yes_peak_val = yes_curve[yes_peak_idx]
        no_peak_val = no_curve[no_peak_idx]
        yes_sh_peak_val = yes_sh_curve[yes_sh_peak_idx]
        no_sh_peak_val = no_sh_curve[no_sh_peak_idx]
        
        final_yes_exp = yes_curve[-1]
        final_yes_sh = yes_sh_curve[-1]
        final_no_exp = no_curve[-1]
        final_no_sh = no_sh_curve[-1]
        final_net_exp = net_curve[-1]
        final_net_sh = net_sh_curve[-1]
    else:
        yes_peak_idx = no_peak_idx = 0
        yes_sh_peak_idx = no_sh_peak_idx = 0
        yes_peak_val = no_peak_val = 0
        yes_sh_peak_val = no_sh_peak_val = 0
        final_yes_exp = final_yes_sh = 0
        final_no_exp = final_no_sh = 0
        final_net_exp = final_net_sh = 0

    # Calculate time range
    start_time = "N/A"
    end_time = "N/A"
    if trades:
        start_time = datetime.datetime.fromtimestamp(trades[0]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        end_time = datetime.datetime.fromtimestamp(trades[-1]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
    
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0

    # 结算方向对应的 outcome 名称
    resolved_outcome = outcome_0_name if resolved_side == "YES" else outcome_1_name
    
    lines = [
        f"{get_text('wallet_address', lang)}: {user_address}",
        f"{get_text('username', lang)}: {username}",
        "",
        f"{get_text('market', lang)}: {target_market}",
    ]
    
    if is_resolved:
        lines.extend([
            f"{get_text('market_status', lang)}: {get_text('settled', lang)}",
            f"{get_text('settlement_direction', lang)}: {resolved_outcome}",
        ])
    else:
        lines.append(f"{get_text('market_status', lang)}: {get_text('unsettled', lang)}")
    
    lines.extend([
        f"{get_text('trade_count', lang)}: {trade_count}",
        f"{get_text('time_range', lang)}: {start_time} {get_text('to', lang)} {end_time}",
        f"{get_text('price_range', lang)}: {min_price:.2f} - {max_price:.2f}",
        "",
    ])
    
    if is_resolved:
        lines.extend([
            f"--- {get_text('settlement_position', lang)} ---",
            f"{get_text('remaining_shares', lang, name=outcome_0_name)}: {remaining_yes:.2f}",
            f"{get_text('remaining_shares', lang, name=outcome_1_name)}:  {remaining_no:.2f}",
            f"{get_text('final_value', lang)}: $ {final_value:.2f}",
            f"{get_text('total_spent', lang)}: $ {total_spent:.2f}",
            f"{get_text('final_pnl', lang)}: $ {pnl:.2f}",
            "",
        ])
    else:
        lines.extend([
            f"--- {get_text('current_position', lang)} ---",
            f"{get_text('remaining_shares', lang, name=outcome_0_name)}: {remaining_yes:.2f}",
            f"{get_text('remaining_shares', lang, name=outcome_1_name)}:  {remaining_no:.2f}",
            f"{get_text('total_spent', lang)}: $ {total_spent:.2f}",
            "",
        ])
    
    sh = get_text('shares', lang)
    lines.extend([
        f"--- {get_text('buy_sell_summary', lang)} ---",
        f"{outcome_0_name} {get_text('buy', lang)}:  {yes_buy_sh:.2f} {sh} / $ {yes_buy_cost:.2f}",
        f"{outcome_0_name} {get_text('sell', lang)}:  {yes_sell_sh:.2f} {sh} / $ {yes_sell_cost:.2f}",
        f"{outcome_1_name} {get_text('buy', lang)}:   {no_buy_sh:.2f} {sh} / $ {no_buy_cost:.2f}",
        f"{outcome_1_name} {get_text('sell', lang)}:   {no_sell_sh:.2f} {sh} / $ {no_sell_cost:.2f}",
        "",
        f"--- {get_text('cumulative_buy', lang)} ---",
        f"{outcome_0_name} {get_text('cumulative', lang)}: {cum_yes_total:.2f} {sh} / $ {cum_yes_cost_total:.2f}",
        f"{outcome_1_name} {get_text('cumulative', lang)}:  {cum_no_total:.2f} {sh} / $ {cum_no_cost_total:.2f}",
        "",
        f"--- {get_text('exposure_peak', lang)} ---",
        f"{outcome_0_name} {get_text('dollar_peak', lang)}: $ {yes_peak_val:.2f} {get_text('at_trade', lang, n=yes_peak_idx + 1)}",
        f"{outcome_1_name} {get_text('dollar_peak', lang)}:  $ {no_peak_val:.2f} {get_text('at_trade', lang, n=no_peak_idx + 1)}",
        f"{outcome_0_name} {get_text('share_peak', lang)}: {yes_sh_peak_val:.2f} {sh} {get_text('at_trade', lang, n=yes_sh_peak_idx + 1)}",
        f"{outcome_1_name} {get_text('share_peak', lang)}:  {no_sh_peak_val:.2f} {sh} {get_text('at_trade', lang, n=no_sh_peak_idx + 1)}",
        "",
        f"--- {get_text('final_exposure', lang)} ---",
        f"{outcome_0_name} {get_text('exposure', lang)}: $ {final_yes_exp:.2f} | {final_yes_sh:.2f} {sh}",
        f"{outcome_1_name} {get_text('exposure', lang)}:  $ {final_no_exp:.2f} | {final_no_sh:.2f} {sh}",
        f"{get_text('net_exposure', lang)}:   $ {final_net_exp:.2f} | {final_net_sh:.2f} {sh}",
    ])

    # 交易来源统计 (Step 4: 新增)
    if source_stats:
        lines.append("")
        lines.append(f"--- {get_text('source_stats', lang)} ---")
        source_labels = {
            'direct': 'source_direct',
            'neg_risk': 'source_neg_risk',
            'split': 'source_split',
            'merge': 'source_merge',
            'transfer': 'source_transfer',
            'redeem': 'source_redeem',
            'unknown': 'source_unknown',
        }
        trd = get_text('trades', lang)
        for src, count in source_stats.items():
            if count > 0:
                label = get_text(source_labels.get(src, 'source_unknown'), lang)
                lines.append(f"{label}: {count} {trd}")

    # 统计 maker/taker 数量
    maker_count = sum(1 for t in trades if t.get('maker_taker') == 'MAKER')
    taker_count = sum(1 for t in trades if t.get('maker_taker') == 'TAKER')
    unknown_count = sum(1 for t in trades if t.get('maker_taker') == 'UNKNOWN')
    trd = get_text('trades', lang)
    
    lines.append("")
    lines.append(f"--- {get_text('maker_taker_stats', lang)} ---")
    lines.append(f"{get_text('maker_filled', lang)}: {maker_count} {trd}")
    lines.append(f"{get_text('taker_filled', lang)}: {taker_count} {trd}")
    if unknown_count > 0:
        lines.append(f"{get_text('unknown', lang)}:   {unknown_count} {trd}")

    lines.append("")
    record_title = "持仓变动记录" if lang == 'zh' else "Position Change Records"
    lines.append(f"--- {record_title} ---")
    
    # 根据是否有来源数据决定表头格式
    has_source = source_stats and any(v > 0 for v in source_stats.values() if v)
    
    # 新表头格式: 序号 | 时间 | 来源 | 方向 | 份额 | 成本 | 备注
    if has_source:
        header_src = get_text('header_source', lang)
        header_dir = "方向" if lang == 'zh' else "Direction"
        header_note = "备注" if lang == 'zh' else "Note"
        lines.append(f"{get_text('header_seq', lang)} | {get_text('header_time', lang)}                | {header_src:<8} | {header_dir:<14} | {get_text('header_shares', lang):>8} | {get_text('header_cost', lang):>10} | {header_note}")
        lines.append("-----+---------------------+----------+----------------+----------+------------+---------------------------")
    else:
        lines.append(f"{get_text('header_seq', lang)} | {get_text('header_time', lang)}                | {get_text('header_type', lang)} | {get_text('header_direction', lang)} | {get_text('header_price', lang)} |   {get_text('header_shares', lang)}     |   {get_text('header_cost', lang)}  | {get_text('header_role', lang)}")
        lines.append("-----+---------------------+------+------+----------+------------+------------+--------")

    # 收集需要显示详情的交易
    neg_risk_details = []
    
    for i, t in enumerate(trades):
        dt_str = datetime.datetime.fromtimestamp(t['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        role = t.get('maker_taker', 'UNKNOWN')
        source = t.get('source', 'Trade')
        record_type = t.get('record_type', 'trade')  # v3.26: 记录类型
        
        if has_source:
            # 生成方向列 (v3.26: 支持链上事件)
            if record_type == 'split':
                direction = "+Yes +No"
            elif record_type == 'merge':
                direction = "-Yes -No"
            elif record_type == 'redeem':
                direction = "-Position"
            elif source == 'transfer':
                direction = f"+{t['side']}"
            else:
                direction = f"{t['type']} {t['side']}"
            
            # 生成成本列 (v3.26: Split 显示负数，Merge/Redeem 显示正数)
            if record_type in ['merge', 'redeem']:
                cost_str = f"+$ {abs(t['cost']):8.2f}"
            elif record_type == 'split':
                cost_str = f"-$ {abs(t['cost']):8.2f}"
            elif source == 'transfer':
                cost_str = "         -"
            else:
                cost_str = f" $ {t['cost']:8.2f}"
            
            # 生成备注列 (v3.26: 支持链上事件)
            if record_type == 'split':
                note = t.get('description', '') or ("拆分 USDC" if lang == 'zh' else "Split USDC")
            elif record_type == 'merge':
                note = t.get('description', '') or ("合并回收" if lang == 'zh' else "Merge to USDC")
            elif record_type == 'redeem':
                note = t.get('description', '') or ("结算赎回" if lang == 'zh' else "Settlement redeem")
            elif source == 'Trade':
                note = role
            elif source == 'neg_risk':
                num_sources = len(t.get('source_trades', []))
                if num_sources > 0:
                    note_text = "从{}个子市场转换" if lang == 'zh' else "from {} sub-markets"
                    note = note_text.format(num_sources)
                    # 收集 Neg-Risk 详情
                    neg_risk_details.append({
                        'seq': i + 1,
                        'time': dt_str,
                        'side': t['side'],
                        'shares': t['shares'],
                        'source_trades': t.get('source_trades', []),
                        'conversion_cost': t.get('conversion_cost', 0),
                        'usdc_returned': t.get('usdc_returned', 0),
                        'net_cost': t.get('net_cost', 0)
                    })
                else:
                    note = "Neg-Risk" if lang == 'en' else "对冲转换"
            elif source == 'transfer':
                counterparty = t.get('counterparty', '')
                if counterparty:
                    short_addr = f"{counterparty[:6]}...{counterparty[-4:]}"
                    note_text = "从 {} 收到" if lang == 'zh' else "from {}"
                    note = note_text.format(short_addr)
                else:
                    note = "Transfer" if lang == 'en' else "转账"
            else:
                note = "-"
            
            lines.append(
                f"{i+1:3d} | {dt_str} | {source:<8} | {direction:<14} | {t['shares']:8.2f} | {cost_str} | {note}"
            )
        else:
            lines.append(
                f"{i+1:3d} | {dt_str} | {t['type']:<4} | {t['side']:<4} | "
                f"{t['price']:8.2f} | {t['shares']:10.2f} | $ {t['cost']:9.2f} | {role}"
            )
    
    # 输出 Neg-Risk 转换明细
    if neg_risk_details:
        lines.append("")
        detail_title = "Neg-Risk 转换明细" if lang == 'zh' else "Neg-Risk Conversion Details"
        lines.append(f"--- {detail_title} ---")
        
        for nrd in neg_risk_details:
            obtain_text = "获得" if lang == 'zh' else "Obtained"
            lines.append(f"#{nrd['seq']} | {nrd['time']} | {obtain_text} {nrd['side']} {nrd['shares']:.2f} 份")
            
            if nrd['source_trades']:
                src_text = "    源交易:" if lang == 'zh' else "    Source trades:"
                lines.append(src_text)
                for st in nrd['source_trades']:
                    market_short = st['market_name'][:30] + "..." if len(st['market_name']) > 30 else st['market_name']
                    lines.append(f"    - [{market_short}] {st['outcome']} {st['shares']:.0f}份 @ {st['price']*100:.1f}¢ = ${st['cost']:.2f}")
                
                conv_text = "    转换:" if lang == 'zh' else "    Conversion:"
                lines.append(f"{conv_text} ${nrd['conversion_cost']:.2f} → ${nrd['usdc_returned']:.2f} USDC + {nrd['shares']:.0f}份")
                
                net_text = "    净成本:" if lang == 'zh' else "    Net cost:"
                price_per_share = (nrd['net_cost'] / nrd['shares'] * 100) if nrd['shares'] > 0 else 0
                lines.append(f"{net_text} ${nrd['net_cost']:.2f} ({price_per_share:.1f}¢/份)")
            lines.append("")

    # Use UTF-8 so Unicode symbols (e.g. arrows) are preserved on Windows
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------
# DATA FETCHING
# ---------------------------------------------------
def search_market(query):
    """Return (event, market) for the first matching search result."""
    try:
        resp = requests.get(SEARCH_URL, params={"q": query}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        print(f"搜索市场错误: {exc}")
        return None, None

    events = data.get("events", []) if isinstance(data, dict) else []
    for event in events:
        markets = event.get("markets") or []
        if markets:
            return event, markets[0]
    return None, None


def fetch_trades(condition_id, user_address, page_limit=500):
    """Fetch all trades for a condition/user with simple pagination."""
    all_trades = []
    offset = 0

    while True:
        params = {
            "limit": page_limit,
            "offset": offset,
            "takerOnly": "false",
            "market": condition_id,
            "user": user_address,
        }
        try:
            resp = requests.get(TRADES_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            print(f"获取交易错误: {exc}")
            return []

        if isinstance(data, dict):
            batch = data.get("trades", [])
        elif isinstance(data, list):
            batch = data
        else:
            batch = []

        all_trades.extend(batch)
        if len(batch) < page_limit:
            break
        offset += page_limit

    return all_trades


def fetch_activities(condition_id, user_address, limit=500):
    """
    使用 activity API 获取用户活动（包括 neg-risk 交易）
    返回格式与 fetch_trades 兼容
    """
    try:
        url = f"https://data-api.polymarket.com/activity?user={user_address}&limit={limit}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        activities = resp.json()
    except requests.RequestException as exc:
        print(f"获取活动错误: {exc}")
        return []
    
    if not isinstance(activities, list):
        return []
    
    # 过滤目标市场的 TRADE 类型活动
    trades = []
    for a in activities:
        if a.get("conditionId") == condition_id and a.get("type") == "TRADE":
            # 转换为 trades API 兼容的格式
            trade = {
                "transactionHash": a.get("transactionHash"),
                "timestamp": a.get("timestamp"),
                "side": a.get("side", "").upper(),  # BUY/SELL
                "size": a.get("size"),
                "price": a.get("price"),
                "outcome": a.get("outcome"),
                "outcomeIndex": a.get("outcomeIndex", 0),
                "title": a.get("title"),
                "name": a.get("name"),
                "pseudonym": a.get("pseudonym"),
                "asset": a.get("asset"),
                "usdcSize": a.get("usdcSize"),
            }
            trades.append(trade)
    
    return trades


def fetch_trades_with_fallback(condition_id, user_address):
    """
    先用 trades API，如果没有结果则尝试 activity API
    这样可以兼容直接交易和 neg-risk 交易
    """
    # 先尝试 trades API
    trades = fetch_trades(condition_id, user_address)
    
    if trades:
        return trades, "trades"
    
    # 如果没有结果，尝试 activity API
    activities = fetch_activities(condition_id, user_address)
    
    if activities:
        return activities, "activity"
    
    return [], None


def normalize_resolved_arg(value):
    if not value:
        return None
    value = value.strip().upper()
    if value in {"YES", "NO", "AUTO"}:
        return value
    return None


def infer_resolved_side_from_trades(trades, threshold=PRICE_RESOLUTION_THRESHOLD):
    """Infer resolved side from the most recent trade price."""
    if not trades:
        return None, None
    latest = max(trades, key=lambda t: t.get("timestamp", 0))
    price = float(latest.get("price", 0))
    outcome = latest.get("outcome", "").lower()

    if outcome not in {"up", "down"}:
        return None, latest

    # If price >= threshold, assume resolved toward that outcome; otherwise opposite.
    if price >= threshold:
        inferred = "YES" if outcome == "up" else "NO"
    else:
        inferred = "NO" if outcome == "up" else "YES"
    return inferred, latest


def run_analysis(market_query, user_address, resolved_arg="AUTO", output_dir=None, cancel_flag=None, lang='zh'):
    """
    供外部调用的分析函数
    
    参数:
        market_query: 市场名称搜索词
        user_address: 用户钱包地址
        resolved_arg: 结算方向 (YES/NO/AUTO)
        output_dir: 输出目录，默认为当前目录
        cancel_flag: 可选的取消标志字典 {"cancelled": bool}
        lang: 语言 ('zh' 或 'en')，默认中文
    
    返回:
        成功: (chart_file, report_file, trades_file, None) 三个文件路径
        失败: (None, None, None, error) 错误信息
        取消: (None, None, None, "CANCELLED") 用户取消
    """
    import os
    
    # 检查是否取消
    if cancel_flag and cancel_flag.get("cancelled"):
        return None, None, None, "CANCELLED"
    
    # 更新进度: 搜索市场
    if cancel_flag:
        cancel_flag["percent"] = 5
    
    # 搜索市场
    event, market = search_market(market_query)
    if not market:
        return None, None, None, get_text('no_market_found', lang)
    
    market_title = (
        market.get("question")
        or market.get("title")
        or event.get("title", "未知市场")
    )
    condition_id = market.get("conditionId") or ""
    
    # 获取 event_slug 用于 neg-risk 来源分析
    event_slug = event.get("slug", "") if event else ""
    
    # 从 market 数据获取 outcomes 名称和结算状态
    market_outcomes = []
    outcomes_str = market.get("outcomes", "[]")
    try:
        market_outcomes = json.loads(outcomes_str) if isinstance(outcomes_str, str) else outcomes_str
    except:
        market_outcomes = []
    
    # 结算状态: closed=true 表示已结算
    is_resolved = market.get("closed", False)
    
    # 更新进度: 获取交易数据
    if cancel_flag:
        cancel_flag["percent"] = 10
    
    # 获取交易（先尝试 trades API，失败则用 activity API）
    raw_data, data_source = fetch_trades_with_fallback(condition_id, user_address)
    if not raw_data:
        return None, None, None, get_text('no_trades', lang)
    
    if data_source == "activity":
        print(f"[INFO] 使用 activity API 获取数据（neg-risk 交易）")
    
    # 生成文件名前缀
    file_prefix = generate_safe_filename(market_title, user_address)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        file_prefix = os.path.join(output_dir, file_prefix)
    
    # 保存原始交易数据
    trades_file = f"{file_prefix}_trades.json"
    with open(trades_file, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=2, ensure_ascii=False)
    
    # 排序
    raw_data.sort(key=lambda x: x.get("timestamp", 0))
    
    # 获取 maker/taker 角色
    maker_taker_roles = {}
    if user_address:
        try:
            maker_taker_roles = batch_get_maker_taker_roles(raw_data, user_address, cancel_flag)
        except CancelledError:
            return None, None, None, "CANCELLED"
    
    # 检查是否取消
    if cancel_flag and cancel_flag.get("cancelled"):
        return None, None, None, "CANCELLED"
    
    # 更新进度: 解析交易数据
    if cancel_flag:
        cancel_flag["percent"] = 85
    
    # 解析交易
    parsed = []
    target_market = market_title or raw_data[0].get("title", "未知市场")
    username = raw_data[0].get("name", "") or raw_data[0].get("pseudonym", "") or "未知"
    
    # 从 market 数据获取 outcome 名称（优先），交易数据作为备选
    if len(market_outcomes) >= 2:
        outcome_0_name = market_outcomes[0]
        outcome_1_name = market_outcomes[1]
    else:
        # 备选：从交易数据提取
        outcome_names = {}
        for item in raw_data:
            outcome = item.get("outcome", "")
            outcome_idx = item.get("outcomeIndex", 0)
            if outcome and outcome_idx not in outcome_names:
                outcome_names[outcome_idx] = outcome
        outcome_0_name = outcome_names.get(0, "Up")
        outcome_1_name = outcome_names.get(1, "Down")
    
    # 决定结算方向
    resolved_side = None
    resolved_arg = normalize_resolved_arg(resolved_arg)
    if resolved_arg in {"YES", "NO"}:
        resolved_side = resolved_arg
    else:
        inferred, latest = infer_resolved_side_from_trades(raw_data)
        if inferred:
            resolved_side = inferred
        else:
            resolved_side = "YES"  # 默认
    
    # 结算方向对应的 outcome 名称
    resolved_outcome = outcome_0_name if resolved_side == "YES" else outcome_1_name
    
    for item in raw_data:
        entry = {}
        raw_side = item.get("side", "BUY").upper()
        entry["type"] = "Buy" if raw_side == "BUY" else "Sell"
        entry["market"] = item.get("title", "")
        entry["side"] = item.get("outcome", outcome_0_name)
        entry["outcomeIndex"] = item.get("outcomeIndex", 0)
        entry["price"] = float(item.get("price", 0)) * 100.0
        entry["shares"] = float(item.get("size", 0))
        entry["cost"] = float(item.get("price", 0)) * entry["shares"]
        entry["timestamp"] = int(item.get("timestamp", 0))
        tx_hash = item.get("transactionHash", "")
        entry["maker_taker"] = maker_taker_roles.get(tx_hash, "UNKNOWN")
        entry["tx_hash"] = tx_hash
        entry["source"] = "direct"  # 默认来源
        parsed.append(entry)
    
    if not parsed:
        return None, None, trades_file, "解析交易失败"
    
    # 交易来源分析（如果 neg_risk 模块可用）
    source_stats = None
    if NEG_RISK_MODULE_AVAILABLE and event_slug:
        try:
            enriched_records, source_stats = enrich_trades_batch(
                raw_data, user_address, condition_id, event_slug
            )
            # 将来源信息添加到 parsed 中
            for i, record in enumerate(enriched_records):
                if i < len(parsed):
                    parsed[i]['source'] = record.source
                    if record.counterparty:
                        parsed[i]['counterparty'] = record.counterparty
                    # Neg-Risk 详情
                    if record.source_trades:
                        parsed[i]['source_trades'] = [
                            {'market_name': st.market_name, 'outcome': st.outcome, 
                             'shares': st.shares, 'price': st.price, 'cost': st.cost}
                            for st in record.source_trades
                        ]
                        parsed[i]['conversion_cost'] = record.conversion_cost
                        parsed[i]['usdc_returned'] = record.usdc_returned
                        parsed[i]['net_cost'] = record.net_cost
        except Exception as e:
            print(f"[WARNING] 来源分析失败: {e}")
            source_stats = None
    
    prices = [e["price"] for e in parsed]
    
    # 计算敞口曲线
    yes_curve, no_curve, net_curve = [], [], []
    yes_sh_curve, no_sh_curve, net_sh_curve = [], [], []
    yes_exp = no_exp = 0
    yes_sh_exp = no_sh_exp = 0
    
    for e in parsed:
        is_outcome_0 = (e.get("outcomeIndex", 0) == 0)
        if is_outcome_0:
            yes_exp += e["cost"] if e["type"] == "Buy" else -e["cost"]
            yes_sh_exp += e["shares"] if e["type"] == "Buy" else -e["shares"]
        else:
            no_exp += e["cost"] if e["type"] == "Buy" else -e["cost"]
            no_sh_exp += e["shares"] if e["type"] == "Buy" else -e["shares"]
        
        yes_curve.append(yes_exp)
        no_curve.append(no_exp)
        net_curve.append(yes_exp + no_exp)
        yes_sh_curve.append(yes_sh_exp)
        no_sh_curve.append(no_sh_exp)
        net_sh_curve.append(yes_sh_exp + no_sh_exp)
    
    # 计算统计数据
    remaining_yes = yes_sh_curve[-1]
    remaining_no = no_sh_curve[-1]
    total_spent = net_curve[-1]
    
    # 盈亏计算：只有已结算市场才计算
    if is_resolved:
        if resolved_side == "YES":
            final_value = remaining_yes * 1.0
        else:
            final_value = remaining_no * 1.0
        pnl = final_value - total_spent
    else:
        # 未结算：不计算盈亏
        final_value = None
        pnl = None
        resolved_outcome = None  # 未结算，无结算方向
    
    # 计算买卖统计
    yes_buy_sh = yes_buy_cost = yes_sell_sh = yes_sell_cost = 0
    no_buy_sh = no_buy_cost = no_sell_sh = no_sell_cost = 0
    raw_vol_yes, raw_vol_no = [], []
    raw_cost_yes, raw_cost_no = [], []
    
    for e in parsed:
        is_outcome_0 = (e.get("outcomeIndex", 0) == 0)
        is_buy = (e["type"] == "Buy")
        
        if is_buy:
            if is_outcome_0:
                yes_buy_sh += e["shares"]
                yes_buy_cost += e["cost"]
                raw_vol_yes.append(e["shares"])
                raw_vol_no.append(0)
                raw_cost_yes.append(e["cost"])
                raw_cost_no.append(0)
            else:
                no_buy_sh += e["shares"]
                no_buy_cost += e["cost"]
                raw_vol_yes.append(0)
                raw_vol_no.append(e["shares"])
                raw_cost_yes.append(0)
                raw_cost_no.append(e["cost"])
        else:
            raw_vol_yes.append(0)
            raw_vol_no.append(0)
            raw_cost_yes.append(0)
            raw_cost_no.append(0)
            if is_outcome_0:
                yes_sell_sh += e["shares"]
                yes_sell_cost += e["cost"]
            else:
                no_sell_sh += e["shares"]
                no_sell_cost += e["cost"]
    
    cum_yes = np.cumsum(raw_vol_yes)
    cum_no = np.cumsum(raw_vol_no)
    cum_yes_cost = np.cumsum(raw_cost_yes)
    cum_no_cost = np.cumsum(raw_cost_no)
    
    cum_yes_total = cum_yes[-1] if len(cum_yes) > 0 else 0
    cum_no_total = cum_no[-1] if len(cum_no) > 0 else 0
    cum_yes_cost_total = cum_yes_cost[-1] if len(cum_yes_cost) > 0 else 0
    cum_no_cost_total = cum_no_cost[-1] if len(cum_no_cost) > 0 else 0
    
    # 更新进度: 生成图表
    if cancel_flag:
        cancel_flag["percent"] = 90
    
    # ===== 生成图表 =====
    unique_timestamps = sorted(list(set(t['timestamp'] for t in parsed)))
    ts_map = {ts: i for i, ts in enumerate(unique_timestamps)}
    x_indices = [ts_map[e['timestamp']] for e in parsed]
    
    if is_resolved:
        pnl_text = (
            f"{get_text('settlement_result', lang, name=resolved_outcome)}\n\n"
            f"{get_text('remaining_shares', lang, name=outcome_0_name)}: {remaining_yes:.2f}\n"
            f"{get_text('remaining_shares', lang, name=outcome_1_name)}:  {remaining_no:.2f}\n\n"
            f"{get_text('final_value', lang)}: $ {final_value:.2f}\n"
            f"{get_text('total_spent', lang)}: $ {total_spent:.2f}\n\n"
            f"{get_text('final_pnl', lang)}: $ {pnl:.2f}"
        )
    else:
        pnl_text = (
            f"{get_text('unsettled_status', lang)}\n\n"
            f"{get_text('remaining_shares', lang, name=outcome_0_name)}: {remaining_yes:.2f}\n"
            f"{get_text('remaining_shares', lang, name=outcome_1_name)}:  {remaining_no:.2f}\n\n"
            f"{get_text('total_spent', lang)}: $ {total_spent:.2f}"
        )
    
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(
        4, 1, figsize=(16, 14.5),
        gridspec_kw={'height_ratios': [3, 1.3, 1.1, 1.1]}
    )
    fig.subplots_adjust(hspace=0.45, bottom=0.2)
    
    # 图表绑制代码（与原 main() 相同）
    grouped_trades = {}
    for i, e in enumerate(parsed):
        x_idx = ts_map[e['timestamp']]
        if x_idx not in grouped_trades:
            grouped_trades[x_idx] = []
        grouped_trades[x_idx].append(e)
    
    next_up = True
    for x_idx in sorted(grouped_trades.keys()):
        group = grouped_trades[x_idx]
        avg_price = sum(t["price"] for t in group) / len(group)
        
        if len(group) == 1:
            e = group[0]
            style_key = (e["type"], e["side"])
            if style_key in STYLES:
                color, marker, label = STYLES[style_key]
            else:
                color, marker, label = ("gray", "o", "Unknown")
            
            ax1.scatter(x_idx, e["price"], color=color, marker=marker,
                        s=60, linewidths=2.5 if marker=="x" else 1.0,
                        alpha=0.9, zorder=5)
            
            direction = 1 if next_up else -1
            next_up = not next_up
            candle_len = 15 * 0.7
            end_y = e["price"] + direction * candle_len
            
            ax1.vlines(x_idx, e["price"], end_y, colors=color, linewidth=1.5, alpha=0.6)
            
            role = e.get('maker_taker', 'UNKNOWN')
            role_short = "M" if role == "MAKER" else ("T" if role == "TAKER" else "?")
            label_text = f"{e['shares']:.2f}份\n${e['cost']:.2f}\n[{role_short}]"
            
            ax1.annotate(
                label_text,
                xy=(x_idx, end_y),
                xytext=(0, direction * 2),
                textcoords="offset points",
                ha="center", va="bottom" if direction > 0 else "top",
                fontsize=7,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7, ec="none")
            )
        else:
            count = len(group)
            first_e = group[0]
            same_side = all((t["type"] == first_e["type"] and t["side"] == first_e["side"]) for t in group)
            
            if same_side:
                style_key = (first_e["type"], first_e["side"])
                color, _, _ = STYLES.get(style_key, ("gray", "o", ""))
            else:
                color = "#1f77b4"
            
            ax1.scatter(x_idx, avg_price, color="white", marker="o", s=300, edgecolors=color, linewidth=2, zorder=5)
            ax1.text(x_idx, avg_price, str(count), ha="center", va="center", fontsize=9, fontweight="bold", color=color, zorder=6)
            
            direction = 1 if next_up else -1
            next_up = not next_up
            
            info_lines = []
            for idx, t in enumerate(group):
                if idx < 5:
                    role = t.get('maker_taker', 'UNKNOWN')
                    role_short = "M" if role == "MAKER" else ("T" if role == "TAKER" else "?")
                    info_lines.append(f"{t['shares']:.2f}份 ${t['cost']:.2f} ({t['side']}) [{role_short}]")
                else:
                    remaining = len(group) - 5
                    info_lines.append(f"...还有 {remaining} 笔")
                    break
            
            box_text = "\n".join(info_lines)
            raw_len = 25 + (len(info_lines) * 5)
            candle_len = raw_len * 0.7
            end_y = avg_price + direction * candle_len
            
            ax1.vlines(x_idx, avg_price, end_y, colors=color, linewidth=2, alpha=0.6, linestyles="dotted")
            ax1.annotate(
                box_text,
                xy=(x_idx, end_y),
                xytext=(0, direction * 2),
                textcoords="offset points",
                ha="center", va="bottom" if direction > 0 else "top",
                fontsize=6,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.85, ec=color)
            )
    
    ax1.set_title(get_text('chart_title', lang, market=target_market))
    ax1.set_ylabel(get_text('price_cents', lang))
    
    def time_formatter(x, pos):
        idx = int(x)
        if 0 <= idx < len(unique_timestamps):
            ts = unique_timestamps[idx]
            return datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S')
        return ""
    
    ax1.xaxis.set_major_locator(ticker.MaxNLocator(nbins=12))
    ax1.xaxis.set_major_formatter(ticker.FuncFormatter(time_formatter))
    ax1.set_yticks(range(0, 101, 10))
    ax1.grid(axis='y', linestyle='--', alpha=0.3)
    
    vol_yes_per_ts = [0.0] * len(unique_timestamps)
    vol_no_per_ts = [0.0] * len(unique_timestamps)
    for x_idx, group in grouped_trades.items():
        for t in group:
            if t["type"] == "Buy":
                if t.get("outcomeIndex", 0) == 0:
                    vol_yes_per_ts[x_idx] += t["shares"]
                else:
                    vol_no_per_ts[x_idx] += t["shares"]
    
    x_range = np.arange(len(unique_timestamps))
    vol_ax = ax1.inset_axes([0, 0.0, 1.0, 0.2], sharex=ax1)
    vol_ax.patch.set_alpha(0)
    vol_ax.bar(x_range - 0.35/2, vol_yes_per_ts, width=0.35, color="green", alpha=0.18, label=get_text('buy_volume', lang, name=outcome_0_name))
    vol_ax.bar(x_range + 0.35/2, vol_no_per_ts, width=0.35, color="red", alpha=0.18, label=get_text('buy_volume', lang, name=outcome_1_name))
    vol_ax.set_yticks([])
    vol_ax.set_xticks([])
    vol_ax.set_xlim(-0.5, len(unique_timestamps) - 0.5)
    
    # 第二图：累计买入
    lbl_cum = get_text('cumulative', lang)
    lbl_sh = get_text('shares', lang)
    ax2.plot(x_indices, cum_yes, color="green", alpha=0.3, linewidth=1, label=f"{lbl_cum} {outcome_0_name} ({lbl_sh})")
    ax2.fill_between(x_indices, cum_yes, color="green", alpha=0.1)
    ax2.plot(x_indices, cum_no, color="red", alpha=0.3, linewidth=1, label=f"{lbl_cum} {outcome_1_name} ({lbl_sh})")
    ax2.fill_between(x_indices, cum_no, color="red", alpha=0.1)
    ax2.set_ylabel(get_text('cumulative_buy_shares', lang))
    ax2.grid(axis='y', alpha=0.2)
    ax2.set_xticks([])
    ax2.set_title(get_text('cumulative_buy_chart', lang))
    max_cum = max(cum_yes.max() if len(cum_yes) else 0, cum_no.max() if len(cum_no) else 0)
    ax2.set_ylim(0, max_cum * 1.15 + 1e-6)
    
    ax2_cost = ax2.twinx()
    ax2_cost.plot(x_indices, cum_yes_cost, color="green", linewidth=1.8, linestyle="--", alpha=0.7, label=f"{lbl_cum} {outcome_0_name} ($)")
    ax2_cost.plot(x_indices, cum_no_cost, color="red", linewidth=1.8, linestyle="--", alpha=0.7, label=f"{lbl_cum} {outcome_1_name} ($)")
    ax2_cost.set_ylabel(get_text('cumulative_buy_cost', lang), color="gray", fontsize=9)
    ax2_cost.tick_params(axis='y', labelsize=8, colors="gray")
    ax2_cost.spines['right'].set_alpha(0.3)
    handles2, labels2 = ax2_cost.get_legend_handles_labels()
    handles1, labels1 = ax2.get_legend_handles_labels()
    ax2.legend(handles1 + handles2, labels1 + labels2, loc="upper left")
    
    cum_stats_text = f"{outcome_0_name}: {cum_yes_total:.2f} {lbl_sh} / $ {cum_yes_cost_total:.2f}\n{outcome_1_name}:  {cum_no_total:.2f} {lbl_sh} / $ {cum_no_cost_total:.2f}"
    ax2.text(0.01, 0.02, cum_stats_text, transform=ax2.transAxes, ha="left", va="bottom", fontsize=9,
             bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8, ec="gray"))
    
    # 第三图：美元敞口
    lbl_exp = get_text('exposure', lang)
    lbl_net = get_text('net_exposure', lang)
    lbl_peak = get_text('peak', lang)
    ax3.grid(alpha=0.3)
    ax3.plot(x_indices, yes_curve, color="green", linewidth=2, label=f"{outcome_0_name} {lbl_exp} ($)")
    ax3.plot(x_indices, no_curve, color="red", linewidth=2, label=f"{outcome_1_name} {lbl_exp} ($)")
    ax3.plot(x_indices, net_curve, color="blue", linewidth=2, label=f"{lbl_net} ($)")
    
    if len(yes_curve) > 0:
        yes_peak = int(np.argmax(yes_curve))
        no_peak = int(np.argmax(no_curve))
        ax3.annotate(get_text('dollar_peak_chart', lang, name=outcome_0_name), (x_indices[yes_peak], yes_curve[yes_peak]), xytext=(0, -20),
                     textcoords="offset points", ha='center', arrowprops=dict(arrowstyle="->", color="green"), color="green")
        ax3.annotate(get_text('dollar_peak_chart', lang, name=outcome_1_name), (x_indices[no_peak], no_curve[no_peak]), xytext=(0, -20),
                     textcoords="offset points", ha='center', arrowprops=dict(arrowstyle="->", color="red"), color="red")
        last_x = x_indices[-1]
        ax3.annotate(f"$ {yes_curve[-1]:.2f}", (last_x, yes_curve[-1]), xytext=(15, 0), textcoords="offset points", color="green")
        ax3.annotate(f"$ {no_curve[-1]:.2f}", (last_x, no_curve[-1]), xytext=(15, 0), textcoords="offset points", color="red")
        ax3.annotate(f"$ {net_curve[-1]:.2f}", (last_x, net_curve[-1]), xytext=(15, 0), textcoords="offset points", color="blue")
    
    ax3.set_title(get_text('dollar_exposure', lang))
    ax3.set_ylabel(get_text('exposure_dollar', lang))
    ax3.set_xticks([])
    ax3.legend(loc="upper left")
    
    maker_count = sum(1 for t in parsed if t.get('maker_taker') == 'MAKER')
    taker_count = sum(1 for t in parsed if t.get('maker_taker') == 'TAKER')
    
    lbl_buy = get_text('buy', lang)
    lbl_sell = get_text('sell', lang)
    lbl_trades = get_text('trades', lang)
    summary = (
        f"{outcome_0_name}  {lbl_buy}: {yes_buy_sh:.2f} {lbl_sh} ($ {yes_buy_cost:.2f}) "
        f" | {lbl_sell}: {yes_sell_sh:.2f} {lbl_sh} ($ {yes_sell_cost:.2f})\n"
        f"{outcome_1_name}  {lbl_buy}: {no_buy_sh:.2f} {lbl_sh} ($ {no_buy_cost:.2f}) "
        f" | {lbl_sell}: {no_sell_sh:.2f} {lbl_sh} ($ {no_sell_cost:.2f})\n"
        f"Maker/Taker: MAKER {maker_count} {lbl_trades} | TAKER {taker_count} {lbl_trades}"
    )
    fig.text(0.01, 0.01, summary, ha="left", va="bottom", fontsize=11,
             bbox=dict(facecolor="white", alpha=0.75, edgecolor="black"))
    fig.text(0.99, 0.06, pnl_text, ha="right", va="top", fontsize=12,
             bbox=dict(facecolor="white", alpha=0.75, edgecolor="black"))
    
    # 第四图：份额敞口
    ax4.grid(alpha=0.3)
    ax4.plot(x_indices, yes_sh_curve, color="green", linewidth=2, label=f"{outcome_0_name} {lbl_exp} ({lbl_sh})")
    ax4.plot(x_indices, no_sh_curve, color="red", linewidth=2, label=f"{outcome_1_name} {lbl_exp} ({lbl_sh})")
    ax4.plot(x_indices, net_sh_curve, color="blue", linewidth=2, label=f"{lbl_net} ({lbl_sh})")
    
    if len(yes_sh_curve) > 0:
        yes_sh_peak = int(np.argmax(yes_sh_curve))
        no_sh_peak = int(np.argmax(no_sh_curve))
        ax4.annotate(get_text('share_peak_chart', lang, name=outcome_0_name), (x_indices[yes_sh_peak], yes_sh_curve[yes_sh_peak]), xytext=(0, -20),
                     textcoords="offset points", ha='center', arrowprops=dict(arrowstyle="->", color="green"), color="green")
        ax4.annotate(get_text('share_peak_chart', lang, name=outcome_1_name), (x_indices[no_sh_peak], no_sh_curve[no_sh_peak]), xytext=(0, -20),
                     textcoords="offset points", ha='center', arrowprops=dict(arrowstyle="->", color="red"), color="red")
        ax4.annotate(f"{yes_sh_curve[-1]:.2f} {lbl_sh}", (last_x, yes_sh_curve[-1]), xytext=(15, 0), textcoords="offset points", color="green")
        ax4.annotate(f"{no_sh_curve[-1]:.2f} {lbl_sh}", (last_x, no_sh_curve[-1]), xytext=(15, 0), textcoords="offset points", color="red")
        ax4.annotate(f"{net_sh_curve[-1]:.2f} {lbl_sh}", (last_x, net_sh_curve[-1]), xytext=(15, 0), textcoords="offset points", color="blue")
    
    ax4.set_title(get_text('share_exposure', lang))
    ax4.set_ylabel(get_text('exposure_share', lang))
    ax4.xaxis.set_major_locator(ticker.MaxNLocator(nbins=12))
    ax4.xaxis.set_major_formatter(ticker.FuncFormatter(time_formatter))
    plt.setp(ax4.get_xticklabels(), rotation=30, ha='right')
    ax4.legend(loc="upper left")
    
    xlim_range = (-0.5, len(unique_timestamps) - 0.5)
    for axis in (ax1, ax2, ax3, ax4):
        axis.set_xlim(*xlim_range)
    
    plt.tight_layout()
    chart_file = f"{file_prefix}_chart.png"
    report_file = f"{file_prefix}_report.txt"
    plt.savefig(chart_file, dpi=200, bbox_inches="tight")
    plt.close('all')
    
    # 更新进度: 生成报告
    if cancel_flag:
        cancel_flag["percent"] = 95
    
    # 生成报告
    write_stats_report(
        report_file,
        target_market,
        resolved_side,
        len(parsed),
        remaining_yes,
        remaining_no,
        final_value if final_value is not None else 0,
        total_spent,
        pnl if pnl is not None else 0,
        yes_buy_sh,
        yes_buy_cost,
        yes_sell_sh,
        yes_sell_cost,
        no_buy_sh,
        no_buy_cost,
        no_sell_sh,
        no_sell_cost,
        cum_yes_total,
        cum_no_total,
        cum_yes_cost_total,
        cum_no_cost_total,
        yes_curve,
        no_curve,
        net_curve,
        yes_sh_curve,
        no_sh_curve,
        net_sh_curve,
        prices,
        parsed,
        user_address,
        username,
        outcome_0_name,
        outcome_1_name,
        is_resolved,
        lang,
        source_stats,  # 新增：交易来源统计
    )
    
    # 更新进度: 完成
    if cancel_flag:
        cancel_flag["percent"] = 100
    
    return chart_file, report_file, trades_file, None


def run_analysis_by_condition_id(condition_id, user_address, market_title="未知市场", resolved_arg="AUTO", output_dir=None, cancel_flag=None, is_resolved=False, outcomes_str=None, lang='zh', event_slug=None):
    """
    通过 condition_id 直接分析（用于多选项市场查询）
    
    参数:
        condition_id: 市场的 conditionId
        user_address: 用户钱包地址
        market_title: 市场标题
        resolved_arg: 结算方向 (YES/NO/AUTO)
        output_dir: 输出目录
        cancel_flag: 取消标志字典
        is_resolved: 市场是否已结算（从前端传入）
        outcomes_str: outcomes JSON 字符串（从前端传入）
        lang: 语言 ('zh' 或 'en')，默认中文
    
    返回:
        成功: (chart_file, report_file, trades_file, None)
        失败: (None, None, None, error)
    """
    import os
    
    # 检查是否取消
    if cancel_flag and cancel_flag.get("cancelled"):
        return None, None, None, "CANCELLED"
    
    # 更新进度: 获取交易数据
    if cancel_flag:
        cancel_flag["percent"] = 10
    
    # 获取交易数据（先尝试 trades API，失败则用 activity API）
    raw_data, data_source = fetch_trades_with_fallback(condition_id, user_address)
    
    # v3.27: 即使 trades 为空，也尝试获取链上事件
    chain_events_for_check = []
    if not raw_data and NEG_RISK_MODULE_AVAILABLE:
        try:
            from neg_risk import get_chain_events_by_condition
            chain_events_for_check = get_chain_events_by_condition(user_address, condition_id)
            if chain_events_for_check:
                print(f"[INFO] trades 为空，但找到 {len(chain_events_for_check)} 个链上事件")
        except Exception as e:
            print(f"[WARNING] 获取链上事件失败: {e}")
    
    # 只有当 trades 和链上事件都为空时才返回错误
    if not raw_data and not chain_events_for_check:
        return None, None, None, get_text('no_trades', lang)
    
    if data_source == "activity":
        print(f"[INFO] 使用 activity API 获取数据（neg-risk 交易）")
    
    # v3.27: 如果 raw_data 为空，初始化为空列表
    if raw_data is None:
        raw_data = []
    
    # 优先使用前端传入的 outcomes，否则从交易数据提取
    market_outcomes = []
    if outcomes_str:
        try:
            market_outcomes = json.loads(outcomes_str) if isinstance(outcomes_str, str) else outcomes_str
        except:
            pass
    
    # 如果前端未传入或解析失败，从交易数据中提取
    if not market_outcomes or len(market_outcomes) < 2:
        outcome_names = {}
        for item in raw_data:
            outcome = item.get("outcome", "")
            outcome_idx = item.get("outcomeIndex", 0)
            if outcome and outcome_idx not in outcome_names:
                outcome_names[outcome_idx] = outcome
        if outcome_names:
            market_outcomes = [outcome_names.get(0, "Yes"), outcome_names.get(1, "No")]
    
    # is_resolved 直接使用前端传入的值（已在函数参数中定义）
    
    # 生成文件名前缀
    file_prefix = generate_safe_filename(market_title, user_address)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        file_prefix = os.path.join(output_dir, file_prefix)
    
    # 保存原始交易数据（v3.27: 可能为空列表）
    trades_file = f"{file_prefix}_trades.json"
    with open(trades_file, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=2, ensure_ascii=False)
    
    # 排序
    raw_data.sort(key=lambda x: x.get("timestamp", 0))
    
    # 获取 maker/taker 角色（v3.27: raw_data 可能为空）
    maker_taker_roles = {}
    if user_address and raw_data:
        try:
            maker_taker_roles = batch_get_maker_taker_roles(raw_data, user_address, cancel_flag)
        except CancelledError:
            return None, None, None, "CANCELLED"
    
    # 检查是否取消
    if cancel_flag and cancel_flag.get("cancelled"):
        return None, None, None, "CANCELLED"
    
    # 更新进度: 解析交易数据
    if cancel_flag:
        cancel_flag["percent"] = 85
    
    # 解析交易
    parsed = []
    target_market = market_title
    # v3.27: 处理 raw_data 为空的情况
    username = raw_data[0].get("name", "") or raw_data[0].get("pseudonym", "") or "未知" if raw_data else "未知"
    
    # 获取 outcome 名称
    if len(market_outcomes) >= 2:
        outcome_0_name = market_outcomes[0]
        outcome_1_name = market_outcomes[1]
    elif raw_data:
        outcome_names = {}
        for item in raw_data:
            outcome = item.get("outcome", "")
            outcome_idx = item.get("outcomeIndex", 0)
            if outcome and outcome_idx not in outcome_names:
                outcome_names[outcome_idx] = outcome
        outcome_0_name = outcome_names.get(0, "Yes")
        outcome_1_name = outcome_names.get(1, "No")
    else:
        # v3.27: raw_data 为空时使用默认值
        outcome_0_name = "Yes"
        outcome_1_name = "No"
    
    # 决定结算方向
    resolved_side = None
    resolved_arg = normalize_resolved_arg(resolved_arg)
    if resolved_arg in {"YES", "NO"}:
        resolved_side = resolved_arg
    else:
        inferred, latest = infer_resolved_side_from_trades(raw_data)
        if inferred:
            resolved_side = inferred
        else:
            resolved_side = "YES"
    
    resolved_outcome = outcome_0_name if resolved_side == "YES" else outcome_1_name
    
    for item in raw_data:
        entry = {}
        raw_side = item.get("side", "BUY").upper()
        entry["type"] = "Buy" if raw_side == "BUY" else "Sell"
        entry["market"] = item.get("title", "")
        entry["side"] = item.get("outcome", outcome_0_name)
        entry["outcomeIndex"] = item.get("outcomeIndex", 0)
        entry["price"] = float(item.get("price", 0)) * 100.0
        entry["shares"] = float(item.get("size", 0))
        entry["cost"] = float(item.get("price", 0)) * entry["shares"]
        entry["timestamp"] = int(item.get("timestamp", 0))
        tx_hash = item.get("transactionHash", "")
        entry["maker_taker"] = maker_taker_roles.get(tx_hash, "UNKNOWN")
        entry["tx_hash"] = tx_hash
        entry["source"] = "Trade"  # 默认来源
        entry["record_type"] = "trade"  # 记录类型
        parsed.append(entry)
    
    # v3.26: 获取链上事件 (Split/Merge/Redeem) 并合并到交易记录
    # v3.27: 复用之前检查时已获取的链上事件，避免重复查询
    chain_events_count = 0
    if NEG_RISK_MODULE_AVAILABLE:
        try:
            from neg_risk import get_chain_events_by_condition
            # 如果之前已经获取过链上事件，直接使用
            if chain_events_for_check:
                chain_events = chain_events_for_check
            else:
                chain_events = get_chain_events_by_condition(user_address, condition_id)
            chain_events_count = len(chain_events)
            if chain_events_count > 0:
                print(f"[INFO] 找到 {chain_events_count} 个链上事件 (Split/Merge/Redeem)")
            
            for event in chain_events:
                entry = {
                    'type': event['direction'],  # +Yes +No / -Yes -No / -Position
                    'market': market_title,
                    'side': event['direction'],
                    'outcomeIndex': -1,  # 特殊标记，表示这是链上操作
                    'price': 0,
                    'shares': event.get('shares', 0),
                    'cost': event.get('cost', 0),
                    'timestamp': event.get('timestamp', 0),
                    'maker_taker': '-',
                    'tx_hash': event.get('tx_hash', ''),
                    'source': event.get('source', ''),  # Split / Merge / Redeem
                    'record_type': event.get('type', ''),  # split / merge / redeem
                    'description': event.get('description', ''),
                    'amount': event.get('amount', 0),
                }
                parsed.append(entry)
        except Exception as e:
            print(f"[WARNING] 获取链上事件失败: {e}")
    
    # 按时间排序（合并交易和链上事件）
    parsed.sort(key=lambda x: x.get('timestamp', 0))
    
    if not parsed:
        return None, None, trades_file, "解析交易失败"
    
    # 交易来源分析（如果 neg_risk 模块可用且有 event_slug 且有交易数据）
    source_stats = None
    if NEG_RISK_MODULE_AVAILABLE and event_slug and raw_data:
        try:
            enriched_records, source_stats = enrich_trades_batch(
                raw_data, user_address, condition_id, event_slug
            )
            # 将来源信息添加到 parsed 中
            for i, record in enumerate(enriched_records):
                if i < len(parsed):
                    parsed[i]['source'] = record.source
                    if record.counterparty:
                        parsed[i]['counterparty'] = record.counterparty
                    # Neg-Risk 详情
                    if record.source_trades:
                        parsed[i]['source_trades'] = [
                            {'market_name': st.market_name, 'outcome': st.outcome, 
                             'shares': st.shares, 'price': st.price, 'cost': st.cost}
                            for st in record.source_trades
                        ]
                        parsed[i]['conversion_cost'] = record.conversion_cost
                        parsed[i]['usdc_returned'] = record.usdc_returned
                        parsed[i]['net_cost'] = record.net_cost
        except Exception as e:
            print(f"[WARNING] 来源分析失败: {e}")
            source_stats = None
    
    # v3.26: 统计链上事件到 source_stats
    if chain_events_count > 0:
        if source_stats is None:
            source_stats = {}
        # 统计各类型链上事件数量
        for e in parsed:
            rt = e.get('record_type', 'trade')
            if rt in ['split', 'merge', 'redeem']:
                source_stats[rt] = source_stats.get(rt, 0) + 1
    
    # v3.26: 只从交易记录中提取价格（排除链上事件）
    prices = [e["price"] for e in parsed if e.get("record_type", "trade") == "trade"]
    
    # 计算敞口曲线 (v3.26: 支持 Split/Merge/Redeem)
    yes_curve, no_curve, net_curve = [], [], []
    yes_sh_curve, no_sh_curve, net_sh_curve = [], [], []
    yes_exp = no_exp = 0
    yes_sh_exp = no_sh_exp = 0
    
    for e in parsed:
        record_type = e.get('record_type', 'trade')
        
        # v3.26: 处理链上事件
        if record_type == 'split':
            # Split: 花费 USDC，获得 Yes+No 各 N 份
            shares = e.get('shares', 0)
            cost = abs(e.get('amount', 0) or e.get('cost', 0))
            yes_exp += cost / 2  # 成本平分到 Yes/No
            no_exp += cost / 2
            yes_sh_exp += shares
            no_sh_exp += shares
        elif record_type == 'merge':
            # Merge: 消耗 Yes+No 各 N 份，回收 USDC
            shares = e.get('shares', 0)
            cost = abs(e.get('amount', 0) or e.get('cost', 0))
            yes_exp -= cost / 2
            no_exp -= cost / 2
            yes_sh_exp -= shares
            no_sh_exp -= shares
        elif record_type == 'redeem':
            # Redeem: 结算后赎回，不影响敞口计算
            pass
        else:
            # 普通交易
            is_outcome_0 = (e.get("outcomeIndex", 0) == 0)
            if is_outcome_0:
                yes_exp += e["cost"] if e["type"] == "Buy" else -e["cost"]
                yes_sh_exp += e["shares"] if e["type"] == "Buy" else -e["shares"]
            else:
                no_exp += e["cost"] if e["type"] == "Buy" else -e["cost"]
                no_sh_exp += e["shares"] if e["type"] == "Buy" else -e["shares"]
        
        yes_curve.append(yes_exp)
        no_curve.append(no_exp)
        net_curve.append(yes_exp + no_exp)
        yes_sh_curve.append(yes_sh_exp)
        no_sh_curve.append(no_sh_exp)
        net_sh_curve.append(yes_sh_exp + no_sh_exp)
    
    # 计算统计数据
    remaining_yes = yes_sh_curve[-1] if yes_sh_curve else 0
    remaining_no = no_sh_curve[-1] if no_sh_curve else 0
    total_spent = net_curve[-1] if net_curve else 0
    
    if is_resolved:
        if resolved_side == "YES":
            final_value = remaining_yes * 1.0
        else:
            final_value = remaining_no * 1.0
        pnl = final_value - total_spent
    else:
        final_value = None
        pnl = None
        resolved_outcome = None
    
    # 计算买卖统计 (v3.26: 排除链上事件)
    yes_buy_sh = yes_buy_cost = yes_sell_sh = yes_sell_cost = 0
    no_buy_sh = no_buy_cost = no_sell_sh = no_sell_cost = 0
    raw_vol_yes, raw_vol_no = [], []
    raw_cost_yes, raw_cost_no = [], []
    
    for e in parsed:
        # v3.26: 跳过链上事件的买卖统计
        if e.get('record_type', 'trade') != 'trade':
            raw_vol_yes.append(0)
            raw_vol_no.append(0)
            raw_cost_yes.append(0)
            raw_cost_no.append(0)
            continue
            
        is_outcome_0 = (e.get("outcomeIndex", 0) == 0)
        is_buy = (e["type"] == "Buy")
        
        if is_buy:
            if is_outcome_0:
                yes_buy_sh += e["shares"]
                yes_buy_cost += e["cost"]
                raw_vol_yes.append(e["shares"])
                raw_vol_no.append(0)
                raw_cost_yes.append(e["cost"])
                raw_cost_no.append(0)
            else:
                no_buy_sh += e["shares"]
                no_buy_cost += e["cost"]
                raw_vol_yes.append(0)
                raw_vol_no.append(e["shares"])
                raw_cost_yes.append(0)
                raw_cost_no.append(e["cost"])
        else:
            raw_vol_yes.append(0)
            raw_vol_no.append(0)
            raw_cost_yes.append(0)
            raw_cost_no.append(0)
            if is_outcome_0:
                yes_sell_sh += e["shares"]
                yes_sell_cost += e["cost"]
            else:
                no_sell_sh += e["shares"]
                no_sell_cost += e["cost"]
    
    cum_yes = np.cumsum(raw_vol_yes)
    cum_no = np.cumsum(raw_vol_no)
    cum_yes_cost = np.cumsum(raw_cost_yes)
    cum_no_cost = np.cumsum(raw_cost_no)
    
    cum_yes_total = cum_yes[-1] if len(cum_yes) > 0 else 0
    cum_no_total = cum_no[-1] if len(cum_no) > 0 else 0
    cum_yes_cost_total = cum_yes_cost[-1] if len(cum_yes_cost) > 0 else 0
    cum_no_cost_total = cum_no_cost[-1] if len(cum_no_cost) > 0 else 0
    
    # 更新进度: 生成图表
    if cancel_flag:
        cancel_flag["percent"] = 90
    
    # 生成图表
    unique_timestamps = sorted(list(set(t['timestamp'] for t in parsed)))
    ts_map = {ts: i for i, ts in enumerate(unique_timestamps)}
    x_indices = [ts_map[e['timestamp']] for e in parsed]
    
    if is_resolved:
        pnl_text = (
            f"{get_text('settlement_result', lang, name=resolved_outcome)}\n\n"
            f"{get_text('remaining_shares', lang, name=outcome_0_name)}: {remaining_yes:.2f}\n"
            f"{get_text('remaining_shares', lang, name=outcome_1_name)}:  {remaining_no:.2f}\n\n"
            f"{get_text('final_value', lang)}: $ {final_value:.2f}\n"
            f"{get_text('total_spent', lang)}: $ {total_spent:.2f}\n\n"
            f"{get_text('final_pnl', lang)}: $ {pnl:.2f}"
        )
    else:
        pnl_text = (
            f"{get_text('unsettled_status', lang)}\n\n"
            f"{get_text('remaining_shares', lang, name=outcome_0_name)}: {remaining_yes:.2f}\n"
            f"{get_text('remaining_shares', lang, name=outcome_1_name)}:  {remaining_no:.2f}\n\n"
            f"{get_text('total_spent', lang)}: $ {total_spent:.2f}"
        )
    
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(
        4, 1, figsize=(16, 14.5),
        gridspec_kw={'height_ratios': [3, 1.3, 1.1, 1.1]}
    )
    fig.subplots_adjust(hspace=0.45, bottom=0.2)
    
    # 图表绑制 (简化版，复用主函数逻辑)
    grouped_trades = {}
    for i, e in enumerate(parsed):
        x_idx = ts_map[e['timestamp']]
        if x_idx not in grouped_trades:
            grouped_trades[x_idx] = []
        grouped_trades[x_idx].append(e)
    
    next_up = True
    for x_idx in sorted(grouped_trades.keys()):
        group = grouped_trades[x_idx]
        avg_price = sum(t["price"] for t in group) / len(group)
        
        if len(group) == 1:
            e = group[0]
            style_key = (e["type"], e["side"])
            if style_key in STYLES:
                color, marker, label = STYLES[style_key]
            else:
                color, marker, label = ("gray", "o", "Unknown")
            
            ax1.scatter(x_idx, e["price"], color=color, marker=marker,
                        s=60, linewidths=2.5 if marker=="x" else 1.0,
                        alpha=0.9, zorder=5)
        else:
            count = len(group)
            first_e = group[0]
            same_side = all((t["type"] == first_e["type"] and t["side"] == first_e["side"]) for t in group)
            
            if same_side:
                style_key = (first_e["type"], first_e["side"])
                color, _, _ = STYLES.get(style_key, ("gray", "o", ""))
            else:
                color = "#1f77b4"
            
            ax1.scatter(x_idx, avg_price, color="white", marker="o", s=300, edgecolors=color, linewidth=2, zorder=5)
            ax1.text(x_idx, avg_price, str(count), ha="center", va="center", fontsize=9, fontweight="bold", color=color, zorder=6)
    
    ax1.set_title(get_text('chart_title', lang, market=target_market))
    ax1.set_ylabel(get_text('price_cents', lang))
    
    def time_formatter(x, pos):
        idx = int(x)
        if 0 <= idx < len(unique_timestamps):
            ts = unique_timestamps[idx]
            return datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S')
        return ""
    
    ax1.xaxis.set_major_locator(ticker.MaxNLocator(nbins=12))
    ax1.xaxis.set_major_formatter(ticker.FuncFormatter(time_formatter))
    ax1.set_yticks(range(0, 101, 10))
    ax1.grid(axis='y', linestyle='--', alpha=0.3)
    
    # 第二图：累计买入
    lbl_cum = get_text('cumulative', lang)
    lbl_sh = get_text('shares', lang)
    ax2.plot(x_indices, cum_yes, color="green", alpha=0.3, linewidth=1, label=f"{lbl_cum} {outcome_0_name} ({lbl_sh})")
    ax2.fill_between(x_indices, cum_yes, color="green", alpha=0.1)
    ax2.plot(x_indices, cum_no, color="red", alpha=0.3, linewidth=1, label=f"{lbl_cum} {outcome_1_name} ({lbl_sh})")
    ax2.fill_between(x_indices, cum_no, color="red", alpha=0.1)
    ax2.set_ylabel(get_text('cumulative_buy_shares', lang))
    ax2.grid(axis='y', alpha=0.2)
    ax2.set_xticks([])
    ax2.set_title(get_text('cumulative_buy_chart', lang))
    ax2.legend(loc="upper left")
    
    # 第三图：美元敞口
    lbl_exp = get_text('exposure', lang)
    lbl_net = get_text('net_exposure', lang)
    ax3.grid(alpha=0.3)
    ax3.plot(x_indices, yes_curve, color="green", linewidth=2, label=f"{outcome_0_name} {lbl_exp} ($)")
    ax3.plot(x_indices, no_curve, color="red", linewidth=2, label=f"{outcome_1_name} {lbl_exp} ($)")
    ax3.plot(x_indices, net_curve, color="blue", linewidth=2, label=f"{lbl_net} ($)")
    ax3.set_title(get_text('dollar_exposure', lang))
    ax3.set_ylabel(get_text('exposure_dollar', lang))
    ax3.set_xticks([])
    ax3.legend(loc="upper left")
    
    maker_count = sum(1 for t in parsed if t.get('maker_taker') == 'MAKER')
    taker_count = sum(1 for t in parsed if t.get('maker_taker') == 'TAKER')
    
    lbl_buy = get_text('buy', lang)
    lbl_sell = get_text('sell', lang)
    lbl_trades = get_text('trades', lang)
    summary = (
        f"{outcome_0_name}  {lbl_buy}: {yes_buy_sh:.2f} {lbl_sh} ($ {yes_buy_cost:.2f}) "
        f" | {lbl_sell}: {yes_sell_sh:.2f} {lbl_sh} ($ {yes_sell_cost:.2f})\n"
        f"{outcome_1_name}  {lbl_buy}: {no_buy_sh:.2f} {lbl_sh} ($ {no_buy_cost:.2f}) "
        f" | {lbl_sell}: {no_sell_sh:.2f} {lbl_sh} ($ {no_sell_cost:.2f})\n"
        f"Maker/Taker: MAKER {maker_count} {lbl_trades} | TAKER {taker_count} {lbl_trades}"
    )
    fig.text(0.01, 0.01, summary, ha="left", va="bottom", fontsize=11,
             bbox=dict(facecolor="white", alpha=0.75, edgecolor="black"))
    fig.text(0.99, 0.06, pnl_text, ha="right", va="top", fontsize=12,
             bbox=dict(facecolor="white", alpha=0.75, edgecolor="black"))
    
    # 第四图：份额敞口
    ax4.grid(alpha=0.3)
    ax4.plot(x_indices, yes_sh_curve, color="green", linewidth=2, label=f"{outcome_0_name} {lbl_exp} ({lbl_sh})")
    ax4.plot(x_indices, no_sh_curve, color="red", linewidth=2, label=f"{outcome_1_name} {lbl_exp} ({lbl_sh})")
    ax4.plot(x_indices, net_sh_curve, color="blue", linewidth=2, label=f"{lbl_net} ({lbl_sh})")
    ax4.set_title(get_text('share_exposure', lang))
    ax4.set_ylabel(get_text('exposure_share', lang))
    ax4.xaxis.set_major_locator(ticker.MaxNLocator(nbins=12))
    ax4.xaxis.set_major_formatter(ticker.FuncFormatter(time_formatter))
    plt.setp(ax4.get_xticklabels(), rotation=30, ha='right')
    ax4.legend(loc="upper left")
    
    xlim_range = (-0.5, len(unique_timestamps) - 0.5)
    for axis in (ax1, ax2, ax3, ax4):
        axis.set_xlim(*xlim_range)
    
    plt.tight_layout()
    chart_file = f"{file_prefix}_chart.png"
    report_file = f"{file_prefix}_report.txt"
    plt.savefig(chart_file, dpi=200, bbox_inches="tight")
    plt.close('all')
    
    # 更新进度: 生成报告
    if cancel_flag:
        cancel_flag["percent"] = 95
    
    # 生成报告
    write_stats_report(
        report_file,
        target_market,
        resolved_side,
        len(parsed),
        remaining_yes,
        remaining_no,
        final_value if final_value is not None else 0,
        total_spent,
        pnl if pnl is not None else 0,
        yes_buy_sh,
        yes_buy_cost,
        yes_sell_sh,
        yes_sell_cost,
        no_buy_sh,
        no_buy_cost,
        no_sell_sh,
        no_sell_cost,
        cum_yes_total,
        cum_no_total,
        cum_yes_cost_total,
        cum_no_cost_total,
        yes_curve,
        no_curve,
        net_curve,
        yes_sh_curve,
        no_sh_curve,
        net_sh_curve,
        prices,
        parsed,
        user_address,
        username,
        outcome_0_name,
        outcome_1_name,
        is_resolved,
        lang,
        source_stats,  # 新增：交易来源统计
    )
    
    # 更新进度: 完成
    if cancel_flag:
        cancel_flag["percent"] = 100
    
    return chart_file, report_file, trades_file, None


if __name__ == "__main__":
    main()
