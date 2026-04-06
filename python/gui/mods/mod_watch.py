import json
import logging
import os
import time
import weakref

import BigWorld
import Event
import Settings
from PlayerEvents import g_playerEvents
from gui.Scaleform.framework import g_entitiesFactories, ScopeTemplates, ViewSettings
from gui.Scaleform.framework.entities.BaseDAAPIComponent import BaseDAAPIComponent
from gui.Scaleform.framework.entities.View import View
from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
from gui.shared.personality import ServicesLocator
from gui.shared import g_eventBus, EVENT_BUS_SCOPE
from gui.shared.events import GameEvent
from gui.Scaleform.lobby_entry import getLobbyStateMachine
from frameworks.wulf import WindowLayer

try:
    from helpers import getClientLanguage
    _CLIENT_LANG = getClientLanguage()
except Exception:
    _CLIENT_LANG = 'en'

logger = logging.getLogger('Watch')
logger.setLevel(logging.DEBUG if os.path.isfile('.debug_mods') else logging.ERROR)

__version__ = '0.0.1'
__author__ = 'Under_Pressure'

WATCH_CONFIG_DIR = os.path.join('mods', 'configs', 'watch')
_CONFIG_PATH = os.path.join(WATCH_CONFIG_DIR, 'watch.json')

_PREFS_SECTION = 'watchOverlay'
_PREF_GARAGE_X = 'garageX'
_PREF_GARAGE_Y = 'garageY'
_PREF_BATTLE_X = 'battleOffX'
_PREF_BATTLE_Y = 'battleOffY'

_BATTLE_INJECTOR_LINKAGE = 'WatchBattleInjector'
_BATTLE_COMPONENT_LINKAGE = 'WatchBattleClockMain'
_BATTLE_SWF = 'WatchBattle.swf'

_GARAGE_INJECTOR_LINKAGE = 'WatchGarageInjector'
_GARAGE_SWF = 'WatchGarage.swf'

MOD_LINKAGE = 'me.under_pressure.watch'

_L10N_DIR = 'mods/under_pressure.watch'
_L10N_FALLBACK = 'en'
_l10n = {}

_DAYS_DEFAULT = [u'Monday', u'Tuesday', u'Wednesday', u'Thursday', u'Friday', u'Saturday', u'Sunday']


def _byteify(data):
    try:
        _unicode = unicode
    except NameError:
        _unicode = str
    if isinstance(data, dict):
        try:
            items = data.iteritems()
        except AttributeError:
            items = data.items()
        return {_byteify(key): _byteify(value) for key, value in items}
    elif isinstance(data, (list, tuple)):
        return [_byteify(element) for element in data]
    elif isinstance(data, _unicode):
        return data.encode('utf-8')
    return data


def _cancelCallbackSafe(cbid):
    try:
        if cbid is not None:
            BigWorld.cancelCallback(cbid)
    except (AttributeError, ValueError):
        pass


def _weakCallback(obj, methodName):
    ref = weakref.ref(obj)
    def _cb(*args, **kwargs):
        inst = ref()
        if inst is not None:
            getattr(inst, methodName)(*args, **kwargs)
    return _cb


def _getLocalizedDayName(weekday):
    days = _l10n.get('days', _DAYS_DEFAULT)
    if not isinstance(days, list) or len(days) != 7:
        days = _DAYS_DEFAULT
    if 0 <= weekday < 7:
        return days[weekday]
    return u''


def _loadLocalization():
    global _l10n
    import ResMgr
    for tryLang in (_CLIENT_LANG, _L10N_FALLBACK):
        path = _L10N_DIR + '/' + tryLang + '.json'
        try:
            section = ResMgr.openSection(path)
            if section is not None:
                raw = section.asBinary
                _l10n = json.loads(raw)
                return
        except Exception:
            pass


def _tr(key, default=u''):
    return _l10n.get(key, default)


def _getPrefsSection(create=False):
    settings = Settings.g_instance
    if settings is None:
        return None
    prefs = getattr(settings, 'userPrefs', None)
    if prefs is None:
        return None
    try:
        if not prefs.has_key(_PREFS_SECTION):
            if not create:
                return None
            prefs.createSection(_PREFS_SECTION)
        return prefs[_PREFS_SECTION]
    except Exception:
        return None


def _readPrefInt(key, default):
    section = _getPrefsSection(False)
    if section is None:
        return default
    try:
        return int(section.readInt(key, default))
    except Exception:
        return default


