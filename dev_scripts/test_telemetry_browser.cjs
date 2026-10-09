// End-to-end test of actual writer -> JSON -> bridge -> OpenMCT -> graph.
// Run from the flight repo: node dev_scripts/test_telemetry_browser.cjs
const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');
const {spawn} = require('node:child_process');
const readline = require('node:readline');
const root = path.resolve(__dirname, '..');
const dashboard = process.env.DASHBOARD_ROOT || root;
const {chromium} = require(path.join(dashboard, 'openmct-tutorial/node_modules/playwright-core'));

(async () => {
    const python = process.env.FLIGHT_PYTHON || path.join(root, '.venv/Scripts/python.exe');
    const fixture = spawn(python, ['-u', path.join(__dirname, 'telemetry_e2e_fixture.py')], {cwd: root});
    let stderr = '';
    fixture.stderr.on('data', data => { stderr += data; });
    const lines = readline.createInterface({input: fixture.stdout})[Symbol.asyncIterator]();
    async function response() {
        const next = await lines.next();
        if (next.done) throw Error('Fixture stopped: ' + stderr);
        return JSON.parse(next.value);
    }
    async function command(message) {
        fixture.stdin.write(JSON.stringify(message) + '\n');
        return response();
    }
    let browser;
    try {
        const config = await response();
        browser = await chromium.launch({executablePath: process.env.CHROME_PATH ||
            'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true});
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        // Only change the endpoint for this isolated test browser. Production
        // dashboard files and the user's existing localhost processes stay put.
        await page.addInitScript(port => {
            const Native = window.WebSocket;
            window.WebSocket = class extends Native {
                constructor(url, ...args) { super(url.replace(':8765', ':' + port), ...args); }
            };
        }, config.port);
        await page.goto(config.url);
        await page.getByText('Crazyflie', {exact: true}).click();
        await page.getByText('Position X', {exact: true}).first().click();
        assert.equal(await page.getByRole('button', {name: 'Time Conductor Settings'}).count(), 1,
                  'time selector must let users switch between live and saved flights');
        await page.evaluate(async () => {
            window.testObject = await openmct.objects.get({namespace: 'drone.telemetry', key: 'drone.position.x'});
            window.testPoints = [];
            window.testUnsubscribe = openmct.telemetry.subscribe(window.testObject, p => window.testPoints.push(p));
        });
        const base = Date.now() - 20000;
        const samples = Array.from({length: 15}, (_, i) => ({timestamp: base + i * 100,
            x: i / 4, y: i === 0 ? 0 : -i / 8}));
        // Late startup: save a batch first, with the browser already waiting.
        await command({action: 'write', samples: samples.slice(0, 5)});
        await command({action: 'start'});
        async function request(key) {
            return page.evaluate(async ({key, start, end}) => {
                const object = await openmct.objects.get({namespace: 'drone.telemetry', key});
                return openmct.telemetry.request(object, {start, end});
            }, {key, start: base, end: base + 2000});
        }
        await page.waitForFunction(() => window.testPoints.length >= 5);
        assert.equal((await request('drone.position.x')).length, 5);
        // Running flight: every sample in a batch must reach a live view.
        await command({action: 'write', samples: samples.slice(5, 10)});
        await page.waitForFunction(timestamp => window.testPoints.some(p => p.timestamp === timestamp), samples[9].timestamp);
        // Offline gap: keep writing with bridge stopped; restart must backfill.
        await command({action: 'stop'});
        await command({action: 'write', samples: samples.slice(10)});
        await command({action: 'start'});
        await page.waitForFunction(timestamp => window.testPoints.some(p => p.timestamp === timestamp), samples[14].timestamp);
        for (const axis of ['x', 'y']) {
            const key = 'drone.position.' + axis;
            const expected = samples.map(p => ({id: key, timestamp: p.timestamp, value: p[axis]}));
            assert.deepEqual(await request(key), expected);
        }
        // Finished flight: refresh with no new samples, and load the same values.
        await page.reload();
        await page.waitForFunction(() => window.openmct && openmct.router.started);
        assert.equal((await request('drone.position.x')).length, 15);
        // Select a fixed historical window: actual saved data, not retimestamped.
        await page.evaluate(({start, end}) => openmct.time.setMode('fixed', {start, end}),
                            {start: base - 100, end: base + 2000});
        await page.waitForTimeout(800);
        assert.equal(await page.locator('canvas').count(), 2);
        // Check pixels of the blue data trace, not just presence of graph axes.
        const plotImage = await page.locator('canvas').first().screenshot();
        const bluePixels = await page.evaluate(async base64 => {
            // Plot uses WebGL: inspect the rendered screenshot via a separate
            // 2D canvas instead of requesting a conflicting context type.
            const image = new Image();
            image.src = 'data:image/png;base64,' + base64;
            await image.decode();
            const canvas = document.createElement('canvas');
            canvas.width = image.width; canvas.height = image.height;
            const context = canvas.getContext('2d');
            context.drawImage(image, 0, 0);
            const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
            let count = 0;
            for (let i = 0; i < pixels.length; i += 4) {
                if (pixels[i + 2] > 150 && pixels[i + 1] > 80 && pixels[i] < 130 && pixels[i + 3] > 0) count++;
            }
            return count;
        }, plotImage.toString('base64'));
        assert.ok(bluePixels > 30, 'expected a visible blue data trace');
        assert.deepEqual(errors, []);
        const screenshot = path.join(os.tmpdir(), 'flight-json-openmct-e2e.png');
        await page.screenshot({path: screenshot, fullPage: true});
        console.log(JSON.stringify({passed: true, samplesPerMetric: 15, metrics: 2,
            tested: ['dashboard before bridge', 'live batches', 'bridge restart and backfill',
                     'saved flight after refresh', 'exact X/Y values and timestamps', 'fixed-time graph pixels'],
            bluePixels, screenshot}));
    } catch (error) {
        console.error(stderr.slice(-5000));
        throw error;
    } finally {
        if (browser) await browser.close();
        fixture.stdin.end(JSON.stringify({action: 'exit'}) + '\n');
        await new Promise(resolve => {
            if (fixture.exitCode !== null) return resolve();
            fixture.once('exit', resolve);
        });
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
