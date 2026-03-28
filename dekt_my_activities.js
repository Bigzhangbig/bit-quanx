/*
 * 脚本名称：北理工第二课堂-我的活动
 * 作者：Gemini for User
 * 描述：查看个人报名列表，若有待签到/签退活动且在时间内，发送通知并复制二维码链接。
 * 
 * [task_local]
 * 0 8-22 * * * https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/dekt_my_activities.js, tag=第二课堂我的活动, enabled=true
 */

const EnvCtor = (typeof global !== 'undefined' && global.Env) ? global.Env : Env;
const $ = new EnvCtor("北理工第二课堂-我的活动");

// 统一时间戳日志工具
function _nowTs() {
    const d = new Date();
    const pad = (n, w = 2) => String(n).padStart(w, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3, '0')}`;
}
function log(...args) {
    console.log(...args);
}

log("脚本开始运行");

const CONFIG = {
    tokenKey: "bit_sc_token",
    // 调试模式开关（来自 BoxJS：bit_sc_debug）
    debugKey: "bit_sc_debug",
    listUrl: "https://qcbldekt.bit.edu.cn/api/course/list/my?page=1&limit=200",
    // 课程详情 REST 接口（含时长/签到签退时间等）
    courseInfoUrlRest: "https://qcbldekt.bit.edu.cn/api/course/info/",
    // 我的课程列表：使用新路径（旧路径保留在代码兜底处理中）
    myCourseListUrl: "https://qcbldekt.bit.edu.cn/api/course/list/my?page=1&limit=200",
    qrBaseUrl: "https://qcbldekt.bit.edu.cn/qrcode/event/?course_id=",
    categories: [
        { id: 1, name: "理想信念" },
        { id: 2, name: "科学素养" },
        { id: 3, name: "社会贡献" },
        { id: 4, name: "团队协作" },
        { id: 5, name: "文化互鉴" },
        { id: 6, name: "健康生活" }
    ]
};

// 内存缓存，减少接口请求次数
const CACHE = {
    myCourseList: null,
    myCourseListFetchedAt: 0,
    // legacyCheckInFailed 已移除
};

// 仅在作为主模块直接运行时自动执行，避免被 require 时重复执行（如 local 调试脚本）
if (typeof module === 'undefined' || require.main === module) {
    (async () => {
        try {
            await checkActivities();
        } catch (e) {
            log(e);
        } finally {
            $.done();
        }
    })();
}

async function checkActivities() {
    const token = $.getdata(CONFIG.tokenKey);
    const isDebug = isDebugMode();
    const authToken = normalizeAuthToken(token);
    if (!authToken) {
        notify($.name, "❌ 未找到 Token", "请先在 BoxJS 或本地配置 bit_sc_token");
        return;
    }

    // 动态获取微信小程序跳转链接，失败时直接跳转微信
    let openUrl = null;
    try {
        const dynamicUrl = await getWechatJumpLink();
        if (dynamicUrl) {
            openUrl = dynamicUrl;
        } else {
            openUrl = "weixin://"; // 获取失败，直接跳转微信
        }
    } catch (e) {
        console.error('获取动态链接失败，直接跳转微信:', e);
        openUrl = "weixin://"; // 发生错误，直接跳转微信
    }

    const headers = {
        'Authorization': authToken,
        'Content-Type': 'application/json;charset=utf-8'
    };

    try {
        if (isDebug) {
            log("[DEBUG] 调试模式已开启：将抑制通知，仅输出日志。");
        }

        // 若缓存为空或过期，则在后台并行预拉取“我的课程列表”，不阻塞主列表请求
        try {
            if (!CACHE.myCourseList || (Date.now() - CACHE.myCourseListFetchedAt >= 5 * 60 * 1000)) {
                log('[myCourseList] 后台预拉取（不阻塞主流程）...');
                getMyCourseList(headers).then(list => {
                    if (Array.isArray(list)) {
                        log(`[myCourseList] 后台预拉取完成，条数: ${list.length}`);
                    } else {
                        log('[myCourseList] 后台预拉取完成（非数组）');
                    }
                }).catch(e => {
                    log('[myCourseList] 后台预拉取失败: ' + e);
                });
            } else {
                log('[myCourseList] 缓存命中，跳过后台预拉取');
            }
        } catch (e) {
            log("准备后台预拉取失败: " + e);
        }

        const items = await getMyCourseList(headers);
        if (Array.isArray(items)) {
            log(`[checkActivities] 使用主接口 ${CONFIG.listUrl}，拿到 ${items.length} 条我的课程`);
            return await processItems(items, headers);
        }
        log("获取列表失败或列表为空");
    } catch (error) {
        log("请求失败: " + error);
        notify($.name, "请求失败", toErrorText(error));
    }
}

function httpGet(url, headers, timeout = 15000) {
    // 查询接口存在偶发抖动，保留 1 次快速重试，降低假失败概率
    return httpGetWithRetry(url, headers, timeout, 1);
}

function httpGetWithRetry(url, headers, timeout, retries) {
    return new Promise((resolve, reject) => {
        const opts = { url, headers, timeout };

        // 心跳日志：在等待响应或重试期间每秒输出一次，便于诊断网络/阻塞感知
        const startTs = Date.now();
        let hb = setInterval(() => {
            const secs = Math.floor((Date.now() - startTs) / 1000);
            try { log(`[httpGet] hb ${secs}s`); } catch (e) {}
        }, 1000);
        const clearHb = () => { if (hb) { clearInterval(hb); hb = null; } };

        const attempt = (remaining) => {
            $.get(opts, (err, resp, data) => {
                try {
                    if (err) {
                        if (remaining > 0) {
                            log(`[httpGet] 请求错误，重试中（剩余 ${remaining} 次）： ${err}`);
                            setTimeout(() => attempt(remaining - 1), 1000);
                            return;
                        }
                        reject(err);
                    } else {
                        if (resp.status === 401 || resp.statusCode === 401) {
                            resolve({ code: 401, message: "Unauthenticated." });
                            return;
                        }
                        try {
                            resolve(JSON.parse(data));
                        } catch (e) {
                            reject("JSON解析失败");
                        }
                    }
                } finally {
                    clearHb();
                }
            });
        };

        attempt(retries);
    });
}

// 兜底：获取“我的课程列表”，用于补齐时长/分类等元数据（带缓存）
async function getMyCourseList(headers) {
    const now = Date.now();
    // 简单的 5 分钟缓存
    if (CACHE.myCourseList && (now - CACHE.myCourseListFetchedAt < 5 * 60 * 1000)) {
        return CACHE.myCourseList;
    }
    try {
        // 新接口
        let usedUrl = CONFIG.myCourseListUrl;
        let data = await httpGet(usedUrl, headers);
        // 若失败则尝试旧接口
        if (!(data && data.code === 200)) {
            usedUrl = "https://qcbldekt.bit.edu.cn/api/transcript/course/list/my?page=1&limit=200";
            data = await httpGet(usedUrl, headers);
        }
        if (data && data.code === 200) {
            let items = [];
            // 兼容多种返回结构
            if (data.data) {
                if (Array.isArray(data.data.items)) items = data.data.items;
                else if (Array.isArray(data.data.list)) items = data.data.list;
                else if (Array.isArray(data.data)) items = data.data;
            } else {
                if (Array.isArray(data.items)) items = data.items;
                else if (Array.isArray(data.list)) items = data.list;
            }
            // 过滤掉已经过了签退/签到结束时间的课程，避免预拉取到已结束活动
            try {
                const beforeFilterCount = items.length;
                const nowTs = Date.now();
                items = items.filter(it => {
                    // 优先使用签退结束时间，其次签到结束时间
                    const endTimeStr = it.sign_out_end_time || it.sign_in_end_time;
                    if (!endTimeStr) return true; // 没有结束时间则保留
                    const parsed = new Date(String(endTimeStr).replace(/-/g, '/'));
                    if (isNaN(parsed.getTime())) return true; // 无法解析则保留
                    return parsed.getTime() >= nowTs; // 结束时间在现在之后则保留
                });
                CACHE.myCourseList = items;
                CACHE.myCourseListFetchedAt = now;
                log(`[myCourseList] 使用接口: ${usedUrl}，原始 ${beforeFilterCount} 条，过滤后 ${items.length} 条`);
            } catch (e) {
                // 过滤逻辑出错时兜底不影响主流程
                CACHE.myCourseList = items;
                CACHE.myCourseListFetchedAt = now;
                log(`[myCourseList] 过滤失败，仍使用原始列表: ${JSON.stringify(e)}`);
            }
            // 日志打印课程详情（即使为0条也打印接口与条数）
            items.forEach(item => {
                const category = item.transcript_index ? item.transcript_index.transcript_name : (item.transcript_name || '未知');
                const status = item.status_label || item.status;
                const address = item.sign_in_address && Array.isArray(item.sign_in_address) ? item.sign_in_address.map(a => a.address).join(';') : (item.time_place || '未知');
                let lineStr = `课程ID: ${item.id || item.course_id}, 类别: ${category}, 名称: ${item.title || item.course_title}, 状态: ${status}, 地址: ${address}`;
                if (item.completion_flag_text) {
                    lineStr += `, completion_flag_text: ${item.completion_flag_text}`;
                }
                // 判断 time 类型的若干可见字段
                if ((item.completion_flag && String(item.completion_flag).toLowerCase() === 'time') || item.duration != null || (item.transcript_index_type && item.transcript_index_type.duration != null)) {
                    const duration = item.duration || (item.transcript_index_type && item.transcript_index_type.duration) || (item.completion_flag_text ? item.completion_flag_text : '未知');
                    lineStr += `, 时长: ${duration}, 签到: ${item.sign_in_start_time || '无'}-${item.sign_in_end_time || '无'}, 签退: ${item.sign_out_start_time || '无'}-${item.sign_out_end_time || '无'}`;
                }
                log(lineStr);
            });
            return CACHE.myCourseList;
        } else {
            log(`[myCourseList] 接口返回非200或结构异常: ${JSON.stringify(data)}`);
        }
    } catch (e) {
        log(`获取我的课程列表失败: ${e}`);
    }
    return [];
}

// 合并获取课程详细信息：
// 1) checkIn/info 获取签到与签退时间段
// 2) course/info 获取 duration/transcript 等元数据
// 3) 若仍缺失 duration，再从 course/list/my 兜底补齐
async function getCourseInfo(courseId, headers) {
    const result = { _source: {} };

    // 1) 优先获取 REST 课程详情（含签到/签退/时长）
    try {
        const rest = await httpGet(`${CONFIG.courseInfoUrlRest}${courseId}`, headers);
        if (rest && rest.code === 200 && rest.data) {
            Object.assign(result, rest.data);
            result._source.courseInfo = 'rest';
            if (result.duration != null) {
                result._source.duration = 'rest.duration';
            }
            log(`[courseInfo] 使用 REST 接口获取成功: id=${courseId}`);
        } else {
            log(`[courseInfo] REST 接口返回异常: id=${courseId}`);
        }
    } catch (e) {
        log(`[courseInfo] REST 接口请求异常: ${e}`);
    }

    // 2) 兜底：我的课程列表（仅在前面无 duration 时）
    if (result.duration == null) {
        try {
            const items = await getMyCourseList(headers);
            const found = items.find(x => {
                // 兼容字段名差异
                return String(x.course_id || x.id) === String(courseId);
            });
            if (found) {
                if (found.duration != null) result.duration = found.duration;
                if (found.duration != null) result._source.duration = 'myCourseList.duration';
                if (result.transcript_index_id == null && found.transcript_index_id != null) {
                    result.transcript_index_id = found.transcript_index_id;
                }
                if (result.transcript_name == null && found.transcript_name != null) {
                    result.transcript_name = found.transcript_name;
                }
                log(`[duration] 兜底使用 myCourseList: id=${courseId}`);
            }
        } catch (e) {
            log(`从我的课程列表兜底获取时长失败: ${e}`);
        }
    }

    // 3) 最终兜底：尝试从 transcript_index_type.duration 或 completion_flag_text 解析
    if (result.duration == null) {
        try {
            if (result.transcript_index_type && result.transcript_index_type.duration != null) {
                result.duration = result.transcript_index_type.duration;
                result._source.duration = 'transcript_index_type.duration';
            } else if (result.completion_flag_text) {
                const m = String(result.completion_flag_text).match(/(\d{1,3})\s*分钟/);
                if (m) {
                    result.duration = parseInt(m[1], 10);
                    result._source.duration = 'completion_flag_text';
                }
            }
        } catch (e) {
            log(`从元数据提取时长失败: ${e}`);
        }
    }

    return result;
}

async function processItems(items, headers) {
    const now = Date.now();
    let notifyItems = [];
    // 收集需要处理的任务（过滤并去重），再并发拉取详情（并发上限）
    const tasks = [];
    for (const item of items) {
        const statusLabel = getStatusLabel(item);
        // 去除已取消的课程（精确匹配 '已取消' 或 status 为 4）
        if (statusLabel === "已取消") continue;
        if (typeof item.status !== 'undefined' && (item.status === 4 || item.status === '4')) continue;

        const isSignIn = statusLabel === "待签到";
        const isSignOut = statusLabel === "待签退";
        if (!(isSignIn || isSignOut)) continue;

        // 先按状态入队，具体时间窗在详情阶段用 course/info 再校验，避免列表字段缺失造成漏掉活动
        tasks.push({ item, isSignIn, statusLabel });
    }

    if (tasks.length === 0) {
        log("没有需要签到/签退的活动");
        return [];
    }

    log(`开始并发拉取 ${tasks.length} 个课程详情（并发上限 5）`);

    // 并发映射工具（并发上限）
    async function mapWithConcurrencyLimit(inputs, mapper, limit = 5) {
        const results = [];
        const executing = new Set();
        for (const input of inputs) {
            const p = (async () => {
                try {
                    return await mapper(input);
                } finally {
                    executing.delete(p);
                }
            })();
            results.push(p);
            executing.add(p);
            if (executing.size >= limit) {
                await Promise.race(executing);
            }
        }
        return Promise.all(results);
    }

    // mapper: 拉取单个课程的完整 notifyItem（或 null）
    const mapper = async (task) => {
        const item = task.item;
        const isSignIn = task.isSignIn;
        const statusLabel = task.statusLabel;
        const id = item.course_id || item.id;
        const title = item.course_title || item.title || `课程${id || ''}`;
        if (!id) {
            log('[courseInfo] 跳过：缺少 course_id/id');
            return null;
        }
        log(`[courseInfo] 开始拉取详情 id=${id} 标题=${title}`);
        const start = Date.now();
        let info = null;
        try {
            info = await getCourseInfo(id, headers);
        } catch (e) {
            log(`[courseInfo] 拉取异常 id=${id}: ${e}`);
            return null;
        }
        const dur = Date.now() - start;
        log(`[courseInfo] 完成 id=${id} 耗时 ${dur} ms`);

        const signInStart = (info && info.sign_in_start_time) || item.sign_in_start_time;
        const signInEnd = (info && info.sign_in_end_time) || item.sign_in_end_time;
        const signOutStart = (info && info.sign_out_start_time) || item.sign_out_start_time;
        const signOutEnd = (info && info.sign_out_end_time) || item.sign_out_end_time;
        const deadlineRaw = isSignIn ? signInEnd : signOutEnd;

        if (!deadlineRaw) {
            log(`[courseInfo] 跳过 id=${id}：未拿到${isSignIn ? '签到' : '签退'}截止时间`);
            return null;
        }
        const deadlineTs = new Date(String(deadlineRaw).replace(/-/g, '/')).getTime();
        if (!Number.isFinite(deadlineTs)) {
            log(`[courseInfo] 跳过 id=${id}：截止时间无法解析 ${deadlineRaw}`);
            return null;
        }
        if (now >= deadlineTs) {
            log(`[courseInfo] 跳过 id=${id}：已过截止时间 ${deadlineRaw}`);
            return null;
        }

        let category = null;
        const catId = (info && info.transcript_index_id) || item.transcript_index_id;
        if (catId != null) {
            category = CONFIG.categories.find(c => String(c.id) === String(catId));
        } else if (info && info.transcript_name) {
            category = CONFIG.categories.find(c => c.name === info.transcript_name);
        } else if (info && info.transcript_index && info.transcript_index.transcript_name) {
            category = CONFIG.categories.find(c => c.name === info.transcript_index.transcript_name);
        }
        const categoryName = category ? category.name : (info && info.transcript_name) || (info && info.transcript_index && info.transcript_index.transcript_name) || "未知分类";

        let duration = null;
        if (info && info.duration != null) duration = info.duration;
        else if (item && item.duration != null) duration = item.duration;
        else if (info && info.transcript_index_type && info.transcript_index_type.duration != null) duration = info.transcript_index_type.duration;
        else if (info && info.completion_flag_text) {
            const m = String(info.completion_flag_text).match(/(\d{1,3})\s*分钟/);
            if (m) duration = parseInt(m[1], 10);
        }
        const durationSource = (info && info._source && info._source.duration) || (item && item.duration != null ? 'myCourseItem.duration' : null) || 'unknown';

        return {
            title: title,
            action: isSignIn ? "签到" : "签退",
            deadline: deadlineRaw,
            id: id,
            signInStart: signInStart,
            signInEnd: signInEnd,
            signOutStart: signOutStart,
            signOutEnd: signOutEnd,
            category: categoryName,
            statusLabel: statusLabel,
            duration: duration,
            durationSource: durationSource
        };
    };

    const results = await mapWithConcurrencyLimit(tasks, mapper, 5);
    // 过滤掉 null
    notifyItems = results.filter(x => x != null);

    if (notifyItems.length > 0) {
        // 按截止时间排序，优先处理最早截止的
        notifyItems.sort((a, b) => new Date(a.deadline.replace(/-/g, '/')) - new Date(b.deadline.replace(/-/g, '/')));

        // 打印所有待参加活动的签到时间段和签退时间段
        log("待参加活动列表详情:");
        notifyItems.forEach(item => {
            log(`【${item.category} | ${item.statusLabel}】[${item.id}] [${item.action}] ${item.title}`);
            log(`  签到时间: ${item.signInStart || '未设置'} - ${item.signInEnd || '未设置'}`);
            log(`  签退时间: ${item.signOutStart || '未设置'} - ${item.signOutEnd || '未设置'}`);
            let ds = '';
            if (item.duration == null) {
                log('  时长: 未知');
                return;
            }
            // rest.duration 不显示来源；其它来源简化标签
            switch (item.durationSource) {
                case 'rest.duration':
                    ds = '';
                    break;
                case 'myCourseList.duration':
                    ds = ' (列表兜底)';
                    break;
                case 'transcript_index_type.duration':
                    ds = ' (类型默认)';
                    break;
                case 'completion_flag_text':
                    ds = ' (规则解析)';
                    break;
                case 'myCourseItem.duration':
                    ds = ' (我的课程列表)';
                    break;
                default:
                    ds = '';
            }
            log(`  时长: ${item.duration}${ds}`);
        });

        // 1. 处理第一个（最紧急）活动
        const firstItem = notifyItems[0];
        const qrUrl = `${CONFIG.qrBaseUrl}${firstItem.id}`;
        const quickChartUrl = `https://quickchart.io/qr?text=${encodeURIComponent(qrUrl)}`;
        
        let msgBody = `签到: ${firstItem.signInStart || '未设置'} - ${firstItem.signInEnd || '未设置'}`;
        msgBody += `\n签退: ${firstItem.signOutStart || '未设置'} - ${firstItem.signOutEnd || '未设置'}`;
        if (firstItem.duration != null) {
            msgBody += `\n时长: ${firstItem.duration}`;
        }

        notify(
            $.name,
            `⚠️ ${firstItem.action}提醒: [${firstItem.id}] ${firstItem.title}`,
            msgBody,
            {"open-url": quickChartUrl}
        );
        log(`已通知: [${firstItem.id}] ${firstItem.title} ${firstItem.action}`);

        // 2. 其余活动简写为一条通知
        if (notifyItems.length > 1) {
            const restItems = notifyItems.slice(1);
            const summary = restItems.map(item => `[${item.id}] [${item.action}] ${item.title}`).join('\n');
            
            notify(
                $.name,
                `还有 ${restItems.length} 个活动待处理`,
                summary + "\n点击跳转小程序",
                {"open-url": openUrl}
            );
            log(`已通知其余 ${restItems.length} 个活动`);
        }
    } else {
        log("没有需要签到/签退的活动");
    }

    return notifyItems;
}

