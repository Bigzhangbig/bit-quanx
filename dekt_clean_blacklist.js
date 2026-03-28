/*
 * 脚本名称：北理工第二课堂-清理黑名单
 * 作者：Gemini for User
 * 描述：自动移除黑名单中已结束/已取消的课程ID
 * [task_local]
 * 0 3 * * * https://github.com/Bigzhangbig/bit-dekt-quanx/raw/refs/heads/main/dekt_clean_blacklist.js, tag=清理黑名单, enabled=true
 */

const $ = new Env("北理工第二课堂-清理黑名单");

// 统一时间戳日志工具
function _nowTs() {
    const d = new Date();
    const pad = (n, w = 2) => String(n).padStart(w, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${String(d.getMilliseconds()).padStart(3, '0')}`;
}
function log(...args) {
    console.log(`[${_nowTs()}]`, ...args);
}

// 统一通知函数：支持 debug 模式和微信链接
function notify(title, subtitle = "", body = "", options = {}) {
    const isDebug = String($.getdata('bit_sc_debug') || 'false').toLowerCase() === 'true';
    if (isDebug) {
        log(`[NOTIFY] ${title} | ${subtitle} | ${body}`);
    } else {
        $.msg(title, subtitle, body, options);
    }
}

const CONFIG = {
    blacklistKey: "bit_sc_blacklist",
    tokenKey: "bit_sc_token",
    debugKey: "bit_sc_debug"
};

(async () => {
    try {
        const token = $.getdata(CONFIG.tokenKey);
        const authHeader = normalizeAuthToken(token);
        if (!authHeader) {
            notify($.name, "未获取到有效Token", "请先运行cookie脚本获取Token", { force: true });
            $done();
            return;
        }

        // 读取黑名单（按 boxjs.json 约定：逗号分隔的文本）
        const blacklistStr = $.getdata(CONFIG.blacklistKey) || "";
        let blacklist = [];
        try {
            // 兼容用户误填为 JSON 数组的情况
            const maybeJson = blacklistStr.trim();
            if (maybeJson.startsWith("[") && maybeJson.endsWith("]")) {
                const arr = JSON.parse(maybeJson);
                if (Array.isArray(arr)) blacklist = arr.map(x => String(x).trim()).filter(Boolean);
            } else {
                blacklist = blacklistStr.split(/[，,]/).map(id => id.trim()).filter(id => id);
            }
        } catch {
            blacklist = blacklistStr.split(/[，,]/).map(id => id.trim()).filter(id => id);
        }

        if (blacklist.length === 0) {
            notify($.name, "黑名单为空", "无需清理");
            $done();
            return;
        }

        // 备份原始黑名单到一个时间戳键，便于恢复
        try {
            const now = new Date();
            const pad = n => String(n).padStart(2, '0');
            const ts = `${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
            const backupKey = `${CONFIG.blacklistKey}_backup_${ts}`;
            $.setdata(blacklist.join(","), backupKey);
            console.log(`[clean_blacklist] 已备份旧黑名单到 ${backupKey}`);
        } catch (e) { console.log(`[clean_blacklist] 备份旧黑名单失败: ${e}`); }

        // 逐个 ID 检查：优先通过课程详情接口判断状态；若失败则分页获取课程列表做兜底检查
        const remaining = [];
        const removed = [];
        const unknownRemoved = [];

        // 预取一次全部课程列表作为备份（如果 API 支持分页，会完整拉取）
        let fullCourseList = null;
        try { fullCourseList = await getCourseListAll(authHeader); } catch (e) { fullCourseList = null; }

        for (const id of blacklist) {
            let keep = false;
            try {
                const info = await getCourseInfoById(id, authHeader);
                if (info && info.status !== undefined && info.status !== null) {
                    // status 3/4 表示已结束或已取消 -> 不保留
                    if (info.status !== 3 && info.status !== 4) keep = true;
                } else {
                    // 未从详情获得有效状态，尝试在全量列表中查找
                    if (Array.isArray(fullCourseList)) {
                        const course = fullCourseList.find(c => c && String(c.id) === String(id));
                        if (course && course.status !== 3 && course.status !== 4) keep = true;
                        else if (course) keep = false;
                    }
                }
            } catch (e) {
                console.log(`[clean_blacklist] 查询课程 ${id} 详情时异常: ${e}`);
            }

            if (keep) {
                remaining.push(id);
            } else if (fullCourseList) {
                const course = fullCourseList.find(c => c && String(c.id) === String(id));
                if (!course) {
                    // 在全量列表未找到 -> 该课程可能已被删除或历史课程，视作需要移除
                    removed.push(id);
                } else {
                    // 在全量列表找到但状态为 3 或 4
                    removed.push(id);
                }
            } else {
                // 无法判定（既未获得详情也无全量列表），为安全起见记录到 unknownRemoved 并移除
                unknownRemoved.push(id);
            }
        }
        // 写回 BoxJS（统一为逗号分隔格式）
        $.setdata(remaining.join(","), CONFIG.blacklistKey);

        // 构造通知信息
        let body = `剩余ID: ${remaining.join(",") || "无"}`;
        if (removed.length > 0) body += `\n已移除(ID 状态为已结束/已取消): ${removed.join(",")}`;
        if (unknownRemoved.length > 0) body += `\n已移除(未知，无法确认状态): ${unknownRemoved.join(",")}`;
        notify($.name, "黑名单已清理", body);
    } catch (e) {
        notify($.name, "脚本异常", String(e), { force: true });
    }
    $done();
})();