def _writePrefInt(key, value):
    section = _getPrefsSection(True)
    if section is None:
        return
    try:
        section.writeInt(key, int(value))
        if Settings.g_instance is not None:
            Settings.g_instance.save()
    except Exception:
        pass


def _toBool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def _clamp(minVal, val, maxVal):
    return max(minVal, min(val, maxVal))


def _toColorList(value):
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return [_clamp(0, int(c), 255) for c in value]
    return [255, 255, 255]


def _createTooltip(header=None, body=None):
    s = ''
    if header is not None:
        s += '{HEADER}%s{/HEADER}' % header
    if body is not None:
        s += '{BODY}%s{/BODY}' % body
    return s


class _CheckboxParam(object):
    def __init__(self, tokenName, defaultValue=True):
        self.tokenName = tokenName
        self.value = defaultValue
        self.defaultValue = defaultValue

    @property
    def msaValue(self):
        return self.value

    @msaValue.setter
    def msaValue(self, v):
        self.value = bool(v)

    def renderParam(self, header, body=None):
        return {
            "type": "CheckBox",
            "text": header,
            "varName": self.tokenName,
            "value": self.value,
            "tooltip": _createTooltip(header, body)
        }


class _ColorParam(object):
    def __init__(self, tokenName, defaultValue=None):
        self.tokenName = tokenName
        self.value = list(defaultValue) if defaultValue else [255, 255, 255]
        self.defaultValue = list(self.value)

    @property
    def msaValue(self):
        c = self.value
        return "%02X%02X%02X" % (int(c[0]), int(c[1]), int(c[2]))

    @msaValue.setter
    def msaValue(self, v):
        if isinstance(v, (list, tuple)):
            self.value = _toColorList(v)
        else:
            h = str(v).lstrip('#')
            self.value = [int(h[i:i+2], 16) for i in (0, 2, 4)]

    def getPackedColor(self):
        c = self.value
        return (int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])

    def renderParam(self, header, body=None):
        return {
            "type": "ColorChoice",
            "text": header,
            "varName": self.tokenName,
            "value": self.msaValue,
            "tooltip": _createTooltip(header, body)
        }


class _ConfigParams(object):
    def __init__(self):
        self.enabled = _CheckboxParam('enabled', True)
        self.battleEnabled = _CheckboxParam('battle-enabled', True)
        self.garageEnabled = _CheckboxParam('garage-enabled', True)
        self.timeColor = _ColorParam('time-color', [255, 255, 255])

    def items(self):
        return {
            self.enabled.tokenName: self.enabled,
            self.battleEnabled.tokenName: self.battleEnabled,
            self.garageEnabled.tokenName: self.garageEnabled,
            self.timeColor.tokenName: self.timeColor,
        }


g_configParams = _ConfigParams()


class _Config(object):
    def __init__(self):
        self.onConfigChanged = Event.Event()
        self._finalized = False
        self._loadConfig()
        self._registerMod()

    def fini(self):
        self._finalized = True
        self.onConfigChanged.clear()

    def _loadConfig(self):
        try:
            if not os.path.exists(WATCH_CONFIG_DIR):
                os.makedirs(WATCH_CONFIG_DIR)
            if not os.path.isfile(_CONFIG_PATH):
                self._saveConfig()
                return
            with open(_CONFIG_PATH, 'r') as f:
                data = _byteify(json.loads(f.read().strip()))
            params = g_configParams.items()
            for token, param in params.items():
                if token in data:
                    if isinstance(param, _CheckboxParam):
                        param.value = _toBool(data[token])
                    elif isinstance(param, _ColorParam):
                        param.value = _toColorList(data[token])
        except Exception as e:
            logger.error('[Config] Load failed: %s', e)

    def _saveConfig(self):
        try:
            if not os.path.exists(WATCH_CONFIG_DIR):
                os.makedirs(WATCH_CONFIG_DIR)
            data = {}
            for token, param in g_configParams.items().items():
                data[token] = param.value
            with open(_CONFIG_PATH, 'w') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error('[Config] Save failed: %s', e)

    def _registerMod(self):
        try:
            from gui.modsSettingsApi import g_modsSettingsApi
        except ImportError:
            return

        try:
            template = {
                'modDisplayName': _tr('modname', u'Watch Clock'),
                'enabled': True,
                'column1': [
                    g_configParams.battleEnabled.renderParam(
                        _tr('battleEnabled.header', u'Show in battle'),
                        _tr('battleEnabled.body', u'Display clock during battle')
                    ),
                    g_configParams.garageEnabled.renderParam(
                        _tr('garageEnabled.header', u'Show in garage'),
                        _tr('garageEnabled.body', u'Display clock in garage')
                    ),
                ],
                'column2': [
                    g_configParams.timeColor.renderParam(
                        _tr('timeColor.header', u'Clock color'),
                        _tr('timeColor.body', u'Sets the clock text color')
                    ),
                ]
            }
            settings = g_modsSettingsApi.setModTemplate(MOD_LINKAGE, template, self._onSettingsChanged)
            if settings:
                self._applyMsa(settings, save=False)
        except Exception as e:
            logger.error('[Config] MSA register failed: %s', e)

    def _applyMsa(self, settings, save=True):
        params = g_configParams.items()
        for name, value in settings.items():
            if name in params:
                params[name].msaValue = value
        if save:
            self._saveConfig()

    def _onSettingsChanged(self, linkage, newSettings):
        if linkage != MOD_LINKAGE or self._finalized:
            return
        self._applyMsa(newSettings)
        try:
            self.onConfigChanged()
        except Exception:
            pass