function getStatusLabel(item) {
    const label = item && item.status_label ? String(item.status_label).trim() : '';
    if (label) return label;
    const s = String(item && item.status != null ? item.status : '').trim();
    if (s === '0') return '待签到';
    if (s === '1') return '待签退';
    if (s === '4') return '已取消';
    return label;
}

// Env Polyfill
function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { this.isQuanX && $notify(e, s, i, r) } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && $done(t) } }(t, e) }

// 统一通知出口：支持调试模式不发送通知
function notify(title, subtitle = "", body = "", options) {
    const isDebug = String($.getdata(CONFIG.debugKey) || "false").toLowerCase() === "true";
    const bodyText = toErrorText(body);
    if (isDebug) {
        log(`[DEBUG] 抑制通知 -> ${title} | ${subtitle} | ${bodyText.substring(0, 80)}`);
        return;
    }
    $.msg(title, subtitle, bodyText, options);
}

// 将任意错误对象/值统一转成可读文本，避免调试日志中字符串方法报错
function toErrorText(value) {
    if (value == null) return "";
    if (typeof value === 'string') return value;
    if (value instanceof Error) return value.message || String(value);
    if (typeof value === 'object') {
        try { return JSON.stringify(value); } catch (_) { return String(value); }
    }
    return String(value);
}

