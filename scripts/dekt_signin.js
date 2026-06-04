/*
 * 脚本名称：北理工第二课堂签到
 * 作者：Gemini for User
 * 描述：自动检查已报名课程并进行签到/签退。
 *
 * [task_local]
 * # 签到脚本 (默认关闭，需手动运行或开启)
 * 0 8-22/1 * * * https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/dekt_signin.js, tag=第二课堂签到, enabled=false
 */

// MD5 实现（用于签名）
function md5(string) {
    function md5cycle(x, k) {
        var a = x[0], b = x[1], c = x[2], d = x[3];
        a = ff(a, b, c, d, k[0], 7, -680876936);d = ff(d, a, b, c, k[1], 12, -389564586);c = ff(c, d, a, b, k[2], 17, 606105819);b = ff(b, c, d, a, k[3], 22, -1044525330);a = ff(a, b, c, d, k[4], 7, -176418897);d = ff(d, a, b, c, k[5], 12, 1200080426);c = ff(c, d, a, b, k[6], 17, -1473231341);b = ff(b, c, d, a, k[7], 22, -45705983);a = ff(a, b, c, d, k[8], 7, 1770035416);d = ff(d, a, b, c, k[9], 12, -1958414417);c = ff(c, d, a, b, k[10], 17, -42063);b = ff(b, c, d, a, k[11], 22, -1990404162);a = ff(a, b, c, d, k[12], 7, 1804603682);d = ff(d, a, b, c, k[13], 12, -40341101);c = ff(c, d, a, b, k[14], 17, -1502002290);b = ff(b, c, d, a, k[15], 22, 1236535329);a = gg(a, b, c, d, k[1], 5, -165796510);d = gg(d, a, b, c, k[6], 9, -1069501632);c = gg(c, d, a, b, k[11], 14, 643717713);b = gg(b, c, d, a, k[0], 20, -373897302);a = gg(a, b, c, d, k[5], 5, -701558691);d = gg(d, a, b, c, k[10], 9, 38016083);c = gg(c, d, a, b, k[15], 14, -660478335);b = gg(b, c, d, a, k[4], 20, -405537848);a = gg(a, b, c, d, k[9], 5, 568446438);d = gg(d, a, b, c, k[14], 9, -1019803690);c = gg(c, d, a, b, k[3], 14, -187363961);b = gg(b, c, d, a, k[8], 20, 1163531501);a = gg(a, b, c, d, k[13], 5, -1444681467);d = gg(d, a, b, c, k[2], 9, -51403784);c = gg(c, d, a, b, k[7], 14, 1735328473);b = gg(b, c, d, a, k[12], 20, -1926607734);a = hh(a, b, c, d, k[5], 4, -378558);d = hh(d, a, b, c, k[8], 11, -2022574463);c = hh(c, d, a, b, k[11], 16, 1839030562);b = hh(b, c, d, a, k[14], 23, -35309556);a = hh(a, b, c, d, k[1], 4, -1530992060);d = hh(d, a, b, c, k[4], 11, 1272893353);c = hh(c, d, a, b, k[7], 16, -155497632);b = hh(b, c, d, a, k[10], 23, -1094730640);a = hh(a, b, c, d, k[13], 4, 681279174);d = hh(d, a, b, c, k[0], 11, -358537222);c = hh(c, d, a, b, k[3], 16, -722521979);b = hh(b, c, d, a, k[6], 23, 76029189);a = hh(a, b, c, d, k[9], 4, -640364487);d = hh(d, a, b, c, k[12], 11, -421815835);c = hh(c, d, a, b, k[15], 16, 530742520);b = hh(b, c, d, a, k[2], 23, -995338651);a = ii(a, b, c, d, k[0], 6, -198630844);d = ii(d, a, b, c, k[7], 10, 1126891415);c = ii(c, d, a, b, k[14], 15, -1416354905);b = ii(b, c, d, a, k[5], 21, -57434055);a = ii(a, b, c, d, k[12], 6, 1700485571);d = ii(d, a, b, c, k[3], 10, -1894986606);c = ii(c, d, a, b, k[10], 15, -1051523);b = ii(b, c, d, a, k[1], 21, -2054922799);a = ii(a, b, c, d, k[8], 6, 1873313359);d = ii(d, a, b, c, k[15], 10, -30611744);c = ii(c, d, a, b, k[6], 15, -1560198380);b = ii(b, c, d, a, k[13], 21, 1309151649);a = ii(a, b, c, d, k[4], 6, -145523070);d = ii(d, a, b, c, k[11], 10, -1120210379);c = ii(c, d, a, b, k[2], 15, 718787259);b = ii(b, c, d, a, k[9], 21, -343485551);
        x[0] = add32(a, x[0]);x[1] = add32(b, x[1]);x[2] = add32(c, x[2]);x[3] = add32(d, x[3]);
    }
    function cmn(q, a, b, x, s, t) { a = add32(add32(a, q), add32(x, t)); return add32((a << s) | (a >>> (32 - s)), b); }
    function ff(a, b, c, d, x, s, t) { return cmn((b & c) | ((~b) & d), a, b, x, s, t); }
    function gg(a, b, c, d, x, s, t) { return cmn((b & d) | (c & (~d)), a, b, x, s, t); }
    function hh(a, b, c, d, x, s, t) { return cmn(b ^ c ^ d, a, b, x, s, t); }
    function ii(a, b, c, d, x, s, t) { return cmn(c ^ (b | (~d)), a, b, x, s, t); }
    function md51(s) {
        var n = s.length, state = [1732584193, -271733879, -1732584194, 271733878], i;
        for (i = 64; i <= n; i += 64) { md5cycle(state, md5blk(s.substring(i - 64, i))); }
        s = s.substring(i - 64);
        var tail = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0];
        for (i = 0; i < s.length; i++) tail[i >> 2] |= s.charCodeAt(i) << ((i % 4) << 3);
        tail[i >> 2] |= 0x80 << ((i % 4) << 3);
        if (i > 55) { md5cycle(state, tail); tail = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]; }
        tail[14] = n * 8;
        md5cycle(state, tail);
        return state;
    }
    function md5blk(s) {
        var md5blks = [], i;
        for (i = 0; i < 64; i += 4) { md5blks[i >> 2] = s.charCodeAt(i) + (s.charCodeAt(i+1) << 8) + (s.charCodeAt(i+2) << 16) + (s.charCodeAt(i+3) << 24); }
        return md5blks;
    }
    var hex_chr = '0123456789abcdef'.split('');
    function rhex(n) { var s = '', j = 0; for (; j < 4; j++) s += hex_chr[(n >> (j * 8 + 4)) & 0x0F] + hex_chr[(n >> (j * 8)) & 0x0F]; return s; }
    function hex(x) { for (var i = 0; i < x.length; i++) x[i] = rhex(x[i]); return x.join(''); }
    function add32(a, b) { return (a + b) & 0xFFFFFFFF; }
    return hex(md51(string));
}