_loadLocalization()
g_config = _Config()


class _BattleInjectorView(View):
    _g_ctrl = None

    def _populate(self):
        super(_BattleInjectorView, self)._populate()
        if _BattleInjectorView._g_ctrl:
            _BattleInjectorView._g_ctrl._onBattleInjectorReady(self)

    def _dispose(self):
        if _BattleInjectorView._g_ctrl:
            _BattleInjectorView._g_ctrl._onBattleInjectorDisposed()
        super(_BattleInjectorView, self)._dispose()

    def py_onDragEnd(self, offset):
        if _BattleInjectorView._g_ctrl:
            _BattleInjectorView._g_ctrl._onBattleDragEnd(offset)


class _BattleClockView(BaseDAAPIComponent):
    _g_ctrl = None

    def _populate(self):
        super(_BattleClockView, self)._populate()
        if _BattleClockView._g_ctrl:
            _BattleClockView._g_ctrl._onBattleFlashReady(self)

    def _dispose(self):
        if _BattleClockView._g_ctrl:
            _BattleClockView._g_ctrl._onBattleFlashDisposed()
        super(_BattleClockView, self)._dispose()

    def as_updateTime(self, timeStr):
        if self._isDAAPIInited():
            self.flashObject.as_updateTime(timeStr)

    def as_setVisible(self, isVisible):
        if self._isDAAPIInited():
            self.flashObject.as_setVisible(isVisible)

    def as_setPosition(self, offset):
        if self._isDAAPIInited():
            self.flashObject.as_setPosition(offset)

    def as_setScale(self, factor):
        if self._isDAAPIInited():
            self.flashObject.as_setScale(factor)

    def as_setColor(self, color):
        if self._isDAAPIInited():
            self.flashObject.as_setColor(color)


class _GarageInjectorView(View):
    _g_ctrl = None

    def _populate(self):
        super(_GarageInjectorView, self)._populate()
        if _GarageInjectorView._g_ctrl:
            _GarageInjectorView._g_ctrl._onGarageInjectorReady(self)

    def _dispose(self):
        if _GarageInjectorView._g_ctrl:
            _GarageInjectorView._g_ctrl._onGarageInjectorDisposed()
        super(_GarageInjectorView, self)._dispose()

    def py_onDragEnd(self, offset):
        if _GarageInjectorView._g_ctrl:
            _GarageInjectorView._g_ctrl._onGarageDragEnd(offset)

    def py_onPanelReady(self):
        if _GarageInjectorView._g_ctrl:
            _GarageInjectorView._g_ctrl._onGaragePanelReady()


def _registerFlashComponents():
    g_entitiesFactories.addSettings(ViewSettings(
        _BATTLE_INJECTOR_LINKAGE, _BattleInjectorView, _BATTLE_SWF,
        WindowLayer.WINDOW, None, ScopeTemplates.GLOBAL_SCOPE
    ))
    g_entitiesFactories.addSettings(ViewSettings(
        _BATTLE_COMPONENT_LINKAGE, _BattleClockView, None,
        WindowLayer.UNDEFINED, None, ScopeTemplates.DEFAULT_SCOPE
    ))
    g_entitiesFactories.addSettings(ViewSettings(
        _GARAGE_INJECTOR_LINKAGE, _GarageInjectorView, _GARAGE_SWF,
        WindowLayer.WINDOW, None, ScopeTemplates.GLOBAL_SCOPE
    ))