// 获取调试模式
function isDebugMode() {
    return String($.getdata(CONFIG.debugKey) || "false").toLowerCase() === "true";
}

/**
 * 动态获取微信小程序跳转链接
 * @param {string} pagePath - 小程序的页面路径 (可选)
 * @returns {Promise<string|null>} - 返回 weixin:// 开头的链接
 */
async function getWechatJumpLink(pagePath = '/pages/index/index') {
    const apiUrl = `https://qcbldekt.bit.edu.cn/api/generatescheme?path=${encodeURIComponent(pagePath)}`;
    
    try {
        const response = await fetch(apiUrl);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.code === 200 && result.data) {
            return result.data; // 返回 weixin://dl/business/?t=...
        } else {
            console.error('获取微信小程序链接失败:', result.message);
            return null;
        }
    } catch (error) {
        console.error('请求微信小程序链接时发生错误:', error);
        return null;
    }
}

// 统一 token 形态为 "Bearer <id|token>"，避免出现 "Bearer Bearer ..."
function normalizeAuthToken(token) {
    if (!token) return "";
    let raw = String(token).trim();
    raw = raw.replace(/^(?:Bearer\s+)+/i, '').trim();
    if (!raw) return '';
    raw = `Bearer ${raw}`;
    return raw;
}

// 导出统一入口，便于本地或其他脚本调用
async function run() {
    return await checkActivities();
}

if (typeof module !== 'undefined') {
    module.exports = { run, getMyCourseList, getCourseInfo, processItems };
}
