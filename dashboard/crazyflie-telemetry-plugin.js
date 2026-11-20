
function CrazyflieTelemetryPlugin() {
    return function install(openmct) {
        const socket = new WebSocket("ws://localhost:8765");
        const listeners = new Map();

        const telemetryFields = {
            roll: {
                name: "Roll",
                key: "drone.attitude.roll",
                unit: "deg"
            },
            pitch: {
                name: "Pitch",
                key: "drone.attitude.pitch",
                unit: "deg"
            },
            yaw: {
                name: "Yaw",
                key: "drone.attitude.yaw",
                unit: "deg"
            }
        };

        // Connect to the Python WebSocket server.
        socket.onopen = () => {
            console.log("Connected to Crazyflie telemetry WebSocket.");
        };

        socket.onerror = (error) => {
            console.error("Crazyflie WebSocket error:", error);
        };

        socket.onclose = () => {
            console.warn("Crazyflie telemetry WebSocket closed.");
        };

        // Receive and distribute telemetry readings.
        socket.onmessage = (event) => {
            let message;

            try {
                message = JSON.parse(event.data);
            } catch (error) {
                console.error("Invalid telemetry JSON:", error);
                return;
            }

            const values = message.values;

            if (!values || typeof values !== "object") {
                return;
            }

            const timestamp = Number(message.utc);

            if (!Number.isFinite(timestamp)) {
                return;
            }

            Object.values(telemetryFields).forEach((field) => {
                const value = Number(values[field.key]);

                if (!Number.isFinite(value)) {
                    return;
                }

                const datum = {
                    utc: timestamp,
                    value: value
                };

                const callbacks = listeners.get(field.key);

                if (callbacks) {
                    callbacks.forEach((callback) => {
                        callback(datum);
                    });
                }
            });
        };

        // Register the Crazyflie Attitude folder.
        openmct.objects.addRoot({
            namespace: "crazyflie",
            key: "attitude",
            name: "Crazyflie Attitude",
            type: "folder"
        });

        // Define the folder and its Roll, Pitch, and Yaw children.
        openmct.objects.addProvider({
            appliesTo(identifier) {
                return identifier.namespace === "crazyflie";
            },

            get(identifier) {
                if (identifier.namespace !== "crazyflie") {
                    return undefined;
                }

                if (identifier.key === "attitude") {
                    return {
                        identifier: identifier,
                        name: "Crazyflie Attitude",
                        type: "folder",
                        location: "ROOT",
                        composition: Object.values(telemetryFields).map(
                            (field) => ({
                                namespace: "crazyflie",
                                key: field.key
                            })
                        )
                    };
                }

                const field = Object.values(telemetryFields).find(
                    (item) => item.key === identifier.key
                );

                if (!field) {
                    return undefined;
                }

                return {
                    identifier: identifier,
                    name: field.name,
                    type: "telemetry",
                    telemetry: {
                        values: [
                            {
                                key: "utc",
                                name: "Timestamp",
                                format: "utc",
                                hints: {
                                    domain: 1
                                }
                            },
                            {
                                key: "value",
                                name: field.name,
                                units: field.unit,
                                format: "float",
                                hints: {
                                    range: 1
                                }
                            }
                        ]
                    }
                };
            }
        });


        // Provide live telemetry updates to Open MCT.
        openmct.telemetry.addProvider({
            supportsSubscribe(domainObject) {
                return (
                    domainObject.identifier.namespace === "crazyflie" &&
                    Object.values(telemetryFields).some(
                        (field) =>
                            field.key === domainObject.identifier.key
                    )
                );
            },

            subscribe(domainObject, callback) {
                const key = domainObject.identifier.key;

                if (!listeners.has(key)) {
                    listeners.set(key, new Set());
                }

                const callbacks = listeners.get(key);
                callbacks.add(callback);

                // Remove the callback when Open MCT unsubscribes.
                return function unsubscribe() {
                    callbacks.delete(callback);

                    if (callbacks.size === 0) {
                        listeners.delete(key);
                    }
                };
            }
        });

        console.log("Crazyflie telemetry plugin installed.");
    };
}