def _unregisterFlashComponents():
    for linkage in (_BATTLE_INJECTOR_LINKAGE, _BATTLE_COMPONENT_LINKAGE, _GARAGE_INJECTOR_LINKAGE):
        try:
            g_entitiesFactories.removeSettings(linkage)
        except Exception:
            pass


class _BattleClock(object):

    def __init__(self):
        self._injectorView = None
        self._componentView = None
        self._flashReady = False
        self._isActive = False
        self._battleSessionId = 0
        self._tickCallbackId = None
        self._battleOffset = [
            _readPrefInt(_PREF_BATTLE_X, 550),
            _readPrefInt(_PREF_BATTLE_Y, 30),
        ]
        self._hiddenByUI = False
        self._hiddenByStats = False
        self._guiEventsBound = False

    def onAvatarReady(self):
        if not g_configParams.enabled.value or not g_configParams.battleEnabled.value:
            return
        self._battleSessionId += 1
        self._isActive = True
        self._hiddenByUI = False
        self._hiddenByStats = False
        self._battleOffset = [
            _readPrefInt(_PREF_BATTLE_X, 550),
            _readPrefInt(_PREF_BATTLE_Y, 30),
        ]
        _BattleInjectorView._g_ctrl = self
        _BattleClockView._g_ctrl = self
        self._injectBattleFlash()
        self._bindGUIEvents()

    def onAvatarGone(self):
        self._battleSessionId += 1
        self._isActive = False
        self._unbindGUIEvents()
        self._stopTicker()
        _BattleInjectorView._g_ctrl = None
        _BattleClockView._g_ctrl = None
        self._injectorView = None
        self._componentView = None
        self._flashReady = False

    def fini(self):
        self.onAvatarGone()

    def _injectBattleFlash(self, attempt=0):
        sessionId = self._battleSessionId
        try:
            app = ServicesLocator.appLoader.getDefBattleApp()
            if app:
                app.loadView(SFViewLoadParams(_BATTLE_INJECTOR_LINKAGE))
                return
        except Exception:
            pass
        if attempt < 30 and self._isActive and self._battleSessionId == sessionId:
            BigWorld.callback(0.5, lambda: self._injectBattleFlash(attempt + 1))

    def _onBattleInjectorReady(self, view):
        self._injectorView = view

    def _onBattleInjectorDisposed(self):
        self._injectorView = None

    def _onBattleFlashReady(self, view):
        self._componentView = view
        self._flashReady = True
        self._componentView.as_setPosition(self._battleOffset)
        self._componentView.as_setColor(g_configParams.timeColor.getPackedColor())
        self._componentView.as_setVisible(True)
        self._pushTime()
        self._startTicker()
        g_config.onConfigChanged += self._onConfigChanged

    def _onBattleFlashDisposed(self):
        try:
            g_config.onConfigChanged -= self._onConfigChanged
        except Exception:
            pass
        self._componentView = None
        self._flashReady = False

    def _onConfigChanged(self):
        if self._flashReady and self._componentView:
            self._componentView.as_setColor(g_configParams.timeColor.getPackedColor())

    def _bindGUIEvents(self):
        if self._guiEventsBound:
            return
        self._guiEventsBound = True
        try:
            g_eventBus.addListener(GameEvent.GUI_VISIBILITY, self._onGUIVisibility, scope=EVENT_BUS_SCOPE.BATTLE)
            g_eventBus.addListener(GameEvent.FULL_STATS, self._onToggleStats, scope=EVENT_BUS_SCOPE.BATTLE)
            g_eventBus.addListener(GameEvent.FULL_STATS_QUEST_PROGRESS, self._onToggleStats, scope=EVENT_BUS_SCOPE.BATTLE)
            g_eventBus.addListener(GameEvent.FULL_STATS_PERSONAL_RESERVES, self._onToggleStats, scope=EVENT_BUS_SCOPE.BATTLE)
        except Exception:
            pass

    def _unbindGUIEvents(self):
        if not self._guiEventsBound:
            return
        self._guiEventsBound = False
        try:
            g_eventBus.removeListener(GameEvent.GUI_VISIBILITY, self._onGUIVisibility, scope=EVENT_BUS_SCOPE.BATTLE)
            g_eventBus.removeListener(GameEvent.FULL_STATS, self._onToggleStats, scope=EVENT_BUS_SCOPE.BATTLE)
            g_eventBus.removeListener(GameEvent.FULL_STATS_QUEST_PROGRESS, self._onToggleStats, scope=EVENT_BUS_SCOPE.BATTLE)
            g_eventBus.removeListener(GameEvent.FULL_STATS_PERSONAL_RESERVES, self._onToggleStats, scope=EVENT_BUS_SCOPE.BATTLE)
        except Exception:
            pass

    def _onGUIVisibility(self, event):
        hidden = not event.ctx.get('visible', True)
        if hidden != self._hiddenByUI:
            self._hiddenByUI = hidden
            self._updateVisibility()

    def _onToggleStats(self, event):
        hidden = event.ctx.get('isDown', False)
        if hidden != self._hiddenByStats:
            self._hiddenByStats = hidden
            self._updateVisibility()

    def _updateVisibility(self):
        if not self._flashReady or not self._componentView:
            return
        self._componentView.as_setVisible(not self._hiddenByUI and not self._hiddenByStats)

    def _onBattleDragEnd(self, offset):
        try:
            self._battleOffset = [int(offset[0]), int(offset[1])]
            _writePrefInt(_PREF_BATTLE_X, self._battleOffset[0])
            _writePrefInt(_PREF_BATTLE_Y, self._battleOffset[1])
        except Exception:
            pass

    def _startTicker(self):
        self._stopTicker()
        self._onTick()

    def _stopTicker(self):
        _cancelCallbackSafe(self._tickCallbackId)
        self._tickCallbackId = None

    def _onTick(self):
        self._tickCallbackId = None
        if not self._isActive:
            return
        self._pushTime()
        self._tickCallbackId = BigWorld.callback(1.0, _weakCallback(self, '_onTick'))

    def _pushTime(self):
        if not self._flashReady or not self._componentView:
            return
        self._componentView.as_updateTime(time.strftime('%H:%M:%S'))


