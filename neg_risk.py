#!/usr/bin/env python3
"""
Neg-Risk 交易分析模块
用于识别和分析 Polymarket 多选项市场的 Neg-Risk 转换交易
"""
import os
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

# API 端点
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
POLYGON_RPC_URL = os.environ.get('POLY_RPC_URL', 'https://polygon-rpc.com')

# 合约地址
CONTRACTS = {
    'CTF': '0x4D97DCd97eC945f40cF65F87097ACe5EA0476045'.lower(),
    'CTF_EXCHANGE': '0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E'.lower(),
    'NEG_RISK_ADAPTER': '0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296'.lower(),
    'NEG_RISK_CTF_EXCHANGE': '0xC5d563A36AE78145C45a50134d48A1215220f80a'.lower(),
}

# 事件签名
EVENT_TOPICS = {
    # CTF Exchange 交易事件
    'ORDER_FILLED': '0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6',
    # ERC1155 转账事件
    'TRANSFER_SINGLE': '0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62',
    'TRANSFER_BATCH': '0x4a39dc06d4c0dbc64b70af90fd698a233a518aa5d07e595d983b8c0526c8f7fb',
    # CTF 合约事件 - Split/Merge
    'POSITION_SPLIT': '0x2e6bb91f8cbcda0c93623c54d0403a43514fabc40084ec96b6d5379a74786298',
    'POSITIONS_MERGE': '0x6f13ca62553fcc2bcd2372180a43949c1e4cebba603901ede2f4e14f36b282ca',
    # NegRiskAdapter 事件
    'POSITIONS_CONVERTED': '0xb03d19dddbc72a87e735ff0ea3b57bef133ebe44e1894284916a84044deb367e',
    'PAYOUT_REDEMPTION': '0x2682012a4a4f1973119f1c9b90745d1bd91fa2bab387344f044cb3586864d18d',
}


# =============================================================================
# Step 3: 数据结构定义
# =============================================================================

@dataclass
class SourceTrade:
    """Neg-Risk 转换的源交易"""
    market_name: str = ""
    condition_id: str = ""
    outcome: str = ""  # 'yes' | 'no'
    side: str = ""     # 'buy' | 'sell'
    shares: float = 0.0
    price: float = 0.0
    cost: float = 0.0


@dataclass
class ActivityRecord:
    """统一的持仓变动记录"""
    timestamp: int = 0
    tx_hash: str = ""
    source: str = "unknown"  # 'direct' | 'neg_risk' | 'split' | 'merge' | 'transfer' | 'redeem' | 'unknown'
    direction: str = ""      # 'in' | 'out' (买入/卖出)
    outcome: str = ""        # 'Yes' | 'No'
    shares: float = 0.0
    cost: float = 0.0
    
    # Direct Trade 专用字段
    price: float = 0.0
    role: str = ""           # 'MAKER' | 'TAKER' | ''
    side: str = ""           # 'BUY' | 'SELL'
    
    # Neg-Risk 专用字段
    source_trades: List[SourceTrade] = field(default_factory=list)
    conversion_cost: float = 0.0
    usdc_returned: float = 0.0
    net_cost: float = 0.0
    
    # Transfer 专用字段
    counterparty: str = ""
    
    # 原始数据保留 (兼容现有代码)
    raw_data: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """转换为字典 (兼容现有代码)"""
        result = asdict(self)
        # 保留原始字段以兼容现有代码
        if self.raw_data:
            for key, value in self.raw_data.items():
                if key not in result:
                    result[key] = value
        return result
    
    def to_legacy_format(self) -> Dict:
        """转换为现有 trades API 兼容的格式"""
        return {
            "transactionHash": self.tx_hash,
            "timestamp": self.timestamp,
            "side": self.side,
            "size": str(self.shares),
            "price": str(self.price),
            "outcome": self.outcome,
            "source": self.source,
            "role": self.role,
            # 原始数据字段
            **self.raw_data
        }


# =============================================================================
# Step 1: 判断函数
# =============================================================================

def is_neg_risk_market(event_slug: str) -> bool:
    """
    判断指定 event 是否是 neg-risk 市场
    
    Args:
        event_slug: 事件的 slug (从 URL 提取)
        
    Returns:
        bool: True 表示是 neg-risk 市场
    """
    try:
        resp = requests.get(
            f"{GAMMA_API_BASE}/events",
            params={"slug": event_slug},
            timeout=15
        )
        resp.raise_for_status()
        events = resp.json()
        
        if not events:
            return False
        
        event = events[0]
        return event.get('negRisk', False) or event.get('enableNegRisk', False)
        
    except Exception as e:
        print(f"[Neg-Risk] 判断市场类型失败: {e}")
        return False


def get_event_info(event_slug: str) -> Optional[Dict]:
    """
    获取 event 完整信息
    
    Args:
        event_slug: 事件的 slug
        
    Returns:
        dict: 事件信息，包含 title, negRisk, markets 等
    """
    try:
        resp = requests.get(
            f"{GAMMA_API_BASE}/events",
            params={"slug": event_slug},
            timeout=15
        )
        resp.raise_for_status()
        events = resp.json()
        
        if not events:
            return None
        
        return events[0]
        
    except Exception as e:
        print(f"[Neg-Risk] 获取事件信息失败: {e}")
        return None


def get_event_condition_ids(event_slug: str) -> List[str]:
    """
    获取 event 下所有子市场的 conditionId 列表
    
    Args:
        event_slug: 事件的 slug
        
    Returns:
        list: conditionId 列表
    """
    event = get_event_info(event_slug)
    if not event:
        return []
    
    markets = event.get('markets', [])
    return [m.get('conditionId', '') for m in markets if m.get('conditionId')]


def get_condition_to_market_map(event_slug: str) -> Dict[str, Dict]:
    """
    获取 conditionId 到市场信息的映射
    
    Args:
        event_slug: 事件的 slug
        
    Returns:
        dict: {conditionId: {question, outcomes, slug, ...}}
    """
    event = get_event_info(event_slug)
    if not event:
        return {}
    
    result = {}
    for market in event.get('markets', []):
        condition_id = market.get('conditionId', '')
        if condition_id:
            result[condition_id.lower()] = {
                'question': market.get('question', ''),
                'outcomes': market.get('outcomes', '["Yes", "No"]'),
                'slug': market.get('slug', ''),
                'closed': market.get('closed', False),
            }
    
    return result


def extract_event_slug_from_url(url: str) -> Optional[str]:
    """
    从 Polymarket URL 提取 event slug
    
    Args:
        url: Polymarket 市场 URL
        
    Returns:
        str: event slug 或 None
        
    Examples:
        https://polymarket.com/event/fed-decision-in-january -> fed-decision-in-january
        https://polymarket.com/event/fed-decision-in-january/no-change -> fed-decision-in-january
    """
    import re
    match = re.search(r'polymarket\.com/event/([^/\?]+)', url)
    if match:
        return match.group(1)
    return None


# =============================================================================
# Step 2: 链上分析函数
# =============================================================================

