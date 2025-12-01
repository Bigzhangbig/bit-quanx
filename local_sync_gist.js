/*
 * 脚本名称：本地工具-Gist同步
 * 描述：从 GitHub Gist 拉取最新的 Token 配置到本地 .env。
 * 用法：node local_sync_gist.js
 */
const fs = require('fs');
const path = require('path');
const https = require('https');

const envFilePath = path.join(__dirname, '.env');

function loadEnv() {
    if (fs.existsSync(envFilePath)) {
        const content = fs.readFileSync(envFilePath, 'utf8');
        const result = {};
        content.split('\n').forEach(line => {
            line = line.trim();
            if (line && !line.startsWith('#')) {
                const parts = line.split('=');
                const key = parts[0].trim();
                const val = parts.slice(1).join('=').trim();
                if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
                    result[key] = val.slice(1, -1);
                } else {
                    result[key] = val;
                }
            }
        });
        return result;
    }
    return {};
}

function saveEnv(data) {
    const content = Object.entries(data)
        .map(([key, val]) => `${key}=${val}`)
        .join('\n');
    fs.writeFileSync(envFilePath, content);
    console.log("[System] .env updated.");
}

async function syncFromGist() {
    const envData = loadEnv();
    const githubToken = envData.bit_sc_github_token;
    const gistId = envData.bit_sc_gist_id;
    const filename = envData.bit_sc_gist_filename || "bit_cookies.json";

    if (!githubToken || !gistId) {
        console.error("❌ Missing Gist configuration in .env (bit_sc_github_token, bit_sc_gist_id)");
        console.log("Please fill in these fields in .env to enable Gist sync.");
        return;
    }

    console.log(`[System] Fetching Gist: ${gistId}...`);

    const options = {
        hostname: 'api.github.com',
        path: `/gists/${gistId}`,
        method: 'GET',
        headers: {
            'User-Agent': 'Node.js Script',
            'Authorization': `token ${githubToken}`
        },
        rejectUnauthorized: false // 忽略 SSL 证书错误
    };

    const req = https.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => data += chunk);
        res.on('end', () => {
            if (res.statusCode === 200) {
                try {
                    const gist = JSON.parse(data);
                    const file = gist.files[filename];
                    if (file) {
                        const content = JSON.parse(file.content);
                        let updated = false;

                        if (content.token && content.token !== envData.bit_sc_token) {
                            envData.bit_sc_token = content.token;
                            console.log("✅ Token updated from Gist");
                            updated = true;
                        } else {
                            console.log("ℹ️ Token is up to date");
                        }

                        if (content.headers) {
                            const newHeaders = JSON.stringify(content.headers);
                            if (newHeaders !== envData.bit_sc_headers) {
                                envData.bit_sc_headers = newHeaders;
                                console.log("✅ Headers updated from Gist");
                                updated = true;
                            }
                        }

                        // 同步 user_id 到 .env，供取消报名等脚本使用
                        if (typeof content.user_id !== 'undefined' && content.user_id !== envData.bit_sc_user_id) {
                            envData.bit_sc_user_id = String(content.user_id);
                            // 兼容 dekt_user_id 键名
                            envData.dekt_user_id = String(content.user_id);
                            console.log("✅ User ID updated from Gist");
                            updated = true;
                        }

                        if (updated) {
                            saveEnv(envData);
                        } else {
                            console.log("[System] No changes needed.");
                        }
                    } else {
                        console.error(`❌ File ${filename} not found in Gist`);
                    }
                } catch (e) {
                    console.error("❌ Failed to parse Gist response:", e.message);
                }
            } else {
                console.error(`❌ Gist fetch failed: ${res.statusCode} ${res.statusMessage}`);
            }
        });
    });

    req.on('error', (e) => {
        console.error(`❌ Request error: ${e.message}`);
    });

    req.end();
}

syncFromGist();
