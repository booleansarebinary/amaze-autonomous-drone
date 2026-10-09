const listeners = {};   // key -> [callbacks]
const ws = new WebSocket('ws://localhost:8765');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  (listeners[msg.key] || []).forEach((cb) =>
    cb({ timestamp: msg.timestamp, value: msg.value }));
};

function DronePlugin() {
  const NAMESPACE = 'drone';
  const SIGNALS = ['battery', 'roll', 'pitch'];   // rename to your log variables

  // Fake data: replace this later
  function fakeValue(key, t) {
    if (key === 'battery') return 4.0 - (t % 600000) / 600000 * 0.5;
    return Math.sin(t / 1000) * (key === 'roll' ? 10 : 5);
  }
  let ws;
  
    function connect() {
    ws = new WebSocket('ws://localhost:8765');
    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        (listeners[msg.key] || []).forEach((cb) =>
        cb({ timestamp: msg.timestamp, value: msg.value }));
    };
    ws.onclose = () => setTimeout(connect, 1000);
    }
    connect();
  

  return function install(openmct) {
    // Root folder
    openmct.objects.addRoot({ namespace: NAMESPACE, key: 'crazyflie' });

    // Define the objects
    openmct.objects.addProvider(NAMESPACE, {
      get(identifier) {
        if (identifier.key === 'crazyflie') {
          return Promise.resolve({ identifier, name: 'Crazyflie', type: 'folder', location: 'ROOT' });
        }
        return Promise.resolve({
          identifier,
          name: identifier.key,
          type: 'drone.telemetry',
          location: NAMESPACE + ':crazyflie',
          telemetry: {
            values: [
              { key: 'value', name: 'Value', format: 'float', hints: { range: 1 } },
              { key: 'utc', source: 'timestamp', name: 'Time', format: 'utc', hints: { domain: 1 } }
            ]
          }
        });
      }
    });

    // Put the signals inside the folder
    openmct.composition.addProvider({
      appliesTo: (o) => o.identifier.namespace === NAMESPACE && o.type === 'folder',
      load: () => Promise.resolve(SIGNALS.map((key) => ({ namespace: NAMESPACE, key })))
    });

    openmct.types.addType('drone.telemetry', {
      name: 'Drone Telemetry',
      description: 'Value logged from the Crazyflie',
      cssClass: 'icon-telemetry'
    });

    // Historical data (fills the graph's past)
    openmct.telemetry.addProvider({
    supportsRequest: (o) => o.type === 'drone.telemetry',
    request() {
        return Promise.resolve([]);   // no history yet, only live data
    },

    supportsSubscribe: (o) => o.type === 'drone.telemetry',
    subscribe(o, callback) {
        const key = o.identifier.key;
        (listeners[key] = listeners[key] || []).push(callback);
        return () => {
        listeners[key] = listeners[key].filter((cb) => cb !== callback);
        };
    }
    });
  };
}