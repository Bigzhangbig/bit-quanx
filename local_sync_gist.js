const fs = require('fs');
const path = require('path');
const https = require('https');

const envFilePath = path.join(__dirname, 'env.json');

function loadEnv() {
    if (fs.existsSync(envFilePath)) {
        return JSON.parse(fs.readFileSync(envFilePath, 'utf8'));
    }
    return {};
}

function saveEnv(data) {
    fs.writeFileSync(envFilePath, JSON.stringify(data, null, 4));
    console.log("[System] env.json updated.");
}

async function syncFromGist() {
    const envData = loadEnv();
    const githubToken = envData.bit_sc_github_token;
    const gistId = envData.bit_sc_gist_id;
    const filename = envData.bit_sc_gist_filename || "bit_cookies.json";

    if (!githubToken || !gistId) {
        console.error("❌ Missing Gist configuration in env.json (bit_sc_github_token, bit_sc_gist_id)");
        console.log("Please fill in these fields in env.json to enable Gist sync.");
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
        }
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