# CLOB API 端点
CLOB_API_BASE = "https://clob.polymarket.com"

# Token ID 缓存 {condition_id: {'yes': token_id, 'no': token_id}}
_token_id_cache: Dict[str, Dict[str, str]] = {}


def get_market_token_ids(condition_id: str) -> Dict[str, str]:
    """
    从 CLOB API 获取市场的 token IDs
    
    Args:
        condition_id: 市场的 conditionId
        
    Returns:
        dict: {'yes': token_id_hex, 'no': token_id_hex}
    """
    cid_lower = condition_id.lower()
    
    # 检查缓存
    if cid_lower in _token_id_cache:
        return _token_id_cache[cid_lower]
    
    try:
        resp = requests.get(
            f"{CLOB_API_BASE}/markets/{condition_id}",
            timeout=15
        )
        resp.raise_for_status()
        market = resp.json()
        
        result = {}
        for token in market.get('tokens', []):
            outcome = token.get('outcome', '').lower()
            token_id = token.get('token_id', '')
            if outcome and token_id:
                # 转换为 hex 格式 (不含 0x 前缀，64位补零)
                token_hex = hex(int(token_id))[2:].zfill(64).lower()
                result[outcome] = token_hex
        
        _token_id_cache[cid_lower] = result
        return result
        
    except Exception as e:
        print(f"[Neg-Risk] 获取 token IDs 失败: {e}")
        return {}


def build_token_to_condition_map(condition_ids: List[str]) -> Dict[str, Dict]:
    """
    构建 token_id 到 condition_id 的映射
    
    Args:
        condition_ids: conditionId 列表
        
    Returns:
        dict: {token_id_hex: {'condition_id': str, 'outcome': 'yes'|'no'}}
    """
    result = {}
    
    for cid in condition_ids:
        token_ids = get_market_token_ids(cid)
        for outcome, token_hex in token_ids.items():
            result[token_hex] = {
                'condition_id': cid.lower(),
                'outcome': outcome
            }
    
    return result


def analyze_trade_source(
    tx_hash: str,
    user_address: str,
    target_condition_id: str,
    all_condition_ids: List[str],
    is_market_resolved: bool = False
) -> Tuple[str, Dict]:
    """
    分析交易来源类型
    
    Args:
        tx_hash: 交易哈希
        user_address: 用户地址
        target_condition_id: 目标市场的 conditionId
        all_condition_ids: 该 event 下所有子市场的 conditionId
        is_market_resolved: 市场是否已结算
        
    Returns:
        Tuple[str, Dict]: (来源类型, 详情信息)
            来源类型: 'direct' | 'neg_risk' | 'split' | 'merge' | 'transfer' | 'redeem' | 'unknown'
            详情信息: {'counterparty': str, 'shares': float, ...} 等额外信息
    """
    receipt = get_tx_receipt(tx_hash)
    if not receipt:
        return 'unknown', {}
    
    logs = receipt.get('logs', [])
    user_lower = user_address.lower()
    target_lower = target_condition_id.lower()
    
    # 构建 token -> condition 映射
    token_map = build_token_to_condition_map(all_condition_ids)
    
    # 解析 OrderFilled 事件
    order_filled_conditions = set()
    has_order_filled = False
    
    for log in logs:
        topics = log.get('topics', [])
        if not topics or topics[0].lower() != EVENT_TOPICS['ORDER_FILLED'].lower():
            continue
        
        if len(topics) < 4:
            continue
        
        maker = '0x' + topics[2][-40:].lower()
        taker = '0x' + topics[3][-40:].lower()
        
        if user_lower not in [maker, taker]:
            continue
        
        has_order_filled = True
        
        # 解析 assetId
        data = log.get('data', '0x')[2:]
        if len(data) < 128:
            continue
        
        maker_asset_hex = data[0:64].lower()
        taker_asset_hex = data[64:128].lower()
        
        # 查找对应的 condition_id
        for asset_hex in [maker_asset_hex, taker_asset_hex]:
            if asset_hex in token_map:
                order_filled_conditions.add(token_map[asset_hex]['condition_id'])
    
    # 如果有 OrderFilled 事件，判断 direct 还是 neg_risk
    if has_order_filled:
        if len(order_filled_conditions) == 1 and target_lower in order_filled_conditions:
            return 'direct', {}
        elif len(order_filled_conditions) > 1 or target_lower not in order_filled_conditions:
            return 'neg_risk', {}
        else:
            return 'direct', {}
    
    # 无 OrderFilled，解析 TransferSingle 事件判断 Split/Merge/Transfer/Redeem
    transfer_result = _parse_transfer_single_for_source(logs, user_address, target_condition_id, token_map, is_market_resolved)
    return transfer_result


def _parse_transfer_single_for_source(
    logs: List[Dict],
    user_address: str,
    target_condition_id: str,
    token_map: Dict[str, Dict],
    is_market_resolved: bool = False
) -> Tuple[str, Dict]:
    """
    解析 TransferSingle 事件，判断 Split/Merge/Transfer/Redeem
    
    Args:
        logs: 交易日志
        user_address: 用户地址
        target_condition_id: 目标 conditionId
        token_map: token 到 condition 的映射
        is_market_resolved: 市场是否已结算
        
    Returns:
        Tuple[str, Dict]: (来源类型, 详情)
    """
    user_lower = user_address.lower()
    ctf_address = CONTRACTS['CTF']
    zero_address = '0x' + '0' * 40
    
    # 收集用户相关的 TransferSingle 事件
    transfers_in = []   # 用户收到的 token
    transfers_out = []  # 用户发出的 token
    
    for log in logs:
        topics = log.get('topics', [])
        if not topics or topics[0].lower() != EVENT_TOPICS['TRANSFER_SINGLE'].lower():
            continue
        
        if len(topics) < 4:
            continue
        
        # TransferSingle: operator(topic1), from(topic2), to(topic3), id(data0), value(data1)
        from_addr = '0x' + topics[2][-40:].lower()
        to_addr = '0x' + topics[3][-40:].lower()
        
        # 解析 data
        data = log.get('data', '0x')[2:]
        if len(data) < 128:
            continue
        
        token_id = data[0:64].lower()
        value = int(data[64:128], 16)
        
        # 判断 token 属于哪个 condition
        token_info = token_map.get(token_id, {})
        token_condition = token_info.get('condition_id', '').lower()
        token_outcome = token_info.get('outcome', '')
        
        if to_addr == user_lower:
            transfers_in.append({
                'from': from_addr,
                'token_id': token_id,
                'value': value,
                'condition_id': token_condition,
                'outcome': token_outcome
            })
                
        elif from_addr == user_lower:
            transfers_out.append({
                'to': to_addr,
                'token_id': token_id,
                'value': value,
                'condition_id': token_condition,
                'outcome': token_outcome
            })
    
    if not transfers_in and not transfers_out:
        return 'unknown', {}
    
    details = {}
    
    # 1. Redeem: 市场已结算 + 用户发出 token 到 CTF + 无 token 收入
    if is_market_resolved and transfers_out and not transfers_in:
        to_ctf = [t for t in transfers_out if t['to'] == ctf_address]
        if to_ctf:
            details['redeemed_shares'] = sum(t['value'] / 1e6 for t in to_ctf)
            return 'redeem', details
    
    # 2. Split: 用户从 CTF 同时收到 Yes 和 No token
    if transfers_in:
        from_ctf = [t for t in transfers_in if t['from'] == ctf_address]
        if len(from_ctf) >= 2:
            outcomes = set(t['outcome'].lower() for t in from_ctf if t['outcome'])
            if 'yes' in outcomes and 'no' in outcomes:
                details['shares'] = from_ctf[0]['value'] / 1e6 if from_ctf else 0
                return 'split', details
    
    # 3. Merge: 用户向 CTF 同时发出 Yes 和 No token
    if transfers_out:
        to_ctf = [t for t in transfers_out if t['to'] == ctf_address]
        if len(to_ctf) >= 2:
            outcomes = set(t['outcome'].lower() for t in to_ctf if t['outcome'])
            if 'yes' in outcomes and 'no' in outcomes:
                details['shares'] = to_ctf[0]['value'] / 1e6 if to_ctf else 0
                return 'merge', details
    
    # 4. Transfer: 从其他用户收到 token (非 CTF, 非零地址)
    if transfers_in:
        from_users = [t for t in transfers_in if t['from'] != ctf_address and t['from'] != zero_address]
        if from_users:
            details['counterparty'] = from_users[0]['from']
            details['shares'] = sum(t['value'] / 1e6 for t in from_users)
            return 'transfer', details
    
    return 'unknown', {}



