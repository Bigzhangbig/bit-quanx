/*
 * 脚本名称：本地工具-获取活动二维码
 * 描述：获取当前进行中或已结束但未签退的活动二维码，保存到 qrcodes 目录。
 * 用法：node local_dekt_get_qr.js
 */
const fs = require('fs');
const path = require('path');
const QRCode = require('qrcode');
const Env = require('./local_env');
const { spawnSync } = require('child_process');

global.Env = Env;
const $ = new Env("获取二维码");

// 配置
const CONFIG = {
    tokenKey: "bit_sc_token",
    headersKey: "bit_sc_headers",
    // 签到列表接口
    listUrl: "https://qcbldekt.bit.edu.cn/api/transcript/course/signIn/list?page=1&limit=20&type=1",
    infoUrl: "https://qcbldekt.bit.edu.cn/api/transcript/checkIn/info",
    qrBaseUrl: "https://qcbldekt.bit.edu.cn/qrcode/event/?course_id=",
    saveDir: path.join(__dirname, 'qrcodes'),
    categories: [
        { id: 1, name: "理想信念" },
        { id: 2, name: "科学素养" },
        { id: 3, name: "社会贡献" },
        { id: 4, name: "团队协作" },
        { id: 5, name: "文化互鉴" },
        { id: 6, name: "健康生活" }
    ]
};

// 确保保存目录存在
if (!fs.existsSync(CONFIG.saveDir)) {
    fs.mkdirSync(CONFIG.saveDir);
}

