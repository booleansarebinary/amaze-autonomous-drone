function DictionaryPlugin() {
    var measurements = [
        { name: 'Position X', key: 'drone.position.x' },
        { name: 'Position Y', key: 'drone.position.y' }
    ];

    return function install(openmct) {
        var namespace = 'drone.telemetry';
        var root = { namespace: namespace, key: 'drone' };

        openmct.objects.addRoot(root);
        openmct.objects.addProvider(namespace, {
            get: function (identifier) {
                if (identifier.key === 'drone') {
                    return Promise.resolve({
                        identifier: identifier,
                        name: 'Crazyflie',
                        type: 'folder',
                        location: 'ROOT'
                    });
                }
                var measurement = measurements.find(function (item) {
                    return item.key === identifier.key;
                });
                return Promise.resolve({
                    identifier: identifier,
                    name: measurement.name,
                    type: 'drone.telemetry',
                    telemetry: {
                        values: [
                            { key: 'value', name: 'Position', units: 'm', format: 'float', hints: { range: 1 } },
                            { key: 'utc', source: 'timestamp', name: 'Timestamp', format: 'utc', hints: { domain: 1 } }
                        ]
                    },
                    location: namespace + ':drone'
                });
            }
        });
        openmct.composition.addProvider({
            appliesTo: function (domainObject) {
                return domainObject.identifier.namespace === namespace && domainObject.identifier.key === 'drone';
            },
            load: function () {
                return Promise.resolve(measurements.map(function (measurement) {
                    return { namespace: namespace, key: measurement.key };
                }));
            }
        });
        openmct.types.addType('drone.telemetry', {
            name: 'Drone Telemetry',
            cssClass: 'icon-telemetry'
        });
    };
}