def parse_neg_risk_details(
    tx_hash: str,
    user_address: str,
    condition_map: Dict[str, Dict],
    token_map: Dict[str, Dict] = None
) -> Optional[Dict]:
    """
    解析 Neg-Risk 转换的详细信息
    
    Args:
        tx_hash: 交易哈希
        user_address: 用户地址
        condition_map: conditionId 到市场信息的映射
        token_map: token_id 到 condition 的映射 (可选，会自动构建)
        
    Returns:
        dict: {
            'source_trades': [...],  # 源交易列表
            'conversion_cost': float,  # 总花费
            'usdc_returned': float,  # 返还的 USDC
            'net_cost': float,  # 净成本
        }
    """
    receipt = get_tx_receipt(tx_hash)
    if not receipt:
        return None
    
    logs = receipt.get('logs', [])
    user_lower = user_address.lower()
    
    # 构建 token 映射
    if token_map is None:
        token_map = build_token_to_condition_map(list(condition_map.keys()))
    
    source_trades = []
    total_cost = 0.0
    
    for log in logs:
        topics = log.get('topics', [])
        if not topics or topics[0].lower() != EVENT_TOPICS['ORDER_FILLED'].lower():
            continue
        
        if len(topics) < 4:
            continue
        
        maker = '0x' + topics[2][-40:].lower()
        taker = '0x' + topics[3][-40:].lower()
        
        if user_lower not in [maker, taker]:
            continue
        
        # 解析 data
        data = log.get('data', '0x')[2:]
        if len(data) < 256:
            continue
        
        maker_asset_hex = data[0:64].lower()
        taker_asset_hex = data[64:128].lower()
        maker_amount = int(data[128:192], 16)
        taker_amount = int(data[192:256], 16)
        
        # 判断用户是买入还是卖出
        is_maker = user_lower == maker
        
        # 用户支付的 asset 和获得的 asset
        if is_maker:
            user_pays_asset = maker_asset_hex
            user_pays_amount = maker_amount
            user_gets_asset = taker_asset_hex
            user_gets_amount = taker_amount
        else:
            user_pays_asset = taker_asset_hex
            user_pays_amount = taker_amount
            user_gets_asset = maker_asset_hex
            user_gets_amount = maker_amount
        
        # 查找交易的市场
        trade_cid = None
        trade_outcome = None
        
        for asset in [user_pays_asset, user_gets_asset]:
            if asset in token_map:
                trade_cid = token_map[asset]['condition_id']
                trade_outcome = token_map[asset]['outcome']
                break
        
        if trade_cid and trade_cid in condition_map:
            market_info = condition_map[trade_cid]
            
            # 计算价格和份额
            # assetId = 0 表示 USDC
            is_usdc_pay = user_pays_asset == '0' * 64
            
            if is_usdc_pay:
                shares = user_gets_amount / 1e6
                cost = user_pays_amount / 1e6
                price = cost / shares if shares > 0 else 0
                side = 'buy'
            else:
                shares = user_pays_amount / 1e6
                cost = user_gets_amount / 1e6
                price = cost / shares if shares > 0 else 0
                side = 'sell'
            
            source_trades.append({
                'market_name': market_info.get('question', ''),
                'condition_id': trade_cid,
                'outcome': trade_outcome,
                'side': side,
                'shares': shares,
                'price': price,
                'cost': cost,
            })
            
            if side == 'buy':
                total_cost += cost
    
    if not source_trades:
        return None
    
    # 计算 USDC 返还和净成本
    num_markets = len(set(t['condition_id'] for t in source_trades))
    usdc_returned = (num_markets - 1) * min(t['shares'] for t in source_trades) if num_markets > 1 else 0
    net_cost = total_cost - usdc_returned
    
    return {
        'source_trades': source_trades,
        'conversion_cost': total_cost,
        'usdc_returned': usdc_returned,
        'net_cost': net_cost,
    }