// ====== 配置项 ======
const $ = new Env("北理工第二课堂签到");

// 统一时间戳日志工具
function _nowTs() {
    const d = new Date();
    const pad = (n, w = 2) => String(n).padStart(w, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3, '0')}`;
}
function log(...args) {
    console.log(`[${_nowTs()}]`, ...args);
}

const CONFIG = {
    tokenKey: "bit_sc_token",
    autoSignAllKey: "bit_sc_auto_sign_all",
    runtimeIdsKey: "bit_sc_runtime_sign_ids",
    // OLD: signIn 列表接口（当前链路不稳定，已停用）
    // listUrl: "https://qcbldekt.bit.edu.cn/api/transcript/course/signIn/list?page=1&limit=20&type=1",
    listUrl: "https://qcbldekt.bit.edu.cn/api/course/list/my?page=1&limit=20",
    infoUrl: "https://qcbldekt.bit.edu.cn/api/transcript/checkIn/info",
    signInUrl: "https://qcbldekt.bit.edu.cn/api/transcript/signIn",
    courseInfoUrlRest: "https://qcbldekt.bit.edu.cn/api/course/info/",
    myCourseListUrl: "https://qcbldekt.bit.edu.cn/api/course/list/my?page=1&limit=20",
    requestTimeoutMs: 12000,
    detailRetryCount: 3,
    detailRetryBaseDelayMs: 700
};

// 栏目映射（与 dekt_my_activities.js 保持一致）
CONFIG.categories = [
    { id: 1, name: "理想信念" },
    { id: 2, name: "科学素养" },
    { id: 3, name: "社会贡献" },
    { id: 4, name: "团队协作" },
    { id: 5, name: "文化互鉴" },
    { id: 6, name: "健康生活" }
];

// 控制是否发送通知：仅在检测到至少一个课程处于签到/签退窗口时允许发送
let NOTIFY_ALLOWED = false;

function maybeEnableNotifyIfInWindow(info) {
    try {
        if (!info) return;
        if (isInWindow(info, 'signIn') || isInWindow(info, 'signOut')) NOTIFY_ALLOWED = true;
    } catch (e) {}
}

function notify(title, subtitle = "", body = "", options = {}) {
    const force = !!(options && options.force);
    if (force || NOTIFY_ALLOWED) {
        $.msg(title, subtitle, body);
    } else {
        // 若不允许通知，则仅在控制台输出以便调试
        console.log(`[notify suppressed] ${title} | ${subtitle} | ${body}`);
    }
}

// ====== 主入口 ======
main().finally(() => $.done());

async function main() {
    try {
        const { token, headers, autoSignAll, targetIds } = getEnvConfig();
        if (!token) {
            notify($.name, "❌ 未找到 Token", "请先运行获取 Cookie 脚本或在 BoxJS 中填写", { force: true });
            return;
        }

        const courses = await getCourseList(headers);
        const processedIds = new Set();

        if (Array.isArray(courses) && courses.length > 0) {
            await handleCourseList(courses, headers, autoSignAll);
            try {
                for (const c of courses) {
                    const cid = c && (c.course_id != null ? c.course_id : c.id);
                    if (cid != null) processedIds.add(String(cid));
                }
            } catch {}

            // 使用抽取的函数收集处于窗口的课程
            try {
                const coursesInWindow = await collectCoursesInWindow(courses, headers);
                if (coursesInWindow.length === 1) {
                    const only = coursesInWindow[0];
                    const body = `${only.id}|${only.column}|${only.title}\n处在${only.when}窗口：${only.timeRange}\n时长：${only.duration}`;
                    notify($.name, "仅有一门课程在窗口", body, { force: true });
                }
            } catch (e) {}
        }

        // 对于通过 BoxJS/CLI 指定的目标课程：
        // - 当 autoSignAll=false 时，无论是否在列表中都要单独处理（确保会尝试签到/签退）
        // - 当 autoSignAll=true 时，若已通过列表处理过则跳过以避免重复
        const pendingTargetIds = (targetIds || [])
            .map(id => String(id))
            .filter(id => id && (!autoSignAll || !processedIds.has(id)));

        if (pendingTargetIds.length > 0) {
            await handleTargetIds(pendingTargetIds, headers);
        }
    } catch (e) {
        console.log(`❌ 脚本运行异常: ${e}`);
    }
}

// ====== 环境与配置读取 ======
function getEnvConfig() {
    const token = $.getdata(CONFIG.tokenKey);
    const headers = buildHeaders(token);
    const autoSignAll = String($.getdata(CONFIG.autoSignAllKey) || "false").toLowerCase() === "true";
    const runtimeIdsStr = $.getdata(CONFIG.runtimeIdsKey) || "";
    let targetIds = runtimeIdsStr.split(/[,，\s]+/).map(s => s.trim()).filter(s => s);
    if (typeof global !== 'undefined') {
        if (global.DEKT_TARGET_IDS && Array.isArray(global.DEKT_TARGET_IDS)) {
            targetIds = Array.from(new Set([...(targetIds || []), ...global.DEKT_TARGET_IDS.map(String)]));
        } else if (global.DEKT_TARGET_ID) {
            targetIds = Array.from(new Set([...(targetIds || []), String(global.DEKT_TARGET_ID)]));
        }
    }
    return { token, headers, autoSignAll, targetIds };
}

// 生成 sign 签名
function generateSign(timestampMs) {
    const str = `appCode=qcbldekt&timestamp=${timestampMs}&appSecret=2GNFjVv2S7xYnoWe&origin=wechat`;
    return md5(str);
}

// 构建请求 Headers（从token统一生成）
function buildHeaders(token) {
    let headers = {};
    headers['Authorization'] = normalizeAuthToken(token);
    headers['Content-Type'] = 'application/json;charset=utf-8';
    if (!headers['Authorization']) return {};
    return headers;
}

// 构建签到专用 Headers（含 sign/timestamp/appCode）
function buildSignHeaders(token) {
    const headers = buildHeaders(token);
    if (!headers['Authorization']) return {};
    const timestampMs = Date.now().toString();
    headers['appCode'] = 'qcbldekt';
    headers['timestamp'] = timestampMs;
    headers['sign'] = generateSign(timestampMs);
    return headers;
}

function normalizeAuthToken(token) {
    if (!token) return "";
    const t = String(token).trim();
    if (!t) return "";
    return /^Bearer\s+/i.test(t) ? t : `Bearer ${t}`;
}

// 收集处于签到/签退窗口的课程，用于统一通知/展示
async function collectCoursesInWindow(courses, headers) {
    const out = [];
    if (!Array.isArray(courses) || courses.length === 0) return out;
    for (const course of courses) {
        try {
            const cid = course && (course.course_id != null ? course.course_id : course.id);
            if (cid == null) continue;
            const info = await getCourseInfo(cid, headers);
            if (!info) continue;
            const si = isInWindow(info, 'signIn');
            const so = isInWindow(info, 'signOut');
            if (si || so) {
                const title = course.course_title || course.title || info.course_title || String(cid);
                const column = resolveCategoryName(info, course) || '';
                const when = si && so ? '签到/签退' : (si ? '签到' : '签退');
                const timeRange = si ? `${info.sign_in_start_time || ''} - ${info.sign_in_end_time || ''}` : `${info.sign_out_start_time || ''} - ${info.sign_out_end_time || ''}`;
                const duration = (await getCourseDuration(cid, headers)) || '';
                out.push({ id: cid, column, title, when, timeRange, duration });
            }
        } catch (e) {
            // 忽略单个课程出错，继续处理其它
        }
    }
    return out;
}

// ====== 课程列表获取 ======
async function getCourseList(headers) {
    try {
        const listData = await httpGet(CONFIG.listUrl, headers);
        if (listData && listData.code === 200) {
            return listData.data.items || [];
        }
    } catch {}
    return [];
}

// ====== 处理课程列表 ======
async function handleCourseList(courses, headers, autoSignAll) {
    for (const course of courses) {
        const cid = course && (course.course_id != null ? course.course_id : course.id);
        if (cid == null) continue;
        // 参考 my_activities：过滤已取消课程（改为精确匹配）
        if (course.status_label && String(course.status_label).trim() === "已取消") continue;
        if (typeof course.status !== 'undefined' && (course.status === 4 || course.status === '4')) continue;
        const info = await getCourseInfo(cid, headers);
        if (!info) continue;
        if (isSignOutExpired(info)) continue;
        const meta = await getCourseMeta(cid, headers);
        if (meta && meta.completionType === 'time') {
            const safeTitle = course.course_title || course.title || info.course_title || String(cid);
            showCourseLog(cid, safeTitle, info, meta);
            if (autoSignAll) {
                await trySign(cid, info, headers, '签到', safeTitle);
                await trySign(cid, info, headers, '签退', safeTitle);
            }
        }
    }
}

// ====== 处理指定ID ======
async function handleTargetIds(targetIds, headers) {
    const skipDelay = Array.isArray(targetIds) && targetIds.length === 1;
    for (const tId of targetIds) {
        const info = await getCourseInfo(tId, headers);
        if (!info) continue;
        // 若接口返回中包含状态，也参考 activities 逻辑过滤取消状态（改为精确匹配）
        if (info.status_label && String(info.status_label).trim() === "已取消") continue;
        if (typeof info.status !== 'undefined' && (info.status === 4 || info.status === '4')) continue;
        if (isSignOutExpired(info)) continue;
        const meta = await getCourseMeta(tId, headers);
        if (meta && meta.completionType === 'time') {
            const safeTitle = await resolveCourseTitle(tId, info, headers);
            showCourseLog(tId, safeTitle, info, meta);
            await trySign(tId, info, headers, '签到', safeTitle, { skipDelay });
            await trySign(tId, info, headers, '签退', safeTitle, { skipDelay });
        }
    }
}

// ====== 日志输出 ======
function showCourseLog(courseId, title, info, meta) {
    const siWin = isInWindow(info, 'signIn');
    const soWin = isInWindow(info, 'signOut');
    console.log(`===== 课程 ${courseId} | ${title} =====`);
    console.log(`时长: ${meta.duration != null ? meta.duration : '未知'}`);
    console.log(`签到窗口: ${siWin ? '是' : '否'}${info.sign_in_start_time ? ` (${info.sign_in_start_time} - ${info.sign_in_end_time})` : ''}`);
    console.log(`签退窗口: ${soWin ? '是' : '否'}${info.sign_out_start_time ? ` (${info.sign_out_start_time} - ${info.sign_out_end_time})` : ''}`);
    console.log(`----------------------------------------------`);
}

// ====== 签到/签退尝试 ======
async function trySign(courseId, info, headers, typeStr, courseTitle, options = {}) {
    maybeEnableNotifyIfInWindow(info);
    const inSignIn = isInWindow(info, 'signIn');
    const inSignOut = isInWindow(info, 'signOut');
    if (inSignIn && inSignOut) {
        // 同时处于签到和签退窗口，优先签到
        notify($.name, `处于签到和签退窗口，默认签到`, `${courseTitle}`);
        await executeSign(courseId, info, headers, '签到', courseTitle, options);
    } else if (typeStr === '签到' && inSignIn) {
        notify($.name, `处于签到窗口`, `${courseTitle}`);
        await executeSign(courseId, info, headers, '签到', courseTitle, options);
    } else if (typeStr === '签退' && inSignOut) {
        notify($.name, `处于签退窗口`, `${courseTitle}`);
        await executeSign(courseId, info, headers, '签退', courseTitle, options);
    }
}
// 获取课程时长：优先 REST 详情，其次我的课程列表兜底
async function getCourseDuration(courseId, headers) {
    // 1) REST 课程详情
    try {
        const rest = await httpGet(`${CONFIG.courseInfoUrlRest}${courseId}`, headers);
        if (rest && rest.code === 200 && rest.data) {
            if (rest.data.duration != null) return rest.data.duration;
        }
    } catch (e) {
        // 忽略错误，继续兜底
    }
    // 2) 我的课程列表兜底（仅使用新版接口）
    try {
        const list = await httpGet(CONFIG.myCourseListUrl, headers);
        if (list && list.code === 200 && list.data && Array.isArray(list.data.items)) {
            const found = list.data.items.find(x => String(x.course_id || x.id) === String(courseId));
            if (found && found.duration != null) return found.duration;
        }
    } catch (e) {
        // 忽略错误
    }
    return null;
}

async function getCourseInfo(courseId, headers) {
    const url = `${CONFIG.infoUrl}?course_id=${courseId}`;
    for (let i = 1; i <= CONFIG.detailRetryCount; i++) {
        try {
            const data = await httpGet(url, headers, CONFIG.requestTimeoutMs);
            if (data && data.code === 200) {
                return data.data;
            }
            // 服务端业务错误通常重试收益低，直接返回
            console.log(`❌ 获取课程详情失败: ${JSON.stringify(data)}`);
            return null;
        } catch (e) {
            const errText = (e && e.message) ? e.message : String(e);
            const retryable = isRetryableNetworkError(e);
            const isLast = i >= CONFIG.detailRetryCount;
            if (!retryable || isLast) {
                console.error(`❌ 获取课程详情异常: ${errText}`);
                return null;
            }
            const delay = CONFIG.detailRetryBaseDelayMs * i;
            console.log(`⚠️ 获取课程详情异常(第${i}次): ${errText}，${delay}ms 后重试`);
            await sleep(delay);
        }
    }
    return null;
}

// 解析栏目/分类名称：优先使用 transcript_index_id -> transcript_name -> transcript_index.transcript_name
function resolveCategoryName(info, course) {
    try {
        // 先尝试 transcript_index_id
        const catId = (info && info.transcript_index_id) || (course && course.transcript_index_id) || null;
        if (catId != null) {
            const found = CONFIG.categories.find(c => String(c.id) === String(catId));
            if (found) return found.name;
        }

        // 再尝试 transcript_name
        if (info && info.transcript_name) {
            const found2 = CONFIG.categories.find(c => c.name === info.transcript_name);
            if (found2) return found2.name;
            return info.transcript_name;
        }

        // 再尝试 transcript_index.transcript_name
        if (info && info.transcript_index && info.transcript_index.transcript_name) {
            const found3 = CONFIG.categories.find(c => c.name === info.transcript_index.transcript_name);
            if (found3) return found3.name;
            return info.transcript_index.transcript_name;
        }
    } catch (e) {
        // ignore
    }
    return '';
}
    // 获取课程元信息：duration + completionType(time/other)
    async function getCourseMeta(courseId, headers) {
        try {
            const rest = await httpGet(`${CONFIG.courseInfoUrlRest}${courseId}`, headers);
            if (rest && rest.code === 200 && rest.data) {
                const d = rest.data;
                let completionType = null;
                // 可能字段：completion_flag / completion_type / completion_flag_text
                if (d.completion_flag) completionType = String(d.completion_flag).toLowerCase();
                else if (d.completion_type) completionType = String(d.completion_type).toLowerCase();
                else if (d.completion_flag_text) {
                    // 若文本中包含“分钟”，视为 time
                    completionType = /分钟/.test(String(d.completion_flag_text)) ? 'time' : 'other';
                } else if (d.transcript_index_type && d.transcript_index_type.duration != null) {
                    // 存在明确 duration 时倾向认为 time
                    completionType = 'time';
                }
                    return {
                        duration: d.duration != null ? d.duration : null,
                        completionType: completionType || 'other'
                    };
            }
        } catch (e) {
            // 忽略错误
        }
            return { duration: null, completionType: 'other' };
    }

// 解析课程标题：优先 info，其次 REST，最后我的课程列表
async function resolveCourseTitle(courseId, info, headers) {
    if (info) {
        const t = info.course_title || info.title || info.name || info.course_name;
        if (t) return t;
    }
    try {
        const rest = await httpGet(`${CONFIG.courseInfoUrlRest}${courseId}`, headers);
        if (rest && rest.code === 200 && rest.data) {
            const d = rest.data;
            const t2 = d.course_title || d.title || d.name || d.course_name;
            if (t2) return t2;
        }
    } catch {}
    try {
        const list = await httpGet(CONFIG.myCourseListUrl, headers);
        if (list && list.code === 200 && list.data && Array.isArray(list.data.items)) {
            const found = list.data.items.find(x => String(x.course_id || x.id) === String(courseId));
            if (found) {
                const t3 = found.course_title || found.title || found.name || found.course_name;
                if (t3) return t3;
            }
        }
    } catch {}
    return String(courseId);
}


async function doSignIn(courseId, lat, lon, address, headers, typeStr, courseTitle) {
    const body = {
        course_id: courseId,
        sign_address: {
            address: address,
            latitude: lat,
            longitude: lon
        }
    };

    // 使用签到专用 headers（含 sign/timestamp/appCode）
    const signHeaders = buildSignHeaders(headers['Authorization']);

    const options = {
        url: CONFIG.signInUrl,
        headers: signHeaders,
        body: JSON.stringify(body)
    };

    try {
        const result = await httpPost(options);
        console.log(`📝 ${typeStr}结果: ${JSON.stringify(result)}`);
        if (result && result.code === 200) {
            console.log(`✅ ${typeStr}成功！`);
            notify($.name, `${typeStr}成功`, `课程: ${courseTitle}\n位置: ${address}`);
        } else {
            console.log(`❌ ${typeStr}失败！`);
            let failReason = "未知错误";
            if (result) {
                if (typeof result === 'object') {
                    failReason = result.msg || result.message || result.error || JSON.stringify(result);
                } else {
                    failReason = String(result);
                }
            }
            notify($.name, `${typeStr}失败`, `课程: ${courseTitle}\n原因: ${failReason}`);
        }
    } catch (e) {
        console.error(`❌ ${typeStr}请求异常: ${e}`);
        const errStr = (e && e.message) ? e.message : String(e);
        notify($.name, `${typeStr}异常`, `课程: ${courseTitle}\n错误: ${errStr}`);
    }
}

async function executeSign(courseId, info, headers, typeStr, courseTitle, options = {}) {
    const skipDelay = !!(options && options.skipDelay);
    console.log(`🚀 开始执行${typeStr}...`);
    // 获取位置信息
    if (info.sign_in_address && info.sign_in_address.length > 0) {
        const target = info.sign_in_address[0]; // 取第一个位置
        const range = parseFloat(target.range) || 200;
        const baseLat = parseFloat(target.latitude);
        const baseLon = parseFloat(target.longitude);
        const address = target.address;

        // 生成随机坐标
        const { lat, lon } = getRandomCoordinate(baseLat, baseLon, range);
        console.log(`📍 目标位置: ${address} (${baseLat}, ${baseLon}), 范围: ${range}m`);
        console.log(`🎲 随机位置: (${lat}, ${lon})`);

        // 执行签到
        await doSignIn(courseId, lat, lon, address, headers, typeStr, courseTitle);

        // 增加随机延时，避免并发过快（单 ID 时跳过等待）
        if (!skipDelay) {
            const delay = Math.floor(Math.random() * 15000) + 15000; // 15-30秒
            console.log(`⏳ 等待 ${(delay / 1000).toFixed(1)} 秒...`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    } else {
        console.log("❌ 未找到签到位置信息");
        notify($.name, `${typeStr}失败`, `课程: ${courseTitle}\n原因: 未找到位置信息`);
    }
}

// 判断是否处于某个时间窗口（signIn/signOut）
function isInWindow(info, kind) {
    const now = new Date();
    if (kind === 'signOut') {
        if (info.sign_out_start_time && info.sign_out_end_time) {
            const soStart = new Date(String(info.sign_out_start_time).replace(/-/g, '/'));
            const soEnd = new Date(String(info.sign_out_end_time).replace(/-/g, '/'));
            return now >= soStart && now <= soEnd;
        }
        return false;
    }
    if (kind === 'signIn') {
        if (info.sign_in_start_time && info.sign_in_end_time) {
            const siStart = new Date(String(info.sign_in_start_time).replace(/-/g, '/'));
            const siEnd = new Date(String(info.sign_in_end_time).replace(/-/g, '/'));
            return now >= siStart && now <= siEnd;
        }
        return false;
    }
    return false;
}

function parseTimeToMs(timeText) {
    if (!timeText) return NaN;
    const ts = new Date(String(timeText).replace(/-/g, '/')).getTime();
    return Number.isFinite(ts) ? ts : NaN;
}

// 仅屏蔽“签退截止已过”的课程；没有签退截止时间时不做屏蔽。
function isSignOutExpired(info) {
    if (!info || !info.sign_out_end_time) return false;
    const signOutEndMs = parseTimeToMs(info.sign_out_end_time);
    if (!Number.isFinite(signOutEndMs)) return false;
    return Date.now() > signOutEndMs;
}

// 生成范围内随机坐标
function getRandomCoordinate(lat, lon, rangeMeters) {
    // 1度纬度 ≈ 111km = 111000m
    // 1度经度 ≈ 111km * cos(lat)
    
    // 稍微缩小一点范围，确保在圈内
    const safeRange = rangeMeters * 0.8; 
    
    const r = safeRange / 111000; // 转换为度数的大致半径
    const u = Math.random();
    const v = Math.random();
    const w = r * Math.sqrt(u);
    const t = 2 * Math.PI * v;
    const x = w * Math.cos(t);
    const y = w * Math.sin(t);

    // x 是纬度偏移，y 是经度偏移（需要修正）
    const newLat = lat + x;
    const newLon = lon + y / Math.cos(lat * Math.PI / 180);

    return { lat: newLat, lon: newLon };
}

function httpGet(url, headers, timeoutMs) {
    return new Promise((resolve, reject) => {
        const reqOpt = { url, headers };
        if (timeoutMs && Number.isFinite(timeoutMs)) reqOpt.timeout = timeoutMs;
        $.get(reqOpt, (err, resp, data) => {
            if (err) {
                reject(err);
            } else {
                try {
                    const res = JSON.parse(data);
                    resolve(res);
                } catch (e) {
                    resolve(data);
                }
            }
        });
    });
}

function isRetryableNetworkError(err) {
    const msg = ((err && err.message) ? err.message : String(err || "")).toLowerCase();
    return (
        msg.includes("socket hang up") ||
        msg.includes("econnreset") ||
        msg.includes("etimedout") ||
        msg.includes("timeout") ||
        msg.includes("eai_again") ||
        msg.includes("network")
    );
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function httpPost(options) {
    return new Promise((resolve, reject) => {
        $.post(options, (err, resp, data) => {
            if (err) {
                reject(err);
            } else {
                try {
                    const res = JSON.parse(data);
                    resolve(res);
                } catch (e) {
                    resolve(data);
                }
            }
        });
    });
}

// --- Env Polyfill ---
function Env(t, e) {
    class s {
        constructor(t) {
            this.env = t
        }
    }
    return new class {
        constructor(t) {
            this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1
        }
        getdata(t) {
            let e = this.getval(t);
            if (/^@/.test(t)) {
                const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : "";
                if (r) try {
                    const t = JSON.parse(r);
                    e = t ? this.getval(i, t) : null
                } catch (t) {
                    e = ""
                }
            }
            return e
        }
        setdata(t, e) {
            let s = !1;
            if (/^@/.test(e)) {
                const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}";
                try {
                    const e = JSON.parse(h);
                    this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e))
                } catch (e) {
                    const o = {};
                    this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o))
                }
            } else s = this.setval(t, e);
            return s
        }
        getval(t) {
            return this.isQuanX ? $prefs.valueForKey(t) : ""
        }
        setval(t, e) {
            return this.isQuanX ? $prefs.setValueForKey(t, e) : ""
        }
        msg(e = t, s = "", i = "", r) {
            if (this.isQuanX) {
                // Quantumult X: $notify(title, subtitle, body, options)
                if (typeof $notify === 'function') {
                    $notify(e, s, i, r)
                } else {
                    console.log(`[notify] ${e} | ${s} | ${i}`)
                }
            }
        }
        get(t, e = (() => {})) {
            this.isQuanX && ("string" == typeof t && (t = {
                url: t
            }), t.method = "GET", $task.fetch(t).then(t => {
                e(null, t, t.body)
            }, t => e(t.error, null, null)))
        }
        post(t, e = (() => {})) {
            this.isQuanX && ("string" == typeof t && (t = {
                url: t
            }), t.method = "POST", $task.fetch(t).then(t => {
                e(null, t, t.body)
            }, t => e(t.error, null, null)))
        }
        done(t = {}) {
            this.isQuanX && (typeof $done === 'function') && $done(t)
        }
    }(t, e)
}

function decideSignType(info, statusHint) {
    const now = new Date();
    let canSign = false;
    let typeStr = "";

    // 判断在签退窗口
    if (info.sign_out_start_time && info.sign_out_end_time) {
        const soStart = new Date(info.sign_out_start_time.replace(/-/g, '/'));
        const soEnd = new Date(info.sign_out_end_time.replace(/-/g, '/'));
        if (now >= soStart && now <= soEnd) {
            canSign = true;
            typeStr = "签退";
        }
    }

    // 若不在签退窗口，再判断签到窗口
    if (!canSign && info.sign_in_start_time && info.sign_in_end_time) {
        const siStart = new Date(info.sign_in_start_time.replace(/-/g, '/'));
        const siEnd = new Date(info.sign_in_end_time.replace(/-/g, '/'));
        if (now >= siStart && now <= siEnd) {
            canSign = true;
            typeStr = "签到";
        }
    }

    // 如果传入了状态提示（0待签到/1待签退），并且两个窗口都可，仍旧优先签退
    if (canSign && typeStr === "签到" && statusHint === 1) {
        // 已在签退状态优先级，保持签退优先
        // 如果签退窗口同时也在，则已在上方优先返回“签退”
    }

    return { canSign, typeStr };
}