function normalizeAuthToken(token) {
    if (!token) return "";
    const t = String(token).trim();
    if (!t) return "";
    return /^Bearer\s+/i.test(t) ? t : `Bearer ${t}`;
}

async function getCourseList(authHeader) {
    const url = "https://qcbldekt.bit.edu.cn/api/course/list";
    const myRequest = {
        url: url,
        method: "GET",
        headers: {
            "Authorization": authHeader
        }
    };
    return new Promise((resolve) => {
        if ($.isQuanX) {
            $task.fetch(myRequest).then(
                response => {
                    try {
                        const body = JSON.parse(response.body);
                        // 严格按抓包结构：data.items 为数组
                        const list = body && body.data && Array.isArray(body.data.items) ? body.data.items : null;
                        resolve(list || null);
                    } catch (e) {
                        resolve(null);
                    }
                },
                () => resolve(null)
            );
        } else {
            resolve(null);
        }
    });
}

// 按 ID 获取课程详情（优先用于确认单个课程状态）
async function getCourseInfoById(courseId, authHeader) {
    const url = `https://qcbldekt.bit.edu.cn/api/course/info/${courseId}`;
    const myRequest = {
        url: url,
        method: "GET",
        headers: {
            "Authorization": authHeader
        }
    };
    return new Promise((resolve) => {
        if ($.isQuanX) {
            $task.fetch(myRequest).then(
                response => {
                    try {
                        const body = JSON.parse(response.body);
                        // 期望结构: { code: 200, data: { id:..., status: ... } }
                        const data = body && (body.data || body.json && body.json.data) ? (body.data || body.json && body.json.data) : null;
                        resolve(data || null);
                    } catch (e) {
                        resolve(null);
                    }
                },
                () => resolve(null)
            );
        } else {
            resolve(null);
        }
    });
}

// 分页拉取全部课程列表（尽可能遍历所有页，取决于后端分页支持）
async function getCourseListAll(authHeader) {
    const pageSize = 100; // 尝试大页大小以减少请求次数
    let page = 1;
    const all = [];
    while (true) {
        const url = `https://qcbldekt.bit.edu.cn/api/course/list?page=${page}&limit=${pageSize}`;
        const myRequest = {
            url: url,
            method: "GET",
            headers: {
                "Authorization": authHeader
            }
        };
        const pageItems = await new Promise((resolve) => {
            if ($.isQuanX) {
                $task.fetch(myRequest).then(
                    response => {
                        try {
                            const body = JSON.parse(response.body);
                            const list = body && body.data && Array.isArray(body.data.items) ? body.data.items : null;
                            resolve(list || null);
                        } catch (e) { resolve(null); }
                    },
                    () => resolve(null)
                );
            } else resolve(null);
        });

        if (!Array.isArray(pageItems)) {
            // 接口失败或非 QuanX 环境，返回 null 表示无法获取全量
            return null;
        }

        if (pageItems.length === 0) break;
        all.push(...pageItems);
        if (pageItems.length < pageSize) break; // 最后一页
        page++;
        // 为防止触发频率限制，短暂等待
        await new Promise(r => setTimeout(r, 200));
    }
    return all;
}

// --- Env Polyfill ---
function Env(t, e) { class s { constructor(t) { this.env = t } } return new class { constructor(t) { this.name = t, this.logs = [], this.isSurge = !1, this.isQuanX = "undefined" != typeof $task, this.isLoon = !1 } getdata(t) { let e = this.getval(t); if (/^@/.test(t)) { const [, s, i] = /^@(.*?)\.(.*?)$/.exec(t), r = s ? this.getval(s) : ""; if (r) try { const t = JSON.parse(r); e = t ? this.getval(i, t) : null } catch (t) { e = "" } } return e } setdata(t, e) { let s = !1; if (/^@/.test(e)) { const [, i, r] = /^@(.*?)\.(.*?)$/.exec(e), o = this.getval(i), h = i ? "null" === o ? null : o || "{}" : "{}"; try { const e = JSON.parse(h); this.setval(r, t, e), s = !0, this.setval(i, JSON.stringify(e)) } catch (e) { const o = {}; this.setval(r, t, o), s = !0, this.setval(i, JSON.stringify(o)) } } else s = this.setval(t, e); return s } getval(t) { return this.isQuanX ? $prefs.valueForKey(t) : "" } setval(t, e) { return this.isQuanX ? $prefs.setValueForKey(t, e) : "" } msg(e = t, s = "", i = "", r) { if (this.isQuanX) { if (typeof $notify === 'function') { $notify(e, s, i, r) } else { console.log(`[notify] ${e} | ${s} | ${i}`) } } } get(t, e = (() => { })) { this.isQuanX && ("string" == typeof t && (t = { url: t }), t.method = "GET", $task.fetch(t).then(t => { e(null, t, t.body) }, t => e(t.error, null, null))) } done(t = {}) { this.isQuanX && (typeof $done === 'function') && $done(t) } }(t, e) }