def get_tx_receipt(tx_hash: str) -> Optional[Dict]:
    """
    获取交易收据
    
    Args:
        tx_hash: 交易哈希
        
    Returns:
        dict: 交易收据
    """
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getTransactionReceipt",
            "params": [tx_hash],
            "id": 1
        }
        resp = requests.post(POLYGON_RPC_URL, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json().get('result')
    except Exception as e:
        print(f"[Neg-Risk] 获取交易收据失败: {e}")
        return None


def parse_order_filled_events(logs: List[Dict], user_address: str) -> List[Dict]:
    """
    从交易日志中解析 OrderFilled 事件
    
    Args:
        logs: 交易日志列表
        user_address: 用户地址
        
    Returns:
        list: 用户参与的订单列表
    """
    user_lower = user_address.lower()
    orders = []
    
    for log in logs:
        topics = log.get('topics', [])
        if not topics:
            continue
        
        # 检查是否是 OrderFilled 事件
        if topics[0].lower() != EVENT_TOPICS['ORDER_FILLED'].lower():
            continue
        
        if len(topics) < 4:
            continue
        
        # 解析 maker 和 taker 地址
        maker = '0x' + topics[2][-40:].lower()
        taker = '0x' + topics[3][-40:].lower()
        
        # 检查用户是否参与
        if user_lower not in [maker, taker]:
            continue
        
        # 解析 data 字段获取 assetId 和 amount
        data = log.get('data', '0x')
        order_info = {
            'contract': log.get('address', '').lower(),
            'maker': maker,
            'taker': taker,
            'role': 'MAKER' if user_lower == maker else 'TAKER',
            'data': data,
        }
        
        orders.append(order_info)
    
    return orders


# =============================================================================
# Step 3: 数据整合函数
# =============================================================================

def enrich_trade_with_source(
    trade: Dict,
    user_address: str,
    target_condition_id: str,
    event_slug: str = None,
    all_condition_ids: List[str] = None,
    condition_map: Dict[str, Dict] = None
) -> ActivityRecord:
    """
    分析并丰富交易数据，添加来源信息
    
    Args:
        trade: 原始交易数据 (来自 trades API 或 activity API)
        user_address: 用户地址
        target_condition_id: 目标市场的 conditionId
        event_slug: 事件 slug (可选，如果不提供则不进行 neg-risk 分析)
        all_condition_ids: 所有子市场的 conditionId (可选，会自动获取)
        condition_map: conditionId 到市场信息的映射 (可选，会自动获取)
        
    Returns:
        ActivityRecord: 丰富后的交易记录
    """
    # 创建基础记录
    record = ActivityRecord(
        timestamp=trade.get("timestamp", 0),
        tx_hash=trade.get("transactionHash", ""),
        side=trade.get("side", "").upper(),
        outcome=trade.get("outcome", ""),
        shares=float(trade.get("size", 0) or 0),
        price=float(trade.get("price", 0) or 0),
        raw_data=trade.copy()
    )
    
    # 计算方向和成本
    record.direction = "in" if record.side == "BUY" else "out"
    record.cost = record.shares * record.price
    
    # 如果没有提供 event_slug，默认为 direct
    if not event_slug:
        record.source = "direct"
        return record
    
    # 获取所有子市场 conditionId
    if all_condition_ids is None:
        all_condition_ids = get_event_condition_ids(event_slug)
    
    # 如果只有一个子市场，肯定是 direct
    if len(all_condition_ids) <= 1:
        record.source = "direct"
        return record
    
    # 分析交易来源
    tx_hash = record.tx_hash
    if tx_hash:
        source, source_details = analyze_trade_source(
            tx_hash, user_address, target_condition_id, all_condition_ids
        )
        record.source = source
        
        # 保存来源详情 (Transfer 的 counterparty, Split/Merge 的 shares 等)
        if source_details:
            if 'counterparty' in source_details:
                record.counterparty = source_details['counterparty']
        
        # 如果是 neg-risk，解析详情
        if source == "neg_risk":
            if condition_map is None:
                condition_map = get_condition_to_market_map(event_slug)
            
            details = parse_neg_risk_details(tx_hash, user_address, condition_map)
            if details:
                record.conversion_cost = details.get('conversion_cost', 0)
                record.usdc_returned = details.get('usdc_returned', 0)
                record.net_cost = details.get('net_cost', 0)
                
                for st in details.get('source_trades', []):
                    record.source_trades.append(SourceTrade(
                        market_name=st.get('market_name', ''),
                        condition_id=st.get('condition_id', ''),
                        outcome=st.get('outcome', ''),
                        side=st.get('side', ''),
                        shares=st.get('shares', 0),
                        price=st.get('price', 0),
                        cost=st.get('cost', 0),
                    ))
    else:
        record.source = "unknown"
    
    return record


def enrich_trades_batch(
    trades: List[Dict],
    user_address: str,
    target_condition_id: str,
    event_slug: str = None
) -> Tuple[List[ActivityRecord], Dict[str, int]]:
    """
    批量分析交易数据，添加来源信息
    
    Args:
        trades: 原始交易数据列表
        user_address: 用户地址
        target_condition_id: 目标市场的 conditionId
        event_slug: 事件 slug (可选)
        
    Returns:
        (enriched_trades, source_stats): 丰富后的交易列表和来源统计
    """
    if not trades:
        return [], {}
    
    # 预先获取所有需要的数据，避免重复请求
    all_condition_ids = None
    condition_map = None
    
    if event_slug:
        all_condition_ids = get_event_condition_ids(event_slug)
        if len(all_condition_ids) > 1:
            condition_map = get_condition_to_market_map(event_slug)
    
    # 批量处理
    enriched = []
    source_stats = {
        'direct': 0,
        'neg_risk': 0,
        'split': 0,
        'merge': 0,
        'transfer': 0,
        'redeem': 0,
        'unknown': 0
    }
    
    for trade in trades:
        record = enrich_trade_with_source(
            trade, user_address, target_condition_id,
            event_slug, all_condition_ids, condition_map
        )
        enriched.append(record)
        source_stats[record.source] = source_stats.get(record.source, 0) + 1
    
    return enriched, source_stats


def records_to_legacy_format(records: List[ActivityRecord]) -> List[Dict]:
    """
    将 ActivityRecord 列表转换为现有代码兼容的格式
    
    Args:
        records: ActivityRecord 列表
        
    Returns:
        list: 兼容现有代码的字典列表
    """
    return [r.to_legacy_format() for r in records]


# =============================================================================
# Step 4: 链上持仓查询和 Convert 事件解析 (v2.0 新增)
# =============================================================================

def get_user_token_balance(user_address: str, token_id: str) -> float:
    """
    查询用户在 CTF 合约中的 token 余额
    
    Args:
        user_address: 用户钱包地址
        token_id: token ID (十进制字符串或十六进制)
        
    Returns:
        float: 余额 (已除以 1e6)
    """
    ctf_address = CONTRACTS['CTF']
    
    # 确保 token_id 是十六进制格式
    if not token_id.startswith('0x'):
        token_id_hex = hex(int(token_id))
    else:
        token_id_hex = token_id
    
    # balanceOf(address,uint256) 函数签名
    # keccak256("balanceOf(address,uint256)")[:4] = 0x00fdd58e
    func_selector = "0x00fdd58e"
    
    # 编码参数
    user_padded = user_address.lower().replace('0x', '').zfill(64)
    token_padded = token_id_hex.replace('0x', '').zfill(64)
    
    call_data = func_selector + user_padded + token_padded
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [
                {"to": ctf_address, "data": call_data},
                "latest"
            ],
            "id": 1
        }
        resp = requests.post(POLYGON_RPC_URL, json=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json().get('result', '0x0')
        
        balance_wei = int(result, 16)
        return balance_wei / 1e6  # CTF token 有 6 位小数
        
    except Exception as e:
        print(f"[Neg-Risk] 查询余额失败: {e}")
        return 0.0


def get_user_market_positions(user_address: str, condition_id: str) -> Dict[str, float]:
    """
    查询用户在某个市场的 Yes/No 持仓
    
    Args:
        user_address: 用户钱包地址
        condition_id: 市场的 conditionId
        
    Returns:
        dict: {'yes': float, 'no': float}
    """
    token_ids = get_market_token_ids(condition_id)
    
    positions = {'yes': 0.0, 'no': 0.0}
    
    for outcome, token_hex in token_ids.items():
        # token_hex 是64位十六进制，转为十进制
        token_id_int = int(token_hex, 16)
        balance = get_user_token_balance(user_address, str(token_id_int))
        positions[outcome] = balance
    
    return positions


def get_user_positions_for_event(user_address: str, event_slug: str) -> List[Dict]:
    """
    查询用户在某个 event 下所有子市场的持仓
    
    Args:
        user_address: 用户钱包地址
        event_slug: 事件 slug
        
    Returns:
        list: [{'condition_id': str, 'question': str, 'yes': float, 'no': float}, ...]
    """
    condition_map = get_condition_to_market_map(event_slug)
    
    if not condition_map:
        return []
    
    results = []
    
    for cid, info in condition_map.items():
        positions = get_user_market_positions(user_address, cid)
        
        # 只返回有持仓的市场
        if positions['yes'] > 0 or positions['no'] > 0:
            results.append({
                'condition_id': cid,
                'question': info.get('question', ''),
                'outcomes': info.get('outcomes', '["Yes", "No"]'),
                'is_resolved': info.get('closed', False),
                'yes_shares': positions['yes'],
                'no_shares': positions['no'],
            })
    
    return results


def get_convert_events_for_user(
    user_address: str,
    market_id: str = None,
    from_block: int = 50000000,
    to_block: str = "latest"
) -> List[Dict]:
    """
    查询用户的 PositionsConverted 事件
    
    Args:
        user_address: 用户钱包地址
        market_id: 可选，过滤特定 marketId
        from_block: 起始区块
        to_block: 结束区块
        
    Returns:
        list: Convert 事件列表
    """
    neg_risk_adapter = CONTRACTS['NEG_RISK_ADAPTER']
    topic0 = EVENT_TOPICS['POSITIONS_CONVERTED']
    
    # topic1 是 indexed stakeholder (用户地址)
    user_topic = '0x' + user_address.lower().replace('0x', '').zfill(64)
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getLogs",
            "params": [{
                "address": neg_risk_adapter,
                "topics": [topic0, user_topic],
                "fromBlock": hex(from_block),
                "toBlock": to_block
            }],
            "id": 1
        }
        resp = requests.post(POLYGON_RPC_URL, json=payload, timeout=30)
        resp.raise_for_status()
        logs = resp.json().get('result', [])
        
        events = []
        for log in logs:
            topics = log.get('topics', [])
            data = log.get('data', '0x')[2:]
            
            if len(topics) < 4:
                continue
            
            # PositionsConverted(address indexed stakeholder, bytes32 indexed marketId, uint256 indexed indexSet, uint256 amount)
            # topics[1] = stakeholder, topics[2] = marketId, topics[3] = indexSet
            # data = amount
            
            event_market_id = topics[2].lower()
            index_set = int(topics[3], 16)
            amount = int(data, 16) / 1e6 if data else 0
            
            # 如果指定了 marketId 过滤
            if market_id and event_market_id != market_id.lower():
                continue
            
            events.append({
                'tx_hash': log.get('transactionHash', ''),
                'block_number': int(log.get('blockNumber', '0x0'), 16),
                'market_id': event_market_id,
                'index_set': index_set,
                'amount': amount,
                'user': user_address,
            })
        
        return events
        
    except Exception as e:
        print(f"[Neg-Risk] 查询 Convert 事件失败: {e}")
        return []


