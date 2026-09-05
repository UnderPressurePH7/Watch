(function () {
    'use strict';
    var DEFAULT_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    var VIEW_PAD = 8;
    var DIGITS = /[0-9]/g;
    var METRIC_SAMPLES = 10;
    var CLOCK_PERIOD_SEC = 1000;
    var CLOCK_PERIOD_MIN = 60000;
    var CLOCK_GUARD = 20;

    var root = document.getElementById('watch-root');
    var content = document.getElementById('watch-content');
    var timeEl = document.getElementById('watch-time');
    var dateEl = document.getElementById('watch-date');

    var cfg = {};
    var mode = root && String(root.className).indexOf('battle') !== -1 ? 'battle' : 'garage';
    var hidden = false;

    var lastPayload = null;
    var lastShift = null;
    var lastClass = null;
    var lastColor = null;
    var lastFontSize = null;
    var lastDateDisplay = null;
    var lastReportedSize = null;
    var lastTimeText = null;
    var lastDateText = null;
    var lastTimeShape = null;
    var lastDateShape = null;

    var metricsKey = null;
    var metricsSize = null;
    var metricsSamples = 0;
    var metricsUniform = false;

    var measureFrame = null;
    var resizeRetryTimer = null;
    var clockTimer = null;
    var started = false;
    var engineBound = false;

    function pad(n) {
        return n < 10 ? '0' + n : '' + n;
    }

    function shapeOf(text) {
        return String(text).replace(DIGITS, '0');
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

    function applyRootClass() {
        var cls = 'watch-' + mode + (hidden ? ' watch-hidden' : '');
        if (cls === lastClass) {
            return;
        }
        lastClass = cls;
        root.className = cls;
    }

    function applyMode() {
        var next = (cfg.mode === 'battle' || cfg.mode === 'garage') ? cfg.mode : mode;
        var changed = next !== mode;
        mode = next;
        applyRootClass();
        var display = mode === 'garage' ? 'block' : 'none';
        if (display !== lastDateDisplay) {
            lastDateDisplay = display;
            dateEl.style.display = display;
            changed = true;
        }
        return changed;
    }

    function applyColor() {
        var color = '#' + (cfg.color || 'FFFFFF');
        if (color === lastColor) {
            return false;
        }
        lastColor = color;
        timeEl.style.color = color;
        return true;
    }

    function applyVisibility() {
        var next = cfg.visible === false;
        if (next === hidden) {
            return false;
        }
        hidden = next;
        applyRootClass();
        return true;
    }

    function applyScale() {
        var fontSize = uiScale() + 'px';
        if (fontSize === lastFontSize) {
            return false;
        }
        lastFontSize = fontSize;
        document.documentElement.style.fontSize = fontSize;
        return true;
    }

    function metricsSignature() {
        return lastFontSize + '|' + mode + '|' + lastTimeShape + '|' + lastDateShape;
    }

    function reportSize() {
        var w = 0;
        var h = 0;
        try {
            var rect = content.getBoundingClientRect();
            w = rect.width;
            h = rect.height;
        } catch (e) {}
        if (w < 2 || h < 2) {
            w = content.offsetWidth || 0;
            h = content.offsetHeight || 0;
        }
        if (w < 2 || h < 2) {
            return;
        }
        w = Math.max(1, Math.ceil(w));
        h = Math.max(1, Math.ceil(h));
        var key = w + 'x' + h + '@' + VIEW_PAD;

        var signature = metricsSignature();
        if (signature !== metricsKey) {
            metricsKey = signature;
            metricsSize = key;
            metricsSamples = 0;
            metricsUniform = false;
        } else if (!metricsUniform) {
            if (key === metricsSize) {
                metricsSamples += 1;
                if (metricsSamples >= METRIC_SAMPLES) {
                    metricsUniform = true;
                }
            } else {
                metricsSize = key;
                metricsSamples = 0;
            }
        }

        if (key === lastReportedSize) {
            return;
        }
        root.style.width = w + 'px';
        root.style.height = h + 'px';
        root.style.margin = VIEW_PAD + 'px';
        var applied = false;
        try {
            if (window.viewEnv && viewEnv.resizeViewPx) {
                viewEnv.resizeViewPx(w + VIEW_PAD * 2, h + VIEW_PAD * 2);
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

    function cancelMeasure() {
        if (measureFrame === null) {
            return;
        }
        try {
            cancelAnimationFrame(measureFrame);
        } catch (e) {}
        measureFrame = null;
    }

    function applyShift() {
        var raw = '0,0';
        try {
            if (window.model && window.model.shift) {
                raw = String(window.model.shift);
            }
        } catch (e) {}
        if (raw === lastShift) {
            return false;
        }
        lastShift = raw;
        var parts = raw.split(',');
        var dx = parseInt(parts[0], 10) || 0;
        var dy = parseInt(parts[1], 10) || 0;
        if (dx > VIEW_PAD) {
            dx = VIEW_PAD;
        } else if (dx < -VIEW_PAD) {
            dx = -VIEW_PAD;
        }
        if (dy > VIEW_PAD) {
            dy = VIEW_PAD;
        } else if (dy < -VIEW_PAD) {
            dy = -VIEW_PAD;
        }
        root.style.transform = (dx || dy) ? ('translate(' + dx + 'px, ' + dy + 'px)') : '';
        return true;
    }

    function renderClock() {
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
        var timeText = hh + ':' + pad(now.getMinutes()) + (showSec ? ':' + pad(now.getSeconds()) : '') + suffix;
        var dateText = '';
        if (mode === 'garage') {
            var days = cfg.days && cfg.days.length === 7 ? cfg.days : DEFAULT_DAYS;
            var dayName = days[(now.getDay() + 6) % 7] || '';
            dateText = dayName + ', ' + pad(now.getDate()) + '.' + pad(now.getMonth() + 1) + '.' + now.getFullYear();
        }
        var measure = false;
        if (timeText !== lastTimeText) {
            lastTimeText = timeText;
            timeEl.textContent = timeText;
            var timeShape = shapeOf(timeText);
            if (timeShape !== lastTimeShape) {
                lastTimeShape = timeShape;
                measure = true;
            } else if (!metricsUniform) {
                measure = true;
            }
        }
        if (dateText !== lastDateText) {
            lastDateText = dateText;
            dateEl.textContent = dateText;
            var dateShape = shapeOf(dateText);
            if (dateShape !== lastDateShape) {
                lastDateShape = dateShape;
                measure = true;
            } else if (!metricsUniform) {
                measure = true;
            }
        }
        return measure;
    }

    function stopClock() {
        if (clockTimer === null) {
            return;
        }
        window.clearTimeout(clockTimer);
        clockTimer = null;
    }

    function scheduleClock() {
        stopClock();
        if (!started || hidden) {
            return;
        }
        var period = cfg.showSeconds === false ? CLOCK_PERIOD_MIN : CLOCK_PERIOD_SEC;
        var now = Date.now ? Date.now() : new Date().getTime();
        var delay = period - (now % period);
        if (delay < CLOCK_GUARD) {
            delay += period;
        }
        clockTimer = window.setTimeout(onClockTimer, delay);
    }

    function onClockTimer() {
        clockTimer = null;
        if (renderClock()) {
            scheduleMeasure();
        }
        scheduleClock();
    }

    function daysEqual(a, b) {
        var aList = a && a.length === 7 ? a : DEFAULT_DAYS;
        var bList = b && b.length === 7 ? b : DEFAULT_DAYS;
        for (var i = 0; i < 7; i += 1) {
            if (String(aList[i]) !== String(bList[i])) {
                return false;
            }
        }
        return true;
    }

    function readPayload() {
        var raw = '';
        try {
            if (window.model && window.model.payload) {
                raw = String(window.model.payload);
            }
        } catch (e) {}
        if (raw === lastPayload) {
            return false;
        }
        lastPayload = raw;
        var next = {};
        try {
            next = JSON.parse(raw || '{}') || {};
        } catch (e) {
            next = {};
        }
        var prev = cfg;
        cfg = next;

        var modeChanged = applyMode();
        applyColor();
        var scaleChanged = applyScale();
        var shownAgain = applyVisibility() && !hidden;
        var clockChanged = modeChanged
            || String(prev.format) !== String(next.format)
            || (prev.showSeconds !== false) !== (next.showSeconds !== false)
            || (mode === 'garage' && !daysEqual(prev.days, next.days));

        if (hidden) {
            stopClock();
            cancelMeasure();
            return true;
        }
        var measure = modeChanged || scaleChanged || shownAgain;
        if (clockChanged || shownAgain) {
            if (renderClock()) {
                measure = true;
            }
            scheduleClock();
        }
        if (measure) {
            scheduleMeasure();
        }
        return true;
    }

    function onModelChanged() {
        readPayload();
        applyShift();
    }

    function onGeometryEvent() {
        applyScale();
        if (hidden) {
            return;
        }
        scheduleMeasure();
    }

    function bindEngine() {
        if (engineBound || !window.engine) {
            return;
        }
        engineBound = true;
        window.engine.on('viewEnv.onDataChanged', onModelChanged);
        window.engine.on('self.onScaleUpdated', onGeometryEvent);
        window.engine.on('clientResized', onGeometryEvent);
    }

    function unbindEngine() {
        if (!engineBound || !window.engine) {
            return;
        }
        engineBound = false;
        try {
            window.engine.off('viewEnv.onDataChanged', onModelChanged);
            window.engine.off('self.onScaleUpdated', onGeometryEvent);
            window.engine.off('clientResized', onGeometryEvent);
        } catch (e) {}
    }

    function applyAll() {
        readPayload();
        applyScale();
        if (renderClock()) {
            scheduleMeasure();
        }
        applyShift();
    }

    function teardown() {
        started = false;
        stopClock();
        cancelMeasure();
        if (resizeRetryTimer !== null) {
            window.clearTimeout(resizeRetryTimer);
            resizeRetryTimer = null;
        }
        unbindEngine();
    }

    function initialize() {
        if (started) {
            return;
        }
        started = true;
        bindEngine();
        applyAll();
        scheduleMeasure();
        scheduleClock();
        try {
            if (window.addEventListener) {
                window.addEventListener('unload', teardown);
            }
        } catch (e) {}
        if (window.model && typeof window.model.onReady === 'function') {
            window.model.onReady({});
        }
    }

    function afterFrames() {
        requestAnimationFrame(function () {
            requestAnimationFrame(initialize);
        });
    }

    applyMode();
    applyColor();
    applyVisibility();
    applyScale();
    renderClock();
    applyShift();
    reportSize();

    if (window.engine && window.engine.whenReady) {
        var domReady = window.isDomBuilt ? Promise.resolve() : new Promise(function (resolve) {
            window.engine.on('self.onDomBuilt', resolve);
            window.setTimeout(resolve, 1000);
        });
        Promise.all([window.engine.whenReady, domReady]).then(afterFrames);
    } else {
        afterFrames();
    }
}());
