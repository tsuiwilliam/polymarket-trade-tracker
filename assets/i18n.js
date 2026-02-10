// 国际化配置文件
const I18N = {
    zh: {
        // 导航
        nav_quick_query: '快速查询',
        nav_multi_query: '多选项市场查询',
        nav_trader: '交易员分析',
        lang_toggle: '中文',
        
        // 首页
        home_subtitle: '分析每笔交易的 Maker/Taker 角色 · 持仓敞口曲线追踪 · 自动生成盈亏分析报告',
        home_quick_title: '快速查询',
        home_quick_desc: '输入市场名称和钱包地址，快速获取交易分析报告。适用于大多数二元市场。',
        home_multi_title: '多选项市场查询',
        home_multi_desc: '通过市场 URL 查询包含多个子选项的市场，选择具体子市场进行分析。',
        home_start_query: '开始查询',
        home_instructions: '使用说明',
        home_step1_title: '选择查询模式',
        home_step1_desc: '普通市场选择快速查询，多选项市场选择子市场查询',
        home_step2_title: '输入查询信息',
        home_step2_desc: '输入市场名称或 URL，以及要分析的钱包地址',
        home_step3_title: '获取分析报告',
        home_step3_desc: '查看 Maker/Taker 角色、持仓敞口、盈亏报告',
        home_footer: '本工具完全免费，请点击右上角 X 图标关注作者获取更多免费工具与更新。',
        home_notice_line1: '支持查询绝大部分市场',
        home_notice_line2: '仅 Sports 板块 Games 类型市场未支持（如：某队 vs 某队）',
        
        // 快速查询页
        simple_title: '快速查询',
        simple_subtitle: '输入市场名称和钱包地址，快速获取交易分析报告。适用于大多数二元市场。',
        simple_market_label: '市场名称',
        simple_market_placeholder: '例如: Bitcoin Up or Down - January 8',
        simple_wallet_label: '钱包地址',
        simple_wallet_placeholder: '0x...',
        simple_btn_analyze: '开始分析',
        simple_hint: '输入市场名称和钱包地址，获取完整的交易分析报告',
        simple_progress_fetching: '正在获取交易数据...',
        simple_progress_analyzing: '正在分析 Maker/Taker 角色...',
        simple_discover_link: '自动发现每日 96 个加密市场？前往交易员分析',
        simple_btn_cancel: '取消查询',
        simple_btn_new_query: '新查询',
        simple_download_chart: '图表',
        simple_download_report: '报告',
        simple_download_data: '数据',
        
        // 多选项查询页
        multi_title: '多选项市场查询',
        multi_subtitle: '通过市场 URL 查询包含多个子选项的市场，选择具体子市场进行分析。',
        multi_input_title: '输入信息',
        multi_chain_title: '链上操作记录',
        multi_url_label: '市场 URL',
        multi_url_placeholder: '例如: https://polymarket.com/event/...',
        multi_wallet_label: '钱包地址',
        multi_wallet_placeholder: '0x...',
        multi_btn_fetch: '获取子市场列表',
        multi_hint: '输入市场 URL 和钱包地址，获取该用户在此事件下的所有交易市场',
        multi_select_title: '选择用户交易过的子市场（可多选）',
        multi_select_all: '全选',
        multi_deselect_all: '取消全选',
        multi_selected_count: '已选择 {n} 个',
        multi_btn_back: '返回修改',
        multi_btn_analyze: '开始分析',
        multi_analyzing: '批量分析中',
        multi_progress_info: '正在分析第 {current} / {total} 个市场: {name}',
        multi_btn_cancel: '取消分析',
        multi_btn_reset: '重新查询',
        multi_trades_count: '{n} 笔交易',
        
        // 结果展示
        result_trade_count: '总交易笔数',
        result_net_exposure: '净敞口',
        result_final_value: '最终价值',
        result_pnl: '最终盈亏',
        result_settlement: '结算',
        result_unsettled: '未结算',
        result_unsettled_note: '盈亏将在结算后计算',
        result_remaining_shares: '剩余份额',
        result_buy_cost: '买入成本',
        result_avg_price: '均摊价',
        result_sell: '卖出',
        result_peak_exposure: '峰值敞口',
        result_trade_n: '第{n}笔',
        result_maker_taker: 'Maker/Taker 分布',
        result_exposure_summary: '最终敞口汇总',
        result_type: '类型',
        result_dollar_exposure: '美元敞口',
        result_share_exposure: '份额敞口',
        result_exposure: '敞口',
        result_net: '净敞口',
        result_trade_report: '交易报告',
        result_report: '交易报告',
        result_expand: '展开查看',
        result_collapse: '收起',
        result_no_data: '无报告数据',
        result_no_report: '无报告数据',
        market_status: '市场状态',
        
        // 来源统计
        result_source_stats: '交易来源分布',
        source_direct: 'Direct (直接交易)',
        source_neg_risk: 'Neg-Risk (转换)',
        source_split: 'Split (拆分)',
        source_merge: 'Merge (合并)',
        source_transfer: 'Transfer (转账)',
        source_redeem: 'Redeem (赎回)',
        source_unknown: 'Unknown (未知)',
        
        // 交易员分析页
        trader_title: '交易员分析',
        trader_subtitle: '分析交易员在特定市场类型（15分钟、每小时、每日等）的全天交易记录',
        trader_wallet_label: '钱包地址',
        trader_type_label: '市场类型',
        trader_type_hourly: '每小时',
        trader_type_daily: '每日',
        trader_type_custom: '自定义',
        trader_custom_placeholder: '输入市场关键词，如: Bitcoin, Ethereum, Trump...',
        trader_date_label: '日期筛选',
        trader_date_optional: '(可选)',
        trader_btn_analyze: '开始分析',
        trader_btn_cancel: '取消',
        trader_btn_new: '重新分析',
        trader_progress_fetching: '正在获取交易活动...',
        trader_progress_analyzing: '正在分析各市场交易...',
        trader_progress_note: '正在获取并分析多个市场的交易记录...',
        trader_total_markets: '参与市场数',
        trader_total_trades: '总交易笔数',
        trader_buy_volume: '总买入金额',
        trader_sell_volume: '总卖出金额',
        trader_total_pnl: '总盈亏',
        trader_win_rate: '胜率',
        trader_net_exposure: '净敞口',
        trader_username: '用户名',
        trader_settled: '已结算',
        trader_unsettled_short: '未结算',
        trader_pending: '待结算',
        trader_no_settled: '无已结算市场',
        trader_all_time: '所有时间',
        trader_market_breakdown: '各市场明细',
        trader_col_market: '市场',
        trader_col_trades: '交易数',
        trader_col_buy: '买入成本',
        trader_col_sell: '卖出收入',
        trader_col_exposure: '净敞口',
        trader_col_status: '状态',
        trader_col_pnl: '盈亏',
        trader_col_time: '时间',
        trader_resolved: '已结算',
        trader_open: '进行中',
        trader_error_no_type: '请选择市场类型',
        trader_error_no_keyword: '请输入自定义关键词',
        home_trader_title: '交易员分析',
        home_trader_desc: '分析交易员在特定市场类型的全天交易日志，查看盈亏、胜率、各市场明细。',

        // 发现模式
        trader_coin_label: '币种（发现模式）',
        trader_coin_hint: '选择币种自动发现所有市场',
        trader_coin_none: '不选（关键词搜索）',
        trader_discovery_note: '发现模式：将自动查找该币种在选定日期的所有市场，然后检查交易员的交易记录。',
        trader_date_required: '（发现模式必选）',
        trader_btn_discover: '发现并分析',
        trader_progress_discovering: '正在发现市场...',
        trader_discovery_result: '发现 {discovered}/{cycles} 个 {coin} 市场，交易员参与了 {traded} 个',
        trader_traded_markets: '参与/发现',
        trader_show_all: '显示所有市场（含未交易）',
        trader_no_trades: '未交易',
        trader_error_no_date: '使用发现模式请选择日期',

        // 多选项发现模式
        multi_discover_tab: '发现市场',
        multi_discover_coin: '币种',
        multi_discover_interval: '时间间隔',
        multi_discover_btn: '发现所有市场',
        multi_discover_hint: '自动发现指定币种+间隔+日期的所有市场',
        multi_discover_no_coin: '请选择币种',
        multi_discover_no_interval: '请选择时间间隔',
        multi_discover_found: '个市场已发现',

        // 错误消息
        error_no_market: '请输入市场名称',
        error_no_url: '请输入市场 URL',
        error_invalid_wallet: '请输入有效的钱包地址 (0x开头，42位)',
        error_invalid_url: '无效的 Polymarket URL，请输入事件页面的链接',
        error_not_found: '未找到该事件',
        error_no_markets: '该事件下没有子市场',
        error_no_trades: '该用户在此市场没有交易记录',
        error_task_not_found: '任务不存在',
        error_fetch_failed: '获取市场信息失败',
        error_query_cancelled: '查询已取消',
    },
    en: {
        // Navigation
        nav_quick_query: 'Quick Query',
        nav_multi_query: 'Multi-Option Query',
        nav_trader: 'Trader Analysis',
        lang_toggle: 'English',
        
        // Home page
        home_subtitle: 'Analyze Maker/Taker roles · Track position exposure · Auto-generate P&L reports',
        home_quick_title: 'Quick Query',
        home_quick_desc: 'Enter market name and wallet address to get trading analysis report. Suitable for most binary markets.',
        home_multi_title: 'Multi-Option Query',
        home_multi_desc: 'Query markets with multiple sub-options via URL, select specific sub-markets for analysis.',
        home_start_query: 'Start Query',
        home_instructions: 'Instructions',
        home_step1_title: 'Choose Query Mode',
        home_step1_desc: 'Use Quick Query for regular markets, Multi-Option Query for complex markets',
        home_step2_title: 'Enter Information',
        home_step2_desc: 'Enter market name or URL, and the wallet address to analyze',
        home_step3_title: 'Get Analysis Report',
        home_step3_desc: 'View Maker/Taker roles, position exposure, P&L report',
        home_footer: 'This tool is completely free. Follow the author on X (top right) for more free tools and updates.',
        home_notice_line1: 'Supports most market queries',
        home_notice_line2: 'Sports > Games markets not supported (e.g., Team vs Team)',
        
        // Quick query page
        simple_title: 'Quick Query',
        simple_subtitle: 'Enter market name and wallet address to get trading analysis report. Suitable for most binary markets.',
        simple_market_label: 'Market Name',
        simple_market_placeholder: 'e.g., Bitcoin Up or Down - January 8',
        simple_wallet_label: 'Wallet Address',
        simple_wallet_placeholder: '0x...',
        simple_btn_analyze: 'Start Analysis',
        simple_hint: 'Enter market name and wallet address to get complete trading analysis report',
        simple_progress_fetching: 'Fetching trade data...',
        simple_progress_analyzing: 'Analyzing Maker/Taker roles...',
        simple_discover_link: 'Auto-discover all 96 crypto markets per day? Use Trader Analysis',
        simple_btn_cancel: 'Cancel',
        simple_btn_new_query: 'New Query',
        simple_download_chart: 'Chart',
        simple_download_report: 'Report',
        simple_download_data: 'Data',
        
        // Multi-option query page
        multi_title: 'Multi-Option Query',
        multi_subtitle: 'Query markets with multiple sub-options via URL, select specific sub-markets for analysis.',
        multi_input_title: 'Input Info',
        multi_chain_title: 'On-Chain Operations',
        multi_url_label: 'Market URL',
        multi_url_placeholder: 'e.g., https://polymarket.com/event/...',
        multi_wallet_label: 'Wallet Address',
        multi_wallet_placeholder: '0x...',
        multi_btn_fetch: 'Get Sub-Markets',
        multi_hint: 'Enter market URL and wallet address to get all trading markets for this user under this event',
        multi_select_title: 'Select sub-markets user traded (multiple selection)',
        multi_select_all: 'Select All',
        multi_deselect_all: 'Deselect All',
        multi_selected_count: '{n} selected',
        multi_btn_back: 'Go Back',
        multi_btn_analyze: 'Start Analysis',
        multi_analyzing: 'Batch Analysis',
        multi_progress_info: 'Analyzing market {current} / {total}: {name}',
        multi_btn_cancel: 'Cancel',
        multi_btn_reset: 'New Query',
        multi_trades_count: '{n} trades',
        
        // Results
        result_trade_count: 'Total Trades',
        result_net_exposure: 'Net Exposure',
        result_final_value: 'Final Value',
        result_pnl: 'P&L',
        result_settlement: 'Settlement',
        result_unsettled: 'Unsettled',
        result_unsettled_note: 'P&L will be calculated after settlement',
        result_remaining_shares: 'Remaining Shares',
        result_buy_cost: 'Buy Cost',
        result_avg_price: 'Avg Price',
        result_sell: 'Sell',
        result_peak_exposure: 'Peak Exposure',
        result_trade_n: 'Trade #{n}',
        result_maker_taker: 'Maker/Taker Distribution',
        result_exposure_summary: 'Final Exposure Summary',
        result_type: 'Type',
        result_dollar_exposure: '$ Exposure',
        result_share_exposure: 'Share Exposure',
        result_exposure: 'Exposure',
        result_net: 'Net',
        result_trade_report: 'Trade Report',
        result_report: 'Trade Report',
        result_expand: 'Expand',
        result_collapse: 'Collapse',
        result_no_data: 'No report data',
        result_no_report: 'No report data',
        market_status: 'Market Status',
        
        // Source stats
        result_source_stats: 'Trade Source Distribution',
        source_direct: 'Direct Trade',
        source_neg_risk: 'Neg-Risk (Conversion)',
        source_split: 'Split',
        source_merge: 'Merge',
        source_transfer: 'Transfer',
        source_redeem: 'Redeem',
        source_unknown: 'Unknown',
        
        // Trader analysis page
        trader_title: 'Trader Analysis',
        trader_subtitle: 'Analyze a trader\'s full day trade logs across a specific market type (15min, hourly, daily, etc.)',
        trader_wallet_label: 'Wallet Address',
        trader_type_label: 'Market Type',
        trader_type_hourly: 'Hourly',
        trader_type_daily: 'Daily',
        trader_type_custom: 'Custom',
        trader_custom_placeholder: 'Enter market keyword, e.g., Bitcoin, Ethereum, Trump...',
        trader_date_label: 'Date Filter',
        trader_date_optional: '(optional)',
        trader_btn_analyze: 'Start Analysis',
        trader_btn_cancel: 'Cancel',
        trader_btn_new: 'New Analysis',
        trader_progress_fetching: 'Fetching trade activity...',
        trader_progress_analyzing: 'Analyzing trades across markets...',
        trader_progress_note: 'Fetching and analyzing trades across multiple markets...',
        trader_total_markets: 'Markets Traded',
        trader_total_trades: 'Total Trades',
        trader_buy_volume: 'Total Buy Cost',
        trader_sell_volume: 'Total Sell Revenue',
        trader_total_pnl: 'Total P&L',
        trader_win_rate: 'Win Rate',
        trader_net_exposure: 'Net Exposure',
        trader_username: 'Username',
        trader_settled: 'Settled',
        trader_unsettled_short: 'Unsettled',
        trader_pending: 'Pending',
        trader_no_settled: 'No settled markets',
        trader_all_time: 'All Time',
        trader_market_breakdown: 'Per-Market Breakdown',
        trader_col_market: 'Market',
        trader_col_trades: 'Trades',
        trader_col_buy: 'Buy Cost',
        trader_col_sell: 'Sell Revenue',
        trader_col_exposure: 'Net Exposure',
        trader_col_status: 'Status',
        trader_col_pnl: 'P&L',
        trader_col_time: 'Time',
        trader_resolved: 'Settled',
        trader_open: 'Open',
        trader_error_no_type: 'Please select a market type',
        trader_error_no_keyword: 'Please enter a custom keyword',
        home_trader_title: 'Trader Analysis',
        home_trader_desc: 'Analyze a trader\'s full day trade logs across a market type. View P&L, win rate, and per-market breakdown.',

        // Discovery mode
        trader_coin_label: 'Coin (Discovery Mode)',
        trader_coin_hint: 'Select to auto-discover all markets',
        trader_coin_none: 'None (keyword search)',
        trader_discovery_note: 'Discovery mode: will find all markets for this coin on the selected date, then check trader\'s trades for each.',
        trader_date_required: '(required for discovery)',
        trader_btn_discover: 'Discover & Analyze',
        trader_progress_discovering: 'Discovering markets...',
        trader_discovery_result: 'Discovered {discovered}/{cycles} {coin} markets, trader participated in {traded}',
        trader_traded_markets: 'Traded/Discovered',
        trader_show_all: 'Show all markets (including untraded)',
        trader_no_trades: 'No trades',
        trader_error_no_date: 'Please select a date for discovery mode',

        // Multi-option discovery mode
        multi_discover_tab: 'Discover Markets',
        multi_discover_coin: 'Coin',
        multi_discover_interval: 'Interval',
        multi_discover_btn: 'Discover All Markets',
        multi_discover_hint: 'Auto-discover all crypto markets for a coin + interval + date',
        multi_discover_no_coin: 'Please select a coin',
        multi_discover_no_interval: 'Please select an interval',
        multi_discover_found: 'markets discovered',

        // Error messages
        error_no_market: 'Please enter market name',
        error_no_url: 'Please enter market URL',
        error_invalid_wallet: 'Please enter a valid wallet address (starts with 0x, 42 characters)',
        error_invalid_url: 'Invalid Polymarket URL, please enter an event page link',
        error_not_found: 'Event not found',
        error_no_markets: 'No sub-markets under this event',
        error_no_trades: 'No trades found for this user in this market',
        error_task_not_found: 'Task not found',
        error_fetch_failed: 'Failed to fetch market info',
        error_query_cancelled: 'Query cancelled',
    }
};