def get_block_timestamp(block_number: int) -> int:
    """
    获取区块的时间戳
    
    Args:
        block_number: 区块号
        
    Returns:
        int: Unix 时间戳
    """
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBlockByNumber",
            "params": [hex(block_number), False],
            "id": 1
        }
        resp = requests.post(POLYGON_RPC_URL, json=payload, timeout=15)
        resp.raise_for_status()
        block = resp.json().get('result', {})
        return int(block.get('timestamp', '0x0'), 16)
    except:
        return 0


def parse_convert_event_details(
    event: Dict,
    condition_map: Dict[str, Dict]
) -> Dict:
    """
    解析 Convert 事件的详细信息
    
    根据 indexSet 确定哪些市场的 NO 被转换成了哪些市场的 YES
    
    Args:
        event: Convert 事件
        condition_map: conditionId 到市场信息的映射
        
    Returns:
        dict: {
            'no_markets': [...],  # 被销毁 NO 的市场
            'yes_markets': [...],  # 获得 YES 的市场
            'amount': float,
            'usdc_returned': float,
        }
    """
    index_set = event['index_set']
    amount = event['amount']
    market_id = event['market_id']
    
    # 根据 market_id 找到对应的子市场
    # index_set 的每一位表示一个子市场的 NO 是否被转换
    # 例如 indexSet = 0b11010 表示第1、3、4个市场的 NO 被转换
    
    no_markets = []  # 被销毁 NO 的市场
    yes_markets = []  # 获得 YES 的市场
    
    # 遍历所有子市场
    sorted_cids = sorted(condition_map.keys())
    for i, cid in enumerate(sorted_cids):
        if (index_set >> i) & 1:
            # 这个市场的 NO 被销毁
            no_markets.append({
                'condition_id': cid,
                'question': condition_map[cid].get('question', ''),
                'outcome': 'No',
                'shares': amount,
            })
        else:
            # 这个市场获得 YES
            yes_markets.append({
                'condition_id': cid,
                'question': condition_map[cid].get('question', ''),
                'outcome': 'Yes',
                'shares': amount,
            })
    
    # 返还的 USDC = (NO市场数量 - 1) * amount
    usdc_returned = (len(no_markets) - 1) * amount if len(no_markets) > 1 else 0
    
    return {
        'no_markets': no_markets,
        'yes_markets': yes_markets,
        'amount': amount,
        'usdc_returned': usdc_returned,
        'index_set': index_set,
    }


def get_user_all_activity(
    user_address: str,
    event_slug: str,
    target_condition_id: str = None
) -> Tuple[List[Dict], Dict[str, int]]:
    """
    获取用户在某个 event 下的所有活动（包括 Convert 事件）
    
    这是新的核心函数，整合了:
    1. Trades API 的直接交易
    2. Activity API 的持仓变动
    3. 链上 Convert 事件
    
    Args:
        user_address: 用户钱包地址
        event_slug: 事件 slug
        target_condition_id: 目标子市场的 conditionId
        
    Returns:
        Tuple[活动列表, 来源统计]
    """
    all_activities = []
    source_stats = {
        'direct': 0,
        'convert': 0,
        'unknown': 0,
    }
    
    # 1. 获取 Convert 事件
    condition_map = get_condition_to_market_map(event_slug)
    convert_events = get_convert_events_for_user(user_address)
    
    for event in convert_events:
        timestamp = get_block_timestamp(event['block_number'])
        details = parse_convert_event_details(event, condition_map)
        
        # 为每个获得 YES 的市场创建一条活动记录
        for yes_market in details['yes_markets']:
            # 如果指定了目标市场，只记录目标市场的活动
            if target_condition_id and yes_market['condition_id'].lower() != target_condition_id.lower():
                continue
                
            activity = {
                'transactionHash': event['tx_hash'],
                'timestamp': timestamp,
                'side': 'BUY',
                'size': str(yes_market['shares']),
                'price': '0',  # Convert 没有价格概念
                'outcome': 'Yes',
                'source': 'convert',
                'convert_details': {
                    'no_markets': details['no_markets'],
                    'usdc_returned': details['usdc_returned'],
                    'index_set': details['index_set'],
                },
            }
            all_activities.append(activity)
            source_stats['convert'] += 1
    
    return all_activities, source_stats