(async () => {
    console.log("=== 开始获取活动二维码 ===");
    // 先同步 .env（从 Gist 拉取最新 Token/Headers）
    try {
        const syncPath = path.join(__dirname, 'local_sync_gist.js');
        spawnSync(process.execPath, [syncPath], { stdio: 'inherit' });
    } catch (e) {
        console.log('[LocalSync] 同步环境失败（忽略继续）:', e.message || e);
    }
    
    const token = $.getdata(CONFIG.tokenKey);
    if (!token) {
        console.log("❌ 未找到 Token，请先配置 .env");
        return;
    }

    let headers = {};
    try {
        headers = JSON.parse($.getdata(CONFIG.headersKey) || "{}");
    } catch (e) {
        console.log("⚠️ Headers 解析失败，将只使用 Token");
    }
    
    // 确保 headers 中有必要的字段
    if (!headers["Authorization"] && token) {
        headers["Authorization"] = token;
    }

    const options = {
        url: CONFIG.listUrl,
        headers: headers
    };

    $.get(options, async (err, resp, data) => {
        if (err) {
            console.log("❌ 请求失败:", err);
            return;
        }
        
        try {
            const res = JSON.parse(data);
            // 适配不同的 API 响应结构
            const list = (res.data && res.data.items) || (res.data && res.data.list) || [];
            
            if (list.length > 0 || (res.code === 200 || res.status === "success")) {
                console.log(`✅ 获取成功，共找到 ${list.length} 个活动`);
                
                if (list.length === 0) {
                    console.log("没有正在进行的签到活动。");
                }

                for (const item of list) {
                    const courseId = item.courseId || item.course_id;
                    const title = item.courseName || item.course_title;
                    const statusLabel = item.status_label || item.status;
                    
                    // 获取详细信息
                    const info = await getCourseInfo(courseId, headers);
                    
                    // 获取分类名称
                    // 优先使用 transcript_index_id，如果没有则尝试使用 transcript_name 匹配
                    let category = null;
                    const catId = (info && info.transcript_index_id) || item.transcript_index_id;
                    
                    if (catId) {
                        category = CONFIG.categories.find(c => c.id == catId);
                    } else if (info && info.transcript_name) {
                        category = CONFIG.categories.find(c => c.name === info.transcript_name);
                    }
                    
                    const categoryName = category ? category.name : (info && info.transcript_name) || "未知分类";

                    // 构造二维码链接
                    const qrUrl = `${CONFIG.qrBaseUrl}${courseId}`;
                    
                    // 文件名处理：去除非法字符
                    const safeTitle = title.replace(/[\\/:*?"<>|]/g, "_");
                    const fileName = `${courseId}_${safeTitle}.png`;
                    const filePath = path.join(CONFIG.saveDir, fileName);

                    console.log(`\n----------------------------------------`);
                    console.log(`活动名称: ${title}`);
                    console.log(`活动ID:   ${courseId}`);
                    console.log(`活动分类: ${categoryName}`);
                    console.log(`状态:     ${statusLabel}`);
                    
                    // 判断完成方式
                    if (item.completion_flag === 'time') {
                        console.log(`完成方式: ⏱️ 签到计时`);
                        if (item.sign_in_start_time) {
                            console.log(`签到时间: ${item.sign_in_start_time} - ${item.sign_in_end_time}`);
                        }
                        if (item.sign_out_start_time) {
                            console.log(`签退时间: ${item.sign_out_start_time} - ${item.sign_out_end_time}`);
                        }
                    } else {
                        console.log(`完成方式: ✅ ${item.completion_flag_text || '非计时任务'}`);
                    }

                    console.log(`二维码链接: ${qrUrl}`);
                    
                    // 仅为计时活动且在签到/签退时间内生成二维码
                    if (item.completion_flag === 'time') {
                        const now = new Date();
                        const parseTime = (t) => t ? new Date(t.replace(/-/g, '/')) : null;
                        
                        const signInStart = parseTime(item.sign_in_start_time);
                        const signInEnd = parseTime(item.sign_in_end_time);
                        const signOutStart = parseTime(item.sign_out_start_time);
                        const signOutEnd = parseTime(item.sign_out_end_time);
                        
                        let inTimeRange = false;
                        let timeMsg = "";

                        const isSignIn = statusLabel && String(statusLabel).trim() === "待签到";
                        const isSignOut = statusLabel && String(statusLabel).trim() === "待签退";

                        if (isSignIn) {
                            if (!signInEnd || now <= signInEnd) {
                                inTimeRange = true;
                                timeMsg = "🟢 当前状态为待签到";
                            } else {
                                timeMsg = "🔴 已过签到截止时间";
                            }
                        } else if (isSignOut) {
                            if (!signOutEnd || now <= signOutEnd) {
                                inTimeRange = true;
                                timeMsg = "🟢 当前状态为待签退";
                            } else {
                                timeMsg = "🔴 已过签退截止时间";
                            }
                        } else if (signInStart && signInEnd && now >= signInStart && now <= signInEnd) {
                            inTimeRange = true;
                            timeMsg = "🟢 当前在签到时间内";
                        } else if (signOutStart && signOutEnd && now >= signOutStart && now <= signOutEnd) {
                            inTimeRange = true;
                            timeMsg = "🟢 当前在签退时间内";
                        } else {
                            timeMsg = "⏳ 当前不在签到/签退时间范围内";
                        }
                        
                        console.log(timeMsg);

                        if (inTimeRange) {
                            try {
                                // 1. 保存图片
                                await QRCode.toFile(filePath, qrUrl, {
                                    color: {
                                        dark: '#000000',
                                        light: '#ffffff'
                                    },
                                    width: 300
                                });
                                console.log(`✅ 二维码已保存: ${fileName}`);

                                // 2. 在终端直接打印二维码
                                const string = await QRCode.toString(qrUrl, { type: 'terminal', small: true });
                                console.log(string);
                            } catch (qrErr) {
                                console.error(`❌ 生成二维码失败: ${qrErr.message}`);
                            }
                        } else {
                            console.log("🚫 跳过生成二维码");
                        }
                    } else {
                        console.log("ℹ️ 非计时活动，跳过生成二维码");
                    }
                    
                    // 检查是否需要签到/签退 (仅针对计时类活动)
                    if (item.completion_flag === 'time') {
                        const isSignIn = statusLabel && String(statusLabel).trim() === "待签到";
                        const isSignOut = statusLabel && String(statusLabel).trim() === "待签退";
                        
                        if (isSignIn && item.sign_in_end_time) {
                            console.log(`⚠️ 签到截止: ${item.sign_in_end_time}`);
                        } else if (isSignOut && item.sign_out_end_time) {
                            console.log(`⚠️ 签退截止: ${item.sign_out_end_time}`);
                        }
                    }
                }
                console.log(`\n----------------------------------------`);
                console.log(`所有二维码已保存至: ${CONFIG.saveDir}`);
            } else {
                console.log("❌ 获取列表失败或响应格式错误:", JSON.stringify(res).substring(0, 200));
            }
        } catch (e) {
            console.log("❌ 解析响应失败:", e);
            console.log("原始响应 (前200字符):", data.substring(0, 200));
        }
    });
})();

function httpGet(url, headers) {
    return new Promise((resolve, reject) => {
        $.get({ url, headers }, (err, resp, data) => {
            if (err) {
                reject(err);
            } else {
                try {
                    resolve(JSON.parse(data));
                } catch (e) {
                    resolve(data);
                }
            }
        });
    });
}

async function getCourseInfo(courseId, headers) {
    const url = `${CONFIG.infoUrl}?course_id=${courseId}`;
    try {
        const data = await httpGet(url, headers);
        if (data && data.code === 200) {
            return data.data;
        }
        return null;
    } catch (e) {
        console.log(`获取课程详情失败: ${e}`);
        return null;
    }
}