// 当前语言
let currentLang = localStorage.getItem('lang') || 'zh';

// 获取翻译文本
function t(key, params = {}) {
    let text = I18N[currentLang][key] || I18N['zh'][key] || key;
    // 替换参数 {n}, {current}, {total}, {name}
    Object.keys(params).forEach(k => {
        text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), params[k]);
    });
    return text;
}

// 切换语言
function switchLang(lang) {
    currentLang = lang;
    localStorage.setItem('lang', lang);
    applyTranslations();
}

// 切换语言（在中英文间切换）
function toggleLang() {
    const newLang = currentLang === 'zh' ? 'en' : 'zh';
    switchLang(newLang);
}

// 应用翻译到页面
function applyTranslations() {
    // 更新所有带 data-i18n 属性的元素
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        el.textContent = t(key);
    });
    
    // 更新所有带 data-i18n-placeholder 属性的输入框
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        el.placeholder = t(key);
    });
    
    // 更新语言切换按钮文本
    const langText = document.getElementById('langText');
    const langTextMobile = document.getElementById('langTextMobile');
    if (langText) langText.textContent = t('lang_toggle');
    if (langTextMobile) langTextMobile.textContent = t('lang_toggle');
    
    // 更新 HTML lang 属性
    document.documentElement.lang = currentLang === 'zh' ? 'zh-CN' : 'en';
}

// 获取当前语言
function getLang() {
    return currentLang;
}

// 页面加载时应用翻译
document.addEventListener('DOMContentLoaded', function() {
    applyTranslations();
});