# =============================================================================
# Step 5: 完整链上事件查询 (v3.25 新增)
# =============================================================================

def get_user_chain_events(
    user_address: str,
    from_block: int = 50000000,
    to_block: str = "latest"
) -> List[Dict]:
    """
    查询用户的所有链上事件 (Split/Merge/Redeem/Convert/Transfer)
    
    通过分析用户的交易收据来获取事件，而不是直接查 eth_getLogs
    (因为事件的 topic 中不一定包含用户地址)
    
    Args:
        user_address: 用户钱包地址
        from_block: 起始区块 (默认 50000000)
        to_block: 结束区块 (默认 latest)
        
    Returns:
        list: 事件列表，每个事件包含 type, tx_hash, block, timestamp, details
    """
    events = []
    
    # 1. 从 Activity API 获取用户的所有交易哈希
    try:
        resp = requests.get(
            f'https://data-api.polymarket.com/activity?user={user_address}&limit=1000',
            timeout=30
        )
        activities = resp.json() if resp.status_code == 200 else []
    except:
        activities = []
    
    # 收集所有交易哈希，并记录哪些交易包含 TRADE
    # v3.27: 用于过滤 Neg-Risk 内部的 Split/Merge（与 TRADE 在同一交易中的不应该重复显示）
    tx_hashes = set()
    tx_with_trade = set()  # 包含 TRADE 类型的交易
    for a in activities:
        tx = a.get('transactionHash', '')
        if tx:
            tx_hashes.add(tx)
            if a.get('type') == 'TRADE':
                tx_with_trade.add(tx.lower())
    
    print(f"[链上事件] 找到 {len(tx_hashes)} 笔交易待分析")
    
    # 2. 分析每笔交易的事件
    ctf_address = CONTRACTS['CTF']
    neg_risk_adapter = CONTRACTS['NEG_RISK_ADAPTER']
    
    for tx_hash in tx_hashes:
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getTransactionReceipt",
                "params": [tx_hash],
                "id": 1
            }
            resp = requests.post(POLYGON_RPC_URL, json=payload, timeout=15)
            receipt = resp.json().get('result', {})
            
            if not receipt:
                continue
            
            block_number = int(receipt.get('blockNumber', '0x0'), 16)
            logs = receipt.get('logs', [])
            
            for log in logs:
                topic0 = log['topics'][0] if log['topics'] else ''
                addr = log['address'].lower()
                
                event_type = None
                event_details = {}
                
                # 识别事件类型
                if topic0 == EVENT_TOPICS['POSITION_SPLIT'] and addr == ctf_address:
                    # v3.27: 跳过与 TRADE 在同一交易中的 Split（Neg-Risk 内部机制）
                    if tx_hash.lower() in tx_with_trade:
                        continue
                    event_type = 'split'
                    event_details = _parse_split_event(log, user_address)
                    
                elif topic0 == EVENT_TOPICS['POSITIONS_MERGE'] and addr == ctf_address:
                    # v3.27: 跳过与 TRADE 在同一交易中的 Merge（Neg-Risk 内部机制）
                    if tx_hash.lower() in tx_with_trade:
                        continue
                    event_type = 'merge'
                    event_details = _parse_merge_event(log, user_address)
                    
                elif topic0 == EVENT_TOPICS['PAYOUT_REDEMPTION'] and addr == ctf_address:
                    event_type = 'redeem'
                    event_details = _parse_redeem_event(log, user_address)
                    
                elif topic0 == EVENT_TOPICS['POSITIONS_CONVERTED'] and addr == neg_risk_adapter:
                    event_type = 'convert'
                    event_details = _parse_convert_event(log, user_address)
                
                if event_type and event_details.get('is_user_involved', False):
                    events.append({
                        'type': event_type,
                        'tx_hash': tx_hash,
                        'block': block_number,
                        'timestamp': 0,  # 稍后批量获取
                        'details': event_details,
                    })
                    
        except Exception as e:
            print(f"[链上事件] 分析交易 {tx_hash[:20]}... 失败: {e}")
            continue
    
    # 3. 批量获取时间戳
    blocks_to_fetch = set(e['block'] for e in events)
    block_timestamps = {}
    
    for block in blocks_to_fetch:
        ts = get_block_timestamp(block)
        block_timestamps[block] = ts
    
    for event in events:
        event['timestamp'] = block_timestamps.get(event['block'], 0)
    
    # 按时间排序
    events.sort(key=lambda x: x['timestamp'])
    
    print(f"[链上事件] 共找到 {len(events)} 个 Split/Merge/Redeem/Convert 事件")
    
    return events


def _parse_split_event(log: Dict, user_address: str) -> Dict:
    """
    解析 PositionSplit 事件
    
    PositionSplit(address stakeholder, address collateralToken, bytes32 parentCollectionId, 
                  bytes32 conditionId, uint256[] partition, uint256 amount)
    
    Topics: [event_sig, stakeholder_indexed, parentCollectionId, conditionId]
    Data: [collateralToken, offset, amount, partition长度, partition[0], partition[1]]
    
    注意: stakeholder 通常是 NegRiskAdapter，不是用户地址
    我们通过交易来源（Activity API）确认属于用户，不需要在这里验证
    """
    topics = log.get('topics', [])
    data = log.get('data', '0x')[2:]
    
    # stakeholder 在 topic1
    stakeholder = ''
    if len(topics) > 1:
        stakeholder = '0x' + topics[1][-40:]
    
    # conditionId 在 topic3
    condition_id = ''
    if len(topics) > 3:
        condition_id = topics[3]
    
    # 解析 amount - 在第 3 个 32 字节块 (索引 2)
    amount = 0.0
    if len(data) >= 64 * 3:
        try:
            amount = int(data[128:192], 16) / 1e6
        except:
            pass
    
    return {
        'is_user_involved': True,
        'stakeholder': stakeholder,
        'condition_id': condition_id,
        'amount': amount,
        'shares': amount,  # Split 的份额等于金额
        'description': f'拆分 ${amount:.2f} USDC 为 Yes+No',
    }


