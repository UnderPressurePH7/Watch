(function () {
    'use strict';
    var DEFAULT_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    var root = document.getElementById('watch-root');
    var timeEl = document.getElementById('watch-time');
    var dateEl = document.getElementById('watch-date');
    var cfg = {};
    var lastPayload = null;
    var lastSize = null;

    function pad(n) {
        return n < 10 ? '0' + n : '' + n;
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
        var width = parseInt(cfg.w, 10) || 1;
        var height = parseInt(cfg.h, 10) || 1;
        var size = width + 'x' + height;
        if (size !== lastSize && window.viewEnv && viewEnv.resizeViewPx) {
            lastSize = size;
            viewEnv.resizeViewPx(width, height);
        }
    }

    function render() {
        var hidden = cfg.visible === false;
        root.style.display = hidden ? 'none' : 'block';
        if (hidden) {
            return;
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
        render();
    }

    function initialize() {
        readConfig();
        render();
        if (window.engine) {
            window.engine.on('viewEnv.onDataChanged', tick);
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