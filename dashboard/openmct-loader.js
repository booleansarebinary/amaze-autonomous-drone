/* Load OpenMCT as a browser global even when the host injects module globals. */
window.openmctReady = fetch('../openmct-tutorial/node_modules/openmct/dist/openmct.js')
    .then(function (response) {
        if (!response.ok) {
            throw new Error('Could not load OpenMCT: HTTP ' + response.status);
        }
        return response.text();
    })
    .then(function (source) {
        // The package uses a UMD wrapper. Supplying undefined CommonJS/AMD
        // arguments makes it use the final browser-global export branch.
        var runBundle = new Function('exports', 'module', 'define', source);
        runBundle.call(window, undefined, undefined, undefined);
        if (!window.openmct) {
            throw new Error('The OpenMCT bundle did not create window.openmct.');
        }
        return window.openmct;
    });