def _parse_merge_event(log: Dict, user_address: str) -> Dict:
    """
    解析 PositionsMerge 事件
    
    PositionsMerge(address stakeholder, address collateralToken, bytes32 parentCollectionId,
                   bytes32 conditionId, uint256[] partition, uint256 amount)
    
    注意: stakeholder 通常是 NegRiskAdapter，不是用户地址
    Data 结构与 Split 相同
    """
    topics = log.get('topics', [])
    data = log.get('data', '0x')[2:]
    
    stakeholder = ''
    if len(topics) > 1:
        stakeholder = '0x' + topics[1][-40:]
    
    # conditionId 在 topic3
    condition_id = ''
    if len(topics) > 3:
        condition_id = topics[3]
    
    # amount 在第 3 个 32 字节块 (索引 2)
    amount = 0.0
    if len(data) >= 64 * 3:
        try:
            amount = int(data[128:192], 16) / 1e6
        except:
            pass
    
    return {
        'is_user_involved': True,
        'stakeholder': stakeholder,
        'condition_id': condition_id,
        'amount': amount,
        'shares': amount,
        'description': f'合并 Yes+No 回收 ${amount:.2f} USDC',
    }


def _parse_redeem_event(log: Dict, user_address: str) -> Dict:
    """
    解析 PayoutRedemption 事件 (CTF 合约)
    
    PayoutRedemption(address indexed redeemer, address indexed collateralToken, 
                     bytes32 indexed parentCollectionId, bytes32 conditionId, 
                     uint256[] indexSets, uint256 payout)
    
    Topics: [event_sig, redeemer, collateralToken, parentCollectionId]
    Data: [conditionId (32 bytes), indexSets offset, payout, indexSets length, ...]
    
    v3.27: 修正 conditionId 解析位置 - 在 data[0:64]，不是 topics[2]
    """
    topics = log.get('topics', [])
    data = log.get('data', '0x')[2:]
    
    redeemer = ''
    if len(topics) > 1:
        redeemer = '0x' + topics[1][-40:]
    
    # v3.27: conditionId 在 data 的第一个 32 字节块
    condition_id = ''
    if len(data) >= 64:
        condition_id = '0x' + data[0:64]
    
    # payout 在第 3 个 32 字节块 (索引 2)
    amount = 0.0
    if len(data) >= 64 * 3:
        try:
            amount = int(data[128:192], 16) / 1e6
        except:
            pass
    
    return {
        'is_user_involved': True,
        'redeemer': redeemer,
        'condition_id': condition_id,
        'amount': amount,
        'shares': 0,  # Redeem 不涉及份额变化，只有金额
        'description': f'结算赎回 ${amount:.2f} USDC',
    }


def _parse_convert_event(log: Dict, user_address: str) -> Dict:
    """
    解析 PositionsConverted 事件 (NegRiskAdapter)
    
    PositionsConverted(address indexed stakeholder, bytes32 indexed marketId, 
                       uint256 indexed indexSet, uint256 amount)
    
    注意: stakeholder 可能是用户地址
    """
    topics = log.get('topics', [])
    data = log.get('data', '0x')[2:]
    
    stakeholder = ''
    if len(topics) > 1:
        stakeholder = '0x' + topics[1][-40:]
    
    index_set = 0
    if len(topics) > 3:
        index_set = int(topics[3], 16)
    
    amount = 0.0
    if len(data) >= 64:
        try:
            amount = int(data[:64], 16) / 1e6
        except:
            pass
    
    return {
        'is_user_involved': True,  # 总是 True，因为交易来自 Activity API
        'stakeholder': stakeholder,
        'index_set': index_set,
        'amount': amount,
        'description': f'Convert {amount:.2f} 份 (indexSet={index_set})',
    }


def get_user_all_chain_activity(
    user_address: str,
    event_slug: str = None
) -> Tuple[List[Dict], Dict[str, int]]:
    """
    获取用户的完整链上活动记录
    
    整合:
    1. Activity API 的交易记录
    2. 链上 Split/Merge/Redeem/Convert 事件
    
    Args:
        user_address: 用户钱包地址
        event_slug: 可选，过滤特定 event
        
    Returns:
        Tuple[活动列表, 来源统计]
    """
    all_records = []
    source_stats = {
        'trade': 0,
        'split': 0,
        'merge': 0,
        'redeem': 0,
        'convert': 0,
        'transfer': 0,
    }
    
    # 1. 获取 Activity API 记录 (包含交易)
    try:
        resp = requests.get(
            f'https://data-api.polymarket.com/activity?user={user_address}&limit=1000',
            timeout=30
        )
        activities = resp.json() if resp.status_code == 200 else []
    except:
        activities = []
    
    # Activity 记录转换
    for a in activities:
        if a.get('type') == 'TRADE':
            record = {
                'type': 'trade',
                'tx_hash': a.get('transactionHash', ''),
                'timestamp': a.get('timestamp', 0),
                'condition_id': a.get('conditionId', ''),
                'side': a.get('side', ''),
                'outcome': a.get('outcome', ''),
                'size': float(a.get('size', 0)),
                'price': float(a.get('price', 0)),
                'description': f"{a.get('side', '')} {a.get('size', 0)} {a.get('outcome', '')} @ {a.get('price', 0)}",
            }
            all_records.append(record)
            source_stats['trade'] += 1
    
    # 2. 获取链上事件
    chain_events = get_user_chain_events(user_address)
    
    for event in chain_events:
        event_type = event['type']
        details = event.get('details', {})
        record = {
            'type': event_type,
            'tx_hash': event['tx_hash'],
            'timestamp': event['timestamp'],
            'condition_id': details.get('condition_id', ''),
            'side': '',
            'outcome': '',
            'size': details.get('amount', 0),
            'shares': details.get('shares', 0),
            'price': 0,
            'description': details.get('description', ''),
        }
        all_records.append(record)
        source_stats[event_type] = source_stats.get(event_type, 0) + 1
    
    # 3. 去重 (同一笔交易可能同时在 activity 和链上事件中)
    seen_tx = {}
    unique_records = []
    
    for record in all_records:
        tx = record['tx_hash']
        record_type = record['type']
        key = f"{tx}_{record_type}"
        
        if key not in seen_tx:
            seen_tx[key] = True
            unique_records.append(record)
    
    # 按时间排序
    unique_records.sort(key=lambda x: x['timestamp'])
    
    return unique_records, source_stats


def get_chain_events_by_condition(user_address: str, condition_id: str) -> List[Dict]:
    """
    获取指定市场的链上事件 (Split/Merge/Redeem)
    
    Args:
        user_address: 用户钱包地址
        condition_id: 市场的 conditionId
        
    Returns:
        该市场的链上事件列表，格式化为类似交易记录的结构
    """
    all_events = get_user_chain_events(user_address)
    
    # 标准化 condition_id 比较 (去掉 0x 前缀，转小写)
    target_cid = condition_id.lower().replace('0x', '')
    
    result = []
    for event in all_events:
        event_cid = event.get('details', {}).get('condition_id', '')
        event_cid_normalized = event_cid.lower().replace('0x', '')
        
        if event_cid_normalized == target_cid:
            event_type = event['type']
            details = event.get('details', {})
            
            # 转换为类似交易记录的格式
            record = {
                'source': event_type.capitalize(),  # Split / Merge / Redeem
                'timestamp': event.get('timestamp', 0),
                'tx_hash': event.get('tx_hash', ''),
                'amount': details.get('amount', 0),
                'shares': details.get('shares', 0),
                'description': details.get('description', ''),
                'type': event_type,
            }
            
            # 为不同类型设置方向
            if event_type == 'split':
                record['direction'] = '+Yes +No'
                record['cost'] = -details.get('amount', 0)  # 花费
            elif event_type == 'merge':
                record['direction'] = '-Yes -No'
                record['cost'] = details.get('amount', 0)  # 回收
            elif event_type == 'redeem':
                record['direction'] = '-Position'
                record['cost'] = details.get('amount', 0)  # 赎回收益
            
            result.append(record)
    
    # 按时间排序
    result.sort(key=lambda x: x.get('timestamp', 0))
    
    return result