class _GarageClock(object):

    def __init__(self):
        self._injectorView = None
        self._flashReady = False
        self._enabled = False
        self._hangarVisible = False
        self._tickCallbackId = None
        self._garagePosition = [
            _readPrefInt(_PREF_GARAGE_X, 1350),
            _readPrefInt(_PREF_GARAGE_Y, 55),
        ]

    def enable(self):
        if self._enabled:
            return
        if not g_configParams.enabled.value or not g_configParams.garageEnabled.value:
            return
        self._enabled = True
        self._injectorView = None
        self._flashReady = False
        self._hangarVisible = False
        self._garagePosition = [
            _readPrefInt(_PREF_GARAGE_X, 1350),
            _readPrefInt(_PREF_GARAGE_Y, 55),
        ]
        _GarageInjectorView._g_ctrl = self
        try:
            lsm = getLobbyStateMachine()
            if lsm:
                lsm.onVisibleRouteChanged += self._onVisibleRouteChanged
                try:
                    from gui.impl.lobby.hangar.states import DefaultHangarState
                    self._hangarVisible = lsm.getState() == lsm.getStateByCls(DefaultHangarState)
                except Exception:
                    self._hangarVisible = True
        except Exception:
            self._hangarVisible = True
        if self._hangarVisible:
            self._injectFlash()
        g_config.onConfigChanged += self._onConfigChanged

    def disable(self):
        if not self._enabled:
            return
        self._enabled = False
        self._stopTicker()
        try:
            g_config.onConfigChanged -= self._onConfigChanged
        except Exception:
            pass
        try:
            lsm = getLobbyStateMachine()
            if lsm:
                lsm.onVisibleRouteChanged -= self._onVisibleRouteChanged
        except Exception:
            pass
        _GarageInjectorView._g_ctrl = None
        self._injectorView = None
        self._flashReady = False
        self._hangarVisible = False

    def fini(self):
        self.disable()

    def _onConfigChanged(self):
        if not g_configParams.enabled.value or not g_configParams.garageEnabled.value:
            if self._flashReady and self._injectorView:
                self._injectorView.flashObject.as_setVisible(False)
            return
        if self._flashReady and self._injectorView:
            self._injectorView.flashObject.as_setColor(g_configParams.timeColor.getPackedColor())
            self._injectorView.flashObject.as_setVisible(self._hangarVisible)

    def _onVisibleRouteChanged(self, routeInfo):
        try:
            from gui.impl.lobby.hangar.states import DefaultHangarState
            lsm = getLobbyStateMachine()
            if lsm:
                self._hangarVisible = routeInfo.state == lsm.getStateByCls(DefaultHangarState)
            else:
                self._hangarVisible = False
        except Exception:
            self._hangarVisible = True
        if self._hangarVisible and not self._flashReady and not self._injectorView:
            self._injectFlash()
        self._updatePanelVisibility()

    def _updatePanelVisibility(self):
        if self._flashReady and self._injectorView:
            self._injectorView.flashObject.as_setVisible(self._hangarVisible)

    def _injectFlash(self, attempt=0):
        if not self._enabled:
            return
        try:
            app = ServicesLocator.appLoader.getDefLobbyApp()
            if app and app.initialized:
                app.loadView(SFViewLoadParams(_GARAGE_INJECTOR_LINKAGE))
                return
        except Exception:
            pass
        if attempt < 30:
            BigWorld.callback(0.5, lambda: self._injectFlash(attempt + 1))

    def _onGarageInjectorReady(self, view):
        self._injectorView = view

    def _onGarageInjectorDisposed(self):
        self._injectorView = None
        self._flashReady = False
        self._stopTicker()

    def _onGaragePanelReady(self):
        self._flashReady = True
        if self._injectorView:
            self._injectorView.flashObject.as_setPosition(self._garagePosition)
            self._injectorView.flashObject.as_setColor(g_configParams.timeColor.getPackedColor())
            self._injectorView.flashObject.as_setVisible(self._hangarVisible)
        self._pushTime()
        self._startTicker()

    def _onGarageDragEnd(self, offset):
        try:
            self._garagePosition = [int(offset[0]), int(offset[1])]
            _writePrefInt(_PREF_GARAGE_X, self._garagePosition[0])
            _writePrefInt(_PREF_GARAGE_Y, self._garagePosition[1])
        except Exception:
            pass

    def _startTicker(self):
        self._stopTicker()
        self._onTick()

    def _stopTicker(self):
        _cancelCallbackSafe(self._tickCallbackId)
        self._tickCallbackId = None

    def _onTick(self):
        self._tickCallbackId = None
        if not self._enabled:
            return
        self._pushTime()
        self._tickCallbackId = BigWorld.callback(1.0, _weakCallback(self, '_onTick'))

    def _pushTime(self):
        if not self._flashReady or not self._injectorView:
            return
        now = time.localtime()
        timeStr = time.strftime('%H:%M:%S', now)
        dayName = _getLocalizedDayName(now.tm_wday)
        dateStr = u'%s, %s' % (dayName, time.strftime('%d.%m.%Y', now))
        self._injectorView.flashObject.as_updateTime(timeStr, dateStr)


