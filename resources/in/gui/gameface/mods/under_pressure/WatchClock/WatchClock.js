(function () {
    'use strict';
    var DEFAULT_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    var root = document.getElementById('watch-root');
    var timeEl = document.getElementById('watch-time');
    var dateEl = document.getElementById('watch-date');
    var cfg = {};
    var lastPayload = null;
    var lastReportedSize = null;
    var measureFrame = null;
    var resizeRetryTimer = null;

    function pad(n) {
        return n < 10 ? '0' + n : '' + n;
    }

    function cmd(name, value) {
        try {
            if (window.model && typeof window.model.onCmd === 'function') {
                window.model.onCmd({ name: String(name), value: String(value) });
            }
        } catch (e) {}
    }

    function uiScale() {
        try {
            if (window.viewEnv && viewEnv.remToPx) {
                var px = viewEnv.remToPx(1);
                if (px > 0) {
                    return px;
                }
            }
        } catch (e) {}
        var payloadScale = parseFloat(cfg.scale);
        if (payloadScale > 0) {
            return payloadScale;
        }
        var w = document.documentElement.clientWidth || window.innerWidth || 1920;
        var h = document.documentElement.clientHeight || window.innerHeight || 1080;
        return Math.min(w / 1920, h / 1080) || 1;
    }

    function applyScale() {
        var fontSize = uiScale() + 'px';
        if (document.documentElement.style.fontSize !== fontSize) {
            document.documentElement.style.fontSize = fontSize;
        }
    }

    function readConfig() {
        var raw = window.model && window.model.payload ? String(window.model.payload) : '';
        if (raw === lastPayload) {
            return;
        }
        lastPayload = raw;
        try {
            cfg = JSON.parse(raw || '{}');
        } catch (e) {
            cfg = {};
        }
        applyConfig();
    }

    function applyConfig() {
        var mode = cfg.mode === 'battle' ? 'battle' : 'garage';
        root.className = 'watch-' + mode;
        dateEl.style.display = mode === 'garage' ? 'block' : 'none';
        timeEl.style.color = '#' + (cfg.color || 'FFFFFF');
    }

    function reportSize() {
        var w = 0;
        var h = 0;
        try {
            var rect = root.getBoundingClientRect();
            w = rect.width;
            h = rect.height;
        } catch (e) {}
        if (w < 2 || h < 2) {
            w = root.offsetWidth || 0;
            h = root.offsetHeight || 0;
        }
        if (w < 2 || h < 2) {
            return;
        }
        w = Math.max(1, Math.ceil(w));
        h = Math.max(1, Math.ceil(h));
        var key = w + 'x' + h;
        if (key === lastReportedSize) {
            return;
        }
        var applied = false;
        try {
            if (window.viewEnv && viewEnv.resizeViewPx) {
                viewEnv.resizeViewPx(w, h);
                applied = true;
            }
        } catch (e) {}
        if (!applied) {
            if (resizeRetryTimer === null) {
                resizeRetryTimer = window.setTimeout(function () {
                    resizeRetryTimer = null;
                    reportSize();
                }, 250);
            }
            return;
        }
        lastReportedSize = key;
        cmd('onSize', key);
    }

    function scheduleMeasure() {
        if (measureFrame !== null) {
            return;
        }
        measureFrame = requestAnimationFrame(function () {
            measureFrame = null;
            reportSize();
        });
    }

    function render() {
        var hidden = cfg.visible === false;
        if (root.classList) {
            root.classList.toggle('watch-hidden', hidden);
        } else {
            root.style.visibility = hidden ? 'hidden' : 'visible';
        }
        var now = new Date();
        var h = now.getHours();
        var suffix = '';
        if (cfg.format === '12') {
            suffix = h >= 12 ? ' PM' : ' AM';
            h = h % 12;
            if (h === 0) {
                h = 12;
            }
        }
        var hh = cfg.format === '12' ? String(h) : pad(h);
        var showSec = cfg.showSeconds !== false;
        timeEl.textContent = hh + ':' + pad(now.getMinutes()) + (showSec ? ':' + pad(now.getSeconds()) : '') + suffix;
        if (cfg.mode === 'garage') {
            var days = cfg.days && cfg.days.length === 7 ? cfg.days : DEFAULT_DAYS;
            var dayName = days[(now.getDay() + 6) % 7] || '';
            dateEl.textContent = dayName + ', ' + pad(now.getDate()) + '.' + pad(now.getMonth() + 1) + '.' + now.getFullYear();
        } else {
            dateEl.textContent = '';
        }
    }

    function tick() {
        readConfig();
        applyScale();
        render();
        scheduleMeasure();
    }

    function initialize() {
        tick();
        if (window.engine) {
            window.engine.on('viewEnv.onDataChanged', tick);
            window.engine.on('self.onScaleUpdated', tick);
            window.engine.on('clientResized', tick);
        }
        window.setInterval(tick, 1000);
        if (window.model && typeof window.model.onReady === 'function') {
            window.model.onReady({});
        }
    }

    function afterFrames() {
        requestAnimationFrame(function () {
            requestAnimationFrame(initialize);
        });
    }

    if (window.engine && window.engine.whenReady) {
        var domReady = window.isDomBuilt ? Promise.resolve() : new Promise(function (resolve) {
            window.engine.on('self.onDomBuilt', resolve);
        });
        Promise.all([window.engine.whenReady, domReady]).then(afterFrames);
    } else {
        afterFrames();
    }
}());