# =============================================================================
# 测试函数
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # 测试 Step 1 函数
    print("=" * 60)
    print("Neg-Risk 模块测试")
    print("=" * 60)
    
    # 测试 1: 判断 neg-risk 市场
    test_slug = "fed-decision-in-january"
    print(f"\n[Step 1] 测试 1: is_neg_risk_market('{test_slug}')")
    result = is_neg_risk_market(test_slug)
    print(f"  结果: {result}")
    
    # 测试 2: 获取 conditionId 列表
    print(f"\n[Step 1] 测试 2: get_event_condition_ids('{test_slug}')")
    cids = get_event_condition_ids(test_slug)
    print(f"  找到 {len(cids)} 个子市场:")
    for cid in cids:
        print(f"    - {cid[:30]}...")
    
    # 测试 3: 获取 conditionId 到市场名映射
    print(f"\n[Step 1] 测试 3: get_condition_to_market_map('{test_slug}')")
    cmap = get_condition_to_market_map(test_slug)
    print(f"  映射关系:")
    for cid, info in cmap.items():
        print(f"    - {cid[:20]}... -> {info['question'][:40]}...")
    
    # 测试 4: URL 解析
    print("\n[Step 1] 测试 4: extract_event_slug_from_url()")
    test_urls = [
        "https://polymarket.com/event/fed-decision-in-january",
        "https://polymarket.com/event/fed-decision-in-january/no-change",
        "https://polymarket.com/event/bitcoin-above-on-january-12?tid=123",
    ]
    for url in test_urls:
        slug = extract_event_slug_from_url(url)
        print(f"  {url}")
        print(f"    -> {slug}")
    
    print("\n" + "=" * 60)
    print("Step 1 测试完成")
    print("=" * 60)
    
    # Step 2 测试
    print("\n" + "=" * 60)
    print("Step 2: 链上分析函数测试")
    print("=" * 60)
    
    # 测试用的交易和用户
    test_tx = "0x0ded7f2743f186ab47abbbc827a276ca7b282babf70e96378934bf96cd58219a"
    test_user = "0x3b6e39291ec33c49624c38a999cce5fa4c27b070"
    test_event_slug = "bitcoin-above-on-january-12"
    target_cid = "0x7bb1a00a27a5bd6ddc57d05e913e5a4484beddd5f151f28a2cd8452a958b7685"  # Bitcoin 84k
    
    # 测试 5: 获取 token IDs
    print(f"\n[Step 2] 测试 5: get_market_token_ids()")
    token_ids = get_market_token_ids(target_cid)
    print(f"  Bitcoin 84k market tokens:")
    for outcome, tid in token_ids.items():
        print(f"    {outcome}: {tid[:30]}...")
    
    # 测试 6: 获取所有子市场 condition IDs
    print(f"\n[Step 2] 测试 6: 获取 event 所有子市场")
    all_cids = get_event_condition_ids(test_event_slug)
    print(f"  找到 {len(all_cids)} 个子市场")
    
    # 测试 7: 分析交易来源
    print(f"\n[Step 2] 测试 7: analyze_trade_source()")
    print(f"  交易: {test_tx[:20]}...")
    print(f"  用户: {test_user}")
    print(f"  目标市场: Bitcoin 84k")
    
    source, source_details = analyze_trade_source(test_tx, test_user, target_cid, all_cids)
    print(f"  来源类型: {source}")
    print(f"  来源详情: {source_details}")
    
    # 测试 8: 解析交易详情
    print(f"\n[Step 2] 测试 8: parse_neg_risk_details()")
    condition_map = get_condition_to_market_map(test_event_slug)
    details = parse_neg_risk_details(test_tx, test_user, condition_map)
    
    if details:
        print(f"  源交易数量: {len(details['source_trades'])}")
        for i, trade in enumerate(details['source_trades']):
            print(f"    #{i+1}: {trade['market_name'][:40]}...")
            print(f"        {trade['side']} {trade['outcome']} {trade['shares']:.2f} @ {trade['price']:.4f}")
        print(f"  转换总成本: ${details['conversion_cost']:.2f}")
        print(f"  USDC 返还: ${details['usdc_returned']:.2f}")
        print(f"  净成本: ${details['net_cost']:.2f}")
    else:
        print("  无法解析交易详情")
    
    print("\n" + "=" * 60)
    print("Step 2 测试完成")
    print("=" * 60)

    
    # Step 3 测试
    print("\n" + "=" * 60)
    print("Step 3: 数据整合函数测试")
    print("=" * 60)
    
    # 测试 9: 模拟一笔交易数据进行丰富
    print("\n[Step 3] 测试 9: enrich_trade_with_source()")
    mock_trade = {
        "transactionHash": test_tx,
        "timestamp": 1736654400,
        "side": "BUY",
        "size": "2564",
        "price": "0.999",
        "outcome": "Yes",
    }
    
    record = enrich_trade_with_source(
        mock_trade, test_user, target_cid, test_event_slug
    )
    
    print(f"  交易来源: {record.source}")
    print(f"  方向: {record.direction}")
    print(f"  份额: {record.shares}")
    print(f"  价格: {record.price}")
    print(f"  成本: ${record.cost:.2f}")
    if record.source_trades:
        print(f"  源交易数量: {len(record.source_trades)}")
    
    # 测试 10: 批量处理
    print("\n[Step 3] 测试 10: enrich_trades_batch()")
    mock_trades = [mock_trade]
    
    records, stats = enrich_trades_batch(
        mock_trades, test_user, target_cid, test_event_slug
    )
    
    print(f"  处理交易数: {len(records)}")
    print(f"  来源统计:")
    for src, count in stats.items():
        if count > 0:
            print(f"    {src}: {count}")
    
    # 测试 11: 转换为旧格式
    print("\n[Step 3] 测试 11: records_to_legacy_format()")
    legacy = records_to_legacy_format(records)
    if legacy:
        first = legacy[0]
        print("  第一条记录:")
        tx_hash_str = first.get('transactionHash', '')
        print(f"    transactionHash: {tx_hash_str[:30]}...")
        print(f"    source: {first.get('source')}")
        print(f"    side: {first.get('side')}")
    
    print("\n" + "=" * 60)
    print("Step 3 测试完成")
    print("=" * 60)
