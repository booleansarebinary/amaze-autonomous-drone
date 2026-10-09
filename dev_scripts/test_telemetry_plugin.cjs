// Run: node --test dev_scripts/test_telemetry_plugin.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = process.env.DASHBOARD_ROOT || path.resolve(__dirname, '../../amaze-dashboard');
const source = fs.readFileSync(path.join(root, 'dashboard/realtime-telemetry-plugin.js'), 'utf8');
const metric = {type: 'drone.telemetry', identifier: {key: 'drone.position.x'}};
const point = {id: metric.identifier.key, timestamp: 1700000000000, value: -1.25};

function setup() {
    const sockets = [], timers = [];
    let provider;
    class Socket {
        constructor() { this.readyState = 0; this.sent = []; sockets.push(this); }
        send(value) { this.sent.push(JSON.parse(value)); }
        close() { this.readyState = 3; this.onclose(); }
        open() { this.readyState = 1; if (this.onopen) this.onopen(); }
        frame(value) { this.onmessage({data: value}); }
    }
    const context = {WebSocket: Socket, console, Date,
        window: {location: {hostname: 'localhost', protocol: 'http:'}},
        setTimeout: (fn, delay) => { const timer = {fn, delay}; timers.push(timer); return timer; },
        clearTimeout: timer => { if (timer) timer.cancelled = true; }};
    vm.createContext(context);
    vm.runInContext(source, context);
    context.RealtimeTelemetryPlugin()({telemetry: {addProvider: p => { provider = p; }}});
    return {provider, sockets, timers};
}

test('invalid/unknown frames are ignored; negative and zero values remain numeric', () => {
    const {provider, sockets} = setup();
    const received = [];
    provider.subscribe(metric, p => received.push(p));
    for (const frame of ['bad json', 'null', '[]', '{}',
        JSON.stringify({...point, id: 'unknown'}), JSON.stringify({...point, value: '1'}),
        JSON.stringify({...point, timestamp: -1}), JSON.stringify({...point, timestamp: true}),
        '{"id":"drone.position.x","timestamp":1000,"value":1e999}']) {
        assert.doesNotThrow(() => sockets[0].frame(frame));
    }
    assert.equal(received.length, 0);
    sockets[0].frame(JSON.stringify(point));
    sockets[0].frame(JSON.stringify({...point, value: 0}));
    assert.deepEqual(received.map(p => p.value), [-1.25, 0]);
});

test('two subscribers, unsubscribe twice, and callback failure are isolated', () => {
    const {provider, sockets} = setup();
    let count = 0;
    const remove = provider.subscribe(metric, () => { throw Error('broken view'); });
    provider.subscribe(metric, () => { count++; });
    assert.doesNotThrow(() => sockets[0].frame(JSON.stringify(point)));
    remove(); remove();
    sockets[0].frame(JSON.stringify(point));
    assert.equal(count, 2);
});

test('history request waits for connection and returns exact saved points', async () => {
    const {provider, sockets} = setup();
    const result = provider.request(metric, {start: point.timestamp, end: point.timestamp});
    sockets[0].open();
    const request = sockets[0].sent.find(p => p.type === 'history');
    assert.ok(request, 'must request saved history instead of returning []');
    assert.equal(request.start, point.timestamp);
    sockets[0].frame(JSON.stringify({type: 'history', requestId: request.requestId, points: [point]}));
    assert.equal(JSON.stringify(await result), JSON.stringify([point]));
});

test('connection loss retries pending requests; timeout reports failure', async () => {
    const {provider, sockets, timers} = setup();
    sockets[0].open();
    const result = provider.request(metric, {start: 0, end: point.timestamp});
    sockets[0].close();
    const reconnect = timers.find(t => t.delay === 1000 && !t.cancelled);
    assert.ok(reconnect);
    reconnect.fn();
    sockets[1].open();
    const request = sockets[1].sent.find(p => p.type === 'history');
    assert.ok(request);
    sockets[1].frame(JSON.stringify({type: 'history', requestId: request.requestId, points: [point]}));
    assert.equal((await result).length, 1);
    const pending = provider.request(metric, {start: 0, end: 1});
    const rejection = assert.rejects(pending, /telemetry|history|timeout/i);
    const timeout = timers.filter(t => t.delay > 1000 && !t.cancelled).at(-1);
    assert.ok(timeout);
    timeout.fn();
    await rejection;
});