class _WatchMod(object):

    def __init__(self):
        self._battleClock = _BattleClock()
        self._garageClock = _GarageClock()

    def init(self):
        _registerFlashComponents()
        g_playerEvents.onAccountShowGUI += self._onAccountShowGUI
        g_playerEvents.onAvatarReady += self._onAvatarReady
        g_playerEvents.onAccountBecomeNonPlayer += self._onAccountBecomeNonPlayer
        g_playerEvents.onDisconnected += self._onDisconnected
        logger.debug('[Watch] Initialized v%s', __version__)

    def fini(self):
        g_playerEvents.onAccountShowGUI -= self._onAccountShowGUI
        g_playerEvents.onAvatarReady -= self._onAvatarReady
        g_playerEvents.onAccountBecomeNonPlayer -= self._onAccountBecomeNonPlayer
        g_playerEvents.onDisconnected -= self._onDisconnected
        self._garageClock.disable()
        self._battleClock.onAvatarGone()
        _unregisterFlashComponents()
        g_config.fini()
        logger.debug('[Watch] Finalized')

    def _onAccountShowGUI(self, ctx):
        self._battleClock.onAvatarGone()
        self._garageClock.enable()

    def _onAvatarReady(self):
        self._garageClock.disable()
        self._battleClock.onAvatarReady()

    def _onAccountBecomeNonPlayer(self):
        self._battleClock.onAvatarGone()

    def _onDisconnected(self):
        self._garageClock.disable()
        self._battleClock.onAvatarGone()


_g_mod = _WatchMod()


def init():
    try:
        _g_mod.init()
    except Exception:
        logger.exception('[Watch] Failed to initialize')


def fini():
    try:
        _g_mod.fini()
    except Exception:
        logger.exception('[Watch] Failed to finalize')
