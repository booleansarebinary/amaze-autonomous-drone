function RealtimeTelemetryPlugin() {
    return function install(openmct) {
        var listeners = Object.create(null);
        var pending = Object.create(null);
        var lastSeen = Object.create(null);
        var nextRequest = 0;
        var known = ['drone.position.x', 'drone.position.y'];
        var socket;

        function valid(point) {
            return point && known.indexOf(point.id) !== -1 &&
                Number.isInteger(point.timestamp) && point.timestamp >= 0 &&
                point.timestamp <= 8640000000000000 &&
                typeof point.value === 'number' && Number.isFinite(point.value);
        }

        function deliver(point) {
            if (!valid(point)) return;
            lastSeen[point.id] = Math.max(lastSeen[point.id] || 0, point.timestamp);
            (listeners[point.id] || []).slice().forEach(function (callback) {
                try { callback(point); }
                catch (error) { console.warn('Telemetry view callback failed', error); }
            });
        }

        function requestHistory(key, start, end) {
            return new Promise(function (resolve, reject) {
                var id = String(++nextRequest);
                var message = {type: 'history', requestId: id, id: key, start: start, end: end};
                var timer = setTimeout(function () {
                    delete pending[id];
                    reject(new Error('Telemetry history timeout: check the bridge is running'));
                }, 10000);
                pending[id] = {message: message, resolve: resolve, timer: timer};
                if (socket && socket.readyState === 1) socket.send(JSON.stringify(message));
            });
        }

        function connect() {
            var scheme = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            socket = new WebSocket(scheme + window.location.hostname + ':8765');
            socket.onopen = function () {
                Object.keys(pending).forEach(function (id) {
                    socket.send(JSON.stringify(pending[id].message));
                });
                // Recover samples missed during a bridge restart or network
                // interruption, using their original flight timestamps.
                Object.keys(listeners).forEach(function (key) {
                    requestHistory(key, lastSeen[key] || Date.now() - 60000, Date.now())
                        .then(function (points) { points.forEach(deliver); })
                        .catch(function (error) { console.warn(error.message); });
                });
            };
            socket.onmessage = function (event) {
                var point;
                try {
                    point = JSON.parse(event.data);
                } catch (error) {
                    // Ignore a corrupt frame; the next telemetry frame can
                    // still update the live display.
                    return;
                }
                if (!point) return;
                if (point.type === 'history') {
                    var request = pending[point.requestId];
                    if (request && Array.isArray(point.points)) {
                        clearTimeout(request.timer);
                        delete pending[point.requestId];
                        request.resolve(point.points.filter(function (sample) {
                            return valid(sample) && sample.id === request.message.id &&
                                sample.timestamp >= request.message.start && sample.timestamp <= request.message.end;
                        }).sort(function (a, b) { return a.timestamp - b.timestamp; }));
                    }
                    return;
                }
                deliver(point);
            };
            // The dashboard may open before the bridge. Retry until it is up,
            // and reconnect automatically if the bridge is restarted.
            socket.onclose = function () {
                setTimeout(connect, 1000);
            };
            socket.onerror = function () {
                socket.close();
            };
        }

        connect();

        openmct.telemetry.addProvider({
            supportsRequest: function (domainObject) {
                return domainObject.type === 'drone.telemetry';
            },
            request: function (domainObject, options) {
                return requestHistory(domainObject.identifier.key, options.start, options.end);
            },
            supportsSubscribe: function (domainObject) {
                return domainObject.type === 'drone.telemetry';
            },
            subscribe: function (domainObject, callback) {
                var key = domainObject.identifier.key;
                listeners[key] = listeners[key] || [];
                listeners[key].push(callback);
                return function () {
                    var callbacks = listeners[key] || [];
                    var index = callbacks.indexOf(callback);
                    if (index !== -1) {
                        callbacks.splice(index, 1);
                    }
                    if (callbacks.length === 0) {
                        delete listeners[key];
                    }
                };
            }
        });
    };
}
