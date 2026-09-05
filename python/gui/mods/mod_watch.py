import json
import logging
import os

import BigWorld
import Event
from PlayerEvents import g_playerEvents
from gui.shared import g_eventBus, EVENT_BUS_SCOPE
from gui.shared.events import GameEvent
from gui.Scaleform.lobby_entry import getLobbyStateMachine

try:
    from helpers import getClientLanguage
    _CLIENT_LANG = getClientLanguage()
except Exception:
    _CLIENT_LANG = 'en'

logger = logging.getLogger('Watch')
logger.setLevel(logging.DEBUG if os.path.isfile('.debug_mods') else logging.ERROR)

__version__ = '0.2.6'
__author__ = 'Under_Pressure'

_GF_OK = True
try:
    import GUI
    import Keys
    from openwg_gameface import ModDynAccessor, manager as gamefaceResMap, on_ready as gamefaceOnReady
    from frameworks.wulf import ViewFlags, ViewModel, ViewSettings, WindowFlags, WindowLayer, WindowStatus
    from gui.impl.pub import ViewImpl, WindowImpl
    from gui.impl.gui_decorators import args2params
    from helpers import dependency
    from skeletons.gui.impl import IGuiLoader
except Exception:
    _GF_OK = False
    logger.error('[Watch] openwg_gameface is required. Get it at https://gitlab.com/openwg/wot.gameface', exc_info=True)

_WINDOW_BUSY_STATUSES = ()
_WINDOW_DEAD_STATUSES = ()
if _GF_OK:
    _WINDOW_BUSY_STATUSES = tuple(status for status in (getattr(WindowStatus, 'CREATED', None),
                                                        getattr(WindowStatus, 'LOADING', None),
                                                        getattr(WindowStatus, 'DESTROYING', None))
                                  if status is not None)
    _WINDOW_DEAD_STATUSES = tuple(status for status in (getattr(WindowStatus, 'DESTROYING', None),
                                                        getattr(WindowStatus, 'DESTROYED', None))
                                  if status is not None)

try:
    from skeletons.gui.shared.utils import IHangarSpace
except Exception:
    IHangarSpace = None

try:
    from gui import g_guiResetters
except Exception:
    g_guiResetters = None

try:
    from gui.shared.personality import ServicesLocator
except Exception:
    ServicesLocator = None

try:
    from gui.Scaleform.daapi.view.battle.shared.page import SharedPage
except Exception:
    SharedPage = None

try:
    from gui.Scaleform.daapi.view.battle.shared.ingame_menu import IngameMenu
except Exception:
    IngameMenu = None

try:
    from gui.impl.lobby.hangar.states import DefaultHangarState, LegacyHangarState
except Exception:
    DefaultHangarState = LegacyHangarState = None

_APP_STATE_OK = True
try:
    from gui.app_loader.settings import APP_NAME_SPACE
    from skeletons.gui.app_loader import ApplicationStateID, IAppLoader
except Exception:
    _APP_STATE_OK = False
    IAppLoader = APP_NAME_SPACE = ApplicationStateID = None

WATCH_CONFIG_DIR = os.path.join('mods', 'configs', 'under_pressure')
_CONFIG_PATH = os.path.join(WATCH_CONFIG_DIR, 'watch.json')
_CONFIG_ENCODING_UTF8 = 'utf-8'
_CONFIG_ENCODING_UTF8_BOM = 'utf-8-bom'
_UTF8_BOM = '\xef\xbb\xbf'


_DEFAULT_BATTLE_OFFSET = [-32, 8]
_DEFAULT_GARAGE_OFFSET = [-32, 60]

_ANCHOR_LEFT = 'left'
_ANCHOR_RIGHT = 'right'
_ANCHOR_TOP = 'top'
_ANCHOR_BOTTOM = 'bottom'
_ANCHOR_X_VALUES = (_ANCHOR_LEFT, _ANCHOR_RIGHT)
_ANCHOR_Y_VALUES = (_ANCHOR_TOP, _ANCHOR_BOTTOM)

_DEFAULT_BATTLE_ANCHOR = [_ANCHOR_RIGHT, _ANCHOR_TOP]
_DEFAULT_GARAGE_ANCHOR = [_ANCHOR_RIGHT, _ANCHOR_TOP]

_ANCHOR_SCHEME_LEGACY = 1
_ANCHOR_SCHEME_SIGNED = 2
_ANCHOR_SCHEME = 3
_OFFSET_LIMIT = 20000

_GRAB_PAD = 4
_DRAG_THRESHOLD = 6
_DRAG_TICK_ACTIVE = 0.0
_DRAG_TICK_HOVER = 0.03
_DRAG_TICK_IDLE = 0.06
_DRAG_TICK_SLEEP = 0.35
_DRAG_IDLE_GRACE = 4
_DRAG_NEAR_PAD = 200

_LOAD_SETTLE_FRAMES = 2
_LOAD_RETRY_LIMIT = 100
_LOAD_RETRY_DELAY = 0.1
_LOAD_SETTLE_HOLD = 0.1

_GARAGE_SETTLE_DELAY = 0.35
_GARAGE_SETTLE_RETRY = 0.35
_GARAGE_SETTLE_MAX_WAITS = 60
_GARAGE_SETTLE_FRAMES = 3
_GARAGE_SETTLE_HOLD = 0.1

_BATTLE_NAME = 'WatchBattle'
_GARAGE_NAME = 'WatchGarage'

_BATTLE_SIZE = (112, 30)
_GARAGE_SIZE = (170, 50)

_GARAGE_BOTTOM_MARGIN = 100
_GARAGE_EDGE_SNAP = 10

_BASE_SCREEN = (1920, 1080)

MOD_LINKAGE = 'me.under_pressure.watch'

_L10N_DIR = 'mods/under_pressure.watch'
_L10N_FALLBACK = 'en'
_l10n = {}

_DAYS_DEFAULT = [u'Monday', u'Tuesday', u'Wednesday', u'Thursday', u'Friday', u'Saturday', u'Sunday']

_HANGAR_STATE_CLASS_PATHS = (
    'gui.impl.lobby.hangar.states.DefaultHangarState',
    'gui.impl.lobby.hangar.states.LegacyHangarState',
    'gui.impl.lobby.hangar.states.HangarState',
    'comp7.gui.impl.lobby.hangar.states.Comp7HangarState',
    'comp7.gui.impl.lobby.hangar.states.Comp7RootHangarState',
    'comp7_light.gui.impl.lobby.hangar.states.Comp7LightHangarState',
    'comp7_light.gui.impl.lobby.hangar.states.Comp7LightRootHangarState',
    'fun_random.gui.impl.lobby.hangar.states.FunRandomHangarState',
    'fun_random.gui.impl.lobby.hangar.states.DefaultFunRandomHangarState',
    'battle_royale.gui.impl.lobby.views.states.BattleRoyaleHangarState',
)


_hangarSpaceMissingLogged = False


def _cancelCallbackSafe(cbid):
    try:
        if cbid is not None:
            BigWorld.cancelCallback(cbid)
    except (AttributeError, ValueError):
        pass


def _destroyWindowSafe(window):
    try:
        if window is None:
            return
        if getattr(window, 'proxy', None) is None:
            return
        if getattr(window, 'windowStatus', None) in _WINDOW_DEAD_STATUSES:
            return
        window.destroy()
    except Exception:
        logger.exception('[Watch] window destroy failed')


def _importClass(classPath):
    try:
        moduleName, className = classPath.rsplit('.', 1)
        module = __import__(moduleName, globals(), locals(), [className])
        return getattr(module, className, None)
    except Exception:
        return None


def _isHangarState(state):
    try:
        from gui.lobby_state_machine.states import isInHangarState
        if isInHangarState():
            return True
    except Exception:
        pass
    if state is None:
        return False
    try:
        from gui.lobby_state_machine.states import LobbyStateFlags
        if state.getFlags() & LobbyStateFlags.HANGAR:
            return True
    except Exception:
        pass
    try:
        from gui.lobby_state_machine.states import isHangarState
        return bool(isHangarState(state))
    except Exception:
        pass
    try:
        lsm = getLobbyStateMachine()
        if lsm:
            for classPath in _HANGAR_STATE_CLASS_PATHS:
                stateCls = _importClass(classPath)
                if stateCls is not None and state == lsm.getStateByCls(stateCls):
                    return True
    except Exception:
        pass
    return False


def _hangarSpace():
    global _hangarSpaceMissingLogged
    space = None
    if IHangarSpace is not None:
        try:
            space = dependency.instance(IHangarSpace)
        except Exception:
            space = None
    if space is None and not _hangarSpaceMissingLogged:
        _hangarSpaceMissingLogged = True
        logger.error('[Watch] IHangarSpace unavailable, hangar-ready gate is off')
    return space


def _isHangarSpaceReady():
    space = _hangarSpace()
    if space is None:
        return True
    try:
        return bool(space.spaceInited)
    except Exception:
        return True


def _isWindowBusy(window):
    try:
        return window.windowStatus in _WINDOW_BUSY_STATUSES
    except Exception:
        return False


def _isHangarSettled():
    if not _isHangarSpaceReady():
        return False
    try:
        manager = dependency.instance(IGuiLoader).windowsManager
        main = manager.getMainWindow()
    except Exception:
        return False
    if main is None or getattr(main, 'proxy', None) is None:
        return False
    try:
        if main.windowStatus != WindowStatus.LOADED:
            return False
    except Exception:
        return False
    if not _WINDOW_BUSY_STATUSES:
        return True
    try:
        return not manager.findWindows(_isWindowBusy)
    except Exception:
        return True


def _isHostAppInitialized(mode):
    if not _APP_STATE_OK:
        return None
    try:
        ns = APP_NAME_SPACE.SF_BATTLE if mode == 'battle' else APP_NAME_SPACE.SF_LOBBY
        return dependency.instance(IAppLoader).getAppStateID(ns) == ApplicationStateID.INITIALIZED
    except Exception:
        return None


def _dayNames():
    days = _l10n.get('days', _DAYS_DEFAULT)
    if not isinstance(days, list) or len(days) != 7:
        return list(_DAYS_DEFAULT)
    return days


def _loadLocalization():
    global _l10n
    try:
        import ResMgr
    except Exception:
        logger.exception('[Watch] ResMgr unavailable, built-in strings used')
        return
    for tryLang in (_CLIENT_LANG, _L10N_FALLBACK):
        path = _L10N_DIR + '/' + tryLang + '.json'
        try:
            section = ResMgr.openSection(path)
            if section is not None:
                loaded = json.loads(section.asBinary)
                if isinstance(loaded, dict):
                    _l10n = loaded
                    return
        except Exception:
            pass


def _tr(key, default=u''):
    return _l10n.get(key, default)


def _toBool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower() == 'true'


def _clamp(minVal, val, maxVal):
    return max(minVal, min(val, maxVal))


def _toColorList(value, default=None):
    fallback = list(default) if default else [255, 255, 255]
    if isinstance(value, (list, tuple)) and len(value) == 3:
        result = []
        for component in value:
            try:
                result.append(_clamp(0, int(component), 255))
            except (TypeError, ValueError, OverflowError):
                logger.error('[Config] bad colour component %r, keeping %s', component, fallback)
                return fallback
        return result
    if value is not None:
        logger.error('[Config] bad colour value %r, keeping %s', value, fallback)
    return fallback


def _toColorFromHex(value, default=None):
    fallback = list(default) if default else [255, 255, 255]
    try:
        text = str(value).strip().lstrip('#')
    except Exception:
        text = ''
    if len(text) == 3:
        text = ''.join(char * 2 for char in text)
    if len(text) != 6:
        logger.error('[Config] bad colour string %r, keeping %s', value, fallback)
        return fallback
    try:
        return [int(text[i:i + 2], 16) for i in (0, 2, 4)]
    except (TypeError, ValueError):
        logger.error('[Config] bad colour string %r, keeping %s', value, fallback)
        return fallback


def _parseOffset(value):
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            xPos = int(value[0])
            yPos = int(value[1])
        except (TypeError, ValueError, OverflowError):
            return None
        return [_clamp(-_OFFSET_LIMIT, xPos, _OFFSET_LIMIT), _clamp(-_OFFSET_LIMIT, yPos, _OFFSET_LIMIT)]
    return None


def _toOffsetList(value, default):
    parsed = _parseOffset(value)
    return list(default) if parsed is None else parsed


def _parseAnchor(value):
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            anchorX = str(value[0]).strip().lower()
            anchorY = str(value[1]).strip().lower()
        except Exception:
            return None
        if anchorX in _ANCHOR_X_VALUES and anchorY in _ANCHOR_Y_VALUES:
            return [anchorX, anchorY]
    return None


def _toAnchorList(value, default):
    parsed = _parseAnchor(value)
    return list(default) if parsed is None else parsed


def _anchorFromSignedOffset(offset):
    return [_ANCHOR_LEFT if offset[0] >= 0 else _ANCHOR_RIGHT,
            _ANCHOR_TOP if offset[1] >= 0 else _ANCHOR_BOTTOM]


def _readScheme(value, default):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.error('[Config] bad anchor scheme %r, assuming %s', value, default)
        return default


def _loadJsonFile(path):
    with open(path, 'rb') as f:
        raw = f.read()
    encoding = _CONFIG_ENCODING_UTF8
    if raw.startswith(_UTF8_BOM):
        raw = raw[len(_UTF8_BOM):]
        encoding = _CONFIG_ENCODING_UTF8_BOM
    text = raw.decode('utf-8')
    text = text.strip()
    return (json.loads(text) if text else {}, encoding)


def _saveJsonFile(path, data, encoding):
    text = json.dumps(data, indent=4, ensure_ascii=False)
    if not isinstance(text, unicode):
        text = text.decode('utf-8')
    raw = text.encode('utf-8')
    if encoding == _CONFIG_ENCODING_UTF8_BOM:
        raw = _UTF8_BOM + raw
    with open(path, 'wb') as f:
        f.write(raw)


_screenResolutionCache = None


def _probeScreenResolution():
    try:
        if GUI is not None:
            width, height = GUI.screenResolution()[:2]
            if width > 0 and height > 0:
                return (int(width), int(height))
    except Exception:
        pass
    try:
        width, height = BigWorld.screenWidth(), BigWorld.screenHeight()
        if width > 0 and height > 0:
            return (int(width), int(height))
    except Exception:
        pass
    return None


def _screenResolution():
    global _screenResolutionCache
    if _screenResolutionCache is not None:
        return _screenResolutionCache
    probed = _probeScreenResolution()
    if probed is None:
        return _BASE_SCREEN
    _screenResolutionCache = probed
    return probed


def _invalidateScreenResolution():
    global _screenResolutionCache
    _screenResolutionCache = None


_screenResolutionWatcherBound = False


def _installScreenResolutionWatcher():
    global _screenResolutionWatcherBound
    if g_guiResetters is None or _screenResolutionWatcherBound:
        return
    try:
        g_guiResetters.add(_invalidateScreenResolution)
        _screenResolutionWatcherBound = True
    except Exception:
        logger.exception('[Watch] failed to install the screen resolution watcher')


def _removeScreenResolutionWatcher():
    global _screenResolutionWatcherBound
    if g_guiResetters is None or not _screenResolutionWatcherBound:
        return
    _screenResolutionWatcherBound = False
    try:
        g_guiResetters.discard(_invalidateScreenResolution)
    except Exception:
        logger.exception('[Watch] failed to remove the screen resolution watcher')


def _interfaceScale():
    try:
        if ServicesLocator is not None:
            return float(ServicesLocator.settingsCore.interfaceScale.get())
    except Exception:
        pass
    return 1.0


def clampCoordinates(xPos, yPos, size, padX=0, padY=0, padBottom=None):
    if padBottom is None:
        padBottom = padY
    screenWidth, screenHeight = _screenResolution()
    maxX = max(padX, screenWidth - size[0] - padX)
    maxY = max(padY, screenHeight - size[1] - padBottom)
    clampedX = max(padX, min(int(round(xPos)), maxX))
    clampedY = max(padY, min(int(round(yPos)), maxY))
    return (clampedX, clampedY)


def _cursorPixels(cursor):
    normX, normY = cursor.position
    screenWidth, screenHeight = _screenResolution()
    pixelX = int((normX + 1.0) * 0.5 * screenWidth)
    pixelY = int((1.0 - normY) * 0.5 * screenHeight)
    return (pixelX, pixelY)


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
            'type': 'CheckBox',
            'text': header,
            'varName': self.tokenName,
            'value': self.value,
            'tooltip': _createTooltip(header, body)
        }


class _ColorParam(object):
    def __init__(self, tokenName, defaultValue=None):
        self.tokenName = tokenName
        self.value = list(defaultValue) if defaultValue else [255, 255, 255]
        self.defaultValue = list(self.value)

    @property
    def msaValue(self):
        c = self.value
        return '%02X%02X%02X' % (int(c[0]), int(c[1]), int(c[2]))

    @msaValue.setter
    def msaValue(self, v):
        if isinstance(v, (list, tuple)):
            self.value = _toColorList(v, self.value)
        else:
            self.value = _toColorFromHex(v, self.value)

    def renderParam(self, header, body=None):
        return {
            'type': 'ColorChoice',
            'text': header,
            'varName': self.tokenName,
            'value': self.msaValue,
            'tooltip': _createTooltip(header, body)
        }


class _ConfigParams(object):
    def __init__(self):
        self.enabled = _CheckboxParam('enabled', True)
        self.battleEnabled = _CheckboxParam('battle-enabled', True)
        self.garageEnabled = _CheckboxParam('garage-enabled', True)
        self.timeColor = _ColorParam('time-color', [255, 255, 255])
        self.use24h = _CheckboxParam('use-24h', True)
        self.showSeconds = _CheckboxParam('show-seconds', True)

    def items(self):
        return {
            self.enabled.tokenName: self.enabled,
            self.battleEnabled.tokenName: self.battleEnabled,
            self.garageEnabled.tokenName: self.garageEnabled,
            self.timeColor.tokenName: self.timeColor,
            self.use24h.tokenName: self.use24h,
            self.showSeconds.tokenName: self.showSeconds,
        }


g_configParams = _ConfigParams()


class _Config(object):
    def __init__(self):
        self.onConfigChanged = Event.Event()
        self._finalized = False
        self.battleOffset = list(_DEFAULT_BATTLE_OFFSET)
        self.garageOffset = list(_DEFAULT_GARAGE_OFFSET)
        self.battleAnchor = list(_DEFAULT_BATTLE_ANCHOR)
        self.garageAnchor = list(_DEFAULT_GARAGE_ANCHOR)
        self.legacyBattle = False
        self.legacyGarage = False
        self._configEncoding = _CONFIG_ENCODING_UTF8
        try:
            self._loadConfig()
        except Exception:
            logger.exception('[Config] Load failed completely, defaults kept')
        try:
            self._registerMod()
        except Exception:
            logger.exception('[Config] MSA registration failed')

    def fini(self):
        self._finalized = True
        self.onConfigChanged.clear()

    def setBattleOffset(self, offset, anchor=None):
        self._setAnchoredOffset('battle', offset, anchor)

    def setGarageOffset(self, offset, anchor=None):
        self._setAnchoredOffset('garage', offset, anchor)

    def _setAnchoredOffset(self, mode, offset, anchor):
        if mode == 'battle':
            newOffset = _toOffsetList(offset, _DEFAULT_BATTLE_OFFSET)
            newAnchor = list(self.battleAnchor) if anchor is None else _toAnchorList(anchor, self.battleAnchor)
            if newOffset == self.battleOffset and newAnchor == self.battleAnchor and not self.legacyBattle:
                return
            self.battleOffset = newOffset
            self.battleAnchor = newAnchor
            self.legacyBattle = False
        else:
            newOffset = _toOffsetList(offset, _DEFAULT_GARAGE_OFFSET)
            newAnchor = list(self.garageAnchor) if anchor is None else _toAnchorList(anchor, self.garageAnchor)
            if newOffset == self.garageOffset and newAnchor == self.garageAnchor and not self.legacyGarage:
                return
            self.garageOffset = newOffset
            self.garageAnchor = newAnchor
            self.legacyGarage = False
        self._saveConfig()

    def _readMode(self, data, prefix, globalScheme, defaultOffset, defaultAnchor):
        offsetKey = prefix + '-anchor-offset'
        scheme = _readScheme(data.get(prefix + '-anchor-scheme'), globalScheme)
        if offsetKey not in data:
            return (True, list(defaultOffset), list(defaultAnchor), False)
        offset = _parseOffset(data[offsetKey])
        if offset is None:
            logger.error('[Config] bad %s %r, default used', offsetKey, data[offsetKey])
            return (True, list(defaultOffset), list(defaultAnchor), False)
        if scheme >= _ANCHOR_SCHEME:
            anchor = _parseAnchor(data.get(prefix + '-anchor'))
            if anchor is not None:
                return (False, offset, anchor, False)
            logger.error('[Config] missing or bad %s-anchor, signed reading used', prefix)
            return (True, offset, _anchorFromSignedOffset(offset), False)
        if scheme == _ANCHOR_SCHEME_SIGNED:
            return (True, offset, _anchorFromSignedOffset(offset), False)
        return (True, offset, _anchorFromSignedOffset(offset), True)

    def _applyData(self, data):
        if not isinstance(data, dict):
            if data is not None:
                logger.error('[Config] config root is %s, not an object; defaults used', type(data).__name__)
            return True
        missing = False
        for token, param in g_configParams.items().items():
            if token not in data:
                missing = True
                continue
            try:
                if isinstance(param, _CheckboxParam):
                    param.value = _toBool(data[token])
                elif isinstance(param, _ColorParam):
                    param.value = _toColorList(data[token], param.value)
            except Exception:
                logger.error('[Config] unusable value for %s, default kept', token)
                missing = True

        globalScheme = _readScheme(data.get('anchor-scheme'), _ANCHOR_SCHEME_LEGACY)
        battleRepaired, self.battleOffset, self.battleAnchor, self.legacyBattle = self._readMode(
            data, 'battle', globalScheme, _DEFAULT_BATTLE_OFFSET, _DEFAULT_BATTLE_ANCHOR)
        garageRepaired, self.garageOffset, self.garageAnchor, self.legacyGarage = self._readMode(
            data, 'garage', globalScheme, _DEFAULT_GARAGE_OFFSET, _DEFAULT_GARAGE_ANCHOR)
        return missing or battleRepaired or garageRepaired

    def _loadConfig(self):
        data = {}
        existed = os.path.isfile(_CONFIG_PATH)
        if existed:
            try:
                data, self._configEncoding = _loadJsonFile(_CONFIG_PATH)
            except Exception as e:
                logger.error('[Config] Load failed, restoring defaults: %s', e)
                data = {}
                existed = False
                self._configEncoding = _CONFIG_ENCODING_UTF8
        try:
            repaired = self._applyData(data)
        except Exception:
            logger.exception('[Config] Config contents unusable, defaults applied')
            repaired = True
        if not existed or repaired:
            self._saveConfig()

    def _saveConfig(self):
        try:
            if not os.path.exists(WATCH_CONFIG_DIR):
                os.makedirs(WATCH_CONFIG_DIR)
            data = {}
            for token, param in g_configParams.items().items():
                data[token] = param.value
            battleScheme = _ANCHOR_SCHEME_LEGACY if self.legacyBattle else _ANCHOR_SCHEME
            garageScheme = _ANCHOR_SCHEME_LEGACY if self.legacyGarage else _ANCHOR_SCHEME
            data['battle-anchor-offset'] = list(self.battleOffset)
            data['battle-anchor'] = list(self.battleAnchor)
            data['battle-anchor-scheme'] = battleScheme
            data['garage-anchor-offset'] = list(self.garageOffset)
            data['garage-anchor'] = list(self.garageAnchor)
            data['garage-anchor-scheme'] = garageScheme
            data['anchor-scheme'] = min(battleScheme, garageScheme)
            _saveJsonFile(_CONFIG_PATH, data, self._configEncoding)
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
                    g_configParams.use24h.renderParam(
                        _tr('use24h.header', u'24-hour format'),
                        _tr('use24h.body', u'Use 24-hour time instead of AM/PM')
                    ),
                    g_configParams.showSeconds.renderParam(
                        _tr('showSeconds.header', u'Show seconds'),
                        _tr('showSeconds.body', u'Display seconds in the clock')
                    ),
                ]
            }
            settings = g_modsSettingsApi.setModTemplate(MOD_LINKAGE, template, self._onSettingsChanged)
            if settings:
                self._applyMsa(settings, save=False)
        except Exception as e:
            logger.error('[Config] MSA register failed: %s', e)

    def _applyMsa(self, settings, save=True):
        if not isinstance(settings, dict):
            logger.error('[Config] MSA settings are %s, not a mapping; ignored', type(settings).__name__)
            return
        params = g_configParams.items()
        applied = False
        for name, value in settings.items():
            param = params.get(name)
            if param is None:
                continue
            try:
                param.msaValue = value
                applied = True
            except Exception:
                logger.error('[Config] MSA sent an unusable value for %s, current value kept', name)
        if save and applied:
            self._saveConfig()

    def _onSettingsChanged(self, linkage, newSettings):
        if linkage != MOD_LINKAGE or self._finalized:
            return
        try:
            self._applyMsa(newSettings)
        except Exception:
            logger.exception('[Config] failed to apply MSA settings')
        try:
            self.onConfigChanged()
        except Exception:
            logger.exception('[Config] config listeners failed')


try:
    _loadLocalization()
except Exception:
    logger.exception('[Watch] localization load failed')
g_config = _Config()


def _buildPayload(mode, visible):
    p = g_configParams
    return json.dumps({
        'mode': mode,
        'visible': bool(visible),
        'color': p.timeColor.msaValue,
        'format': '24' if p.use24h.value else '12',
        'showSeconds': bool(p.showSeconds.value),
        'days': _dayNames(),
        'scale': _interfaceScale(),
    }, ensure_ascii=False)


if _GF_OK:

    class _ClockModel(ViewModel):
        def __init__(self, payload):
            self._payload = payload
            super(_ClockModel, self).__init__(properties=2, commands=2)

        def _initialize(self):
            super(_ClockModel, self)._initialize()
            self._addStringProperty('payload', self._payload)
            self._addStringProperty('shift', '0,0')
            self.onReady = self._addCommand('onReady')
            self.onCmd = self._addCommand('onCmd')

        def setPayload(self, value):
            self._setString(0, value)

        def setShift(self, value):
            self._setString(1, value)

    class _ClockView(ViewImpl):
        def __init__(self, owner):
            self._owner = owner
            self._viewToken = owner._token
            model = _ClockModel(owner.buildPayload())
            owner._setModel(model, publish=False)
            settings = ViewSettings(layoutID=owner.layoutID(), flags=ViewFlags.VIEW, model=model)
            super(_ClockView, self).__init__(settings)

        def _getEvents(self):
            model = self.getViewModel()
            return (
                (model.onReady, self._onViewReady),
                (model.onCmd, self._onCmd),
            )

        def _isCurrent(self):
            owner = self._owner
            return owner is not None and not owner._destroyed and self._viewToken == owner._token

        def _onViewReady(self, *args):
            if not self._isCurrent():
                logger.debug('[Watch] stale onReady dropped, token=%s', self._viewToken)
                return
            self._owner._onReady(*args)

        @args2params(str, str)
        def _onCmd(self, name, value):
            if not self._isCurrent():
                logger.debug('[Watch] stale command %s dropped, token=%s', name, self._viewToken)
                return
            try:
                self._owner._onCommand(name, value)
            except Exception:
                logger.exception('[Watch] command %s failed', name)

        def _finalize(self):
            if self._viewToken == self._owner._token:
                self._owner._setModel(None)
            super(_ClockView, self)._finalize()
            self._owner._onViewFinalized(self._viewToken)

    class _ClockWindow(WindowImpl):
        def __init__(self, content, parent, name, layer):
            super(_ClockWindow, self).__init__(WindowFlags.WINDOW, content=content, layer=layer, name=name, parent=parent)

        def _onReady(self):
            self.show(focus=False)

    class _ClockOverlay(object):
        def __init__(self, name, mode, size, getState, setState, getDefault):
            self._name = name
            self._mode = mode
            self._viewSize = (max(1, int(size[0])), max(1, int(size[1])))
            self._viewPad = 0
            self._getState = getState
            self._setState = setState
            self._getDefault = getDefault
            self._layout = ModDynAccessor('mods/under_pressure/%s/layoutID' % name)
            self._window = None
            self._model = None
            self._token = 0
            self._nativeReady = False
            self._destroyed = False
            self._active = False
            self._visible = True
            defaultOffset, defaultAnchor = getDefault()
            self._offset = list(defaultOffset)
            self._anchor = list(defaultAnchor)
            self._position = [0, 0]
            self._positionLoaded = False
            self._positionDirty = False
            self._legacyOffset = False
            self._sizeConfirmed = False
            self._lastSaved = None
            self._lastMove = None
            self._shift = [0, 0]
            self._stableScale = None
            self._scaleSample = None
            self._loggedState = None
            self._dragging = False
            self._dragMoved = False
            self._mouseWasDown = False
            self._pressArmed = False
            self._dragIdleTicks = 0
            self._dragStartCursor = None
            self._dragStartPosition = None
            self._dragCallbackID = None
            self._guiResetterBound = False
            self._resizeCallbackID = None
            self._sizeSyncCallbackID = None
            self._loadCallbackID = None
            self._scaleBound = False
            self._suspended = False
            self._parentUid = None
            self._settleFrames = 0
            self.parentGate = None

        def layoutID(self):
            return self._layout()

        def _windowLayer(self):
            return getattr(WindowLayer, 'WINDOW', WindowLayer.OVERLAY)

        def buildPayload(self):
            return _buildPayload(self._mode, self._visible)

        def enable(self):
            self._destroyed = False
            if self._active:
                self._ensureWindow()
                self.refresh()
                self._syncDragTicker()
                return
            self._active = True
            self._visible = True
            self._loadPosition()
            self._bindScaleListener()
            self._ensureWindow()
            self._syncDragTicker()

        def disable(self):
            self._active = False
            self._suspended = False
            self._stopDragTicker()
            self._unbindScaleListener()
            self._flushPosition()
            self._destroyed = True
            self._positionLoaded = False
            self._dropWindow()

        def suspend(self):
            if self._suspended:
                return
            self._suspended = True
            self._stopDragTicker()
            self._flushPosition()
            self._dropWindow()

        def resume(self):
            if not self._suspended:
                return
            self._suspended = False
            if self._active and not self._destroyed:
                self._ensureWindow()
            self._syncDragTicker()

        def setVisible(self, value):
            value = bool(value)
            if value == self._visible:
                return
            self._visible = value
            self.publish()
            self._syncDragTicker()

        def refresh(self):
            self.publish()

        def _setModel(self, model, publish=True):
            self._model = model
            self._shift = [0, 0]
            if publish:
                self.publish()

        def publish(self):
            if self._destroyed or self._window is None:
                return
            if self._model is None:
                return
            payload = _buildPayload(self._mode, self._visible)
            try:
                with self._model.transaction() as model:
                    model.setPayload(payload)
            except Exception:
                pass

        def _publishShift(self, shift):
            newShift = [int(shift[0]), int(shift[1])]
            if newShift == self._shift:
                return
            self._shift = newShift
            if self._destroyed or self._window is None:
                return
            if self._model is None:
                return
            try:
                with self._model.transaction() as model:
                    model.setShift('%d,%d' % (newShift[0], newShift[1]))
            except Exception:
                pass

        def logWindowState(self, tag):
            if not logger.isEnabledFor(logging.DEBUG):
                return
            window = self._window
            if not self._isWindowUsable():
                logger.debug('[Watch:%s] winstate[%s]: no usable window', self._name, tag)
                return
            try:
                logger.debug('[Watch:%s] winstate[%s]: status=%s size=%s pos=%s globalPos=%s layer=%s '
                             'screen=%s viewSize=%s pad=%s intended=%s offset=%s scale=%s lastMove=%s shift=%s',
                             self._name, tag, window.windowStatus, window.size, window.position,
                             window.globalPosition, window.layer, _screenResolution(), self._viewSize,
                             self._viewPad, self._position, self._offset, self._stableScale,
                             self._lastMove, self._shift)
            except Exception:
                pass

        def _onReady(self, *args):
            self._nativeReady = True
            self.publish()
            self._syncPosition()
            self._bindGuiResetter()
            self._syncDragTicker()
            self.logWindowState('ready')

        def _onCommand(self, name, value):
            if name == 'onSize':
                try:
                    parts = unicode(value).split(u'@')
                    sizeParts = parts[0].split(u'x')
                    width = max(1, int(float(sizeParts[0])))
                    height = max(1, int(float(sizeParts[1])))
                    pad = max(0, int(float(parts[1]))) if len(parts) > 1 else 0
                except Exception:
                    return
                first = not self._sizeConfirmed
                changed = (width, height) != tuple(self._viewSize) or pad != self._viewPad
                self._sizeConfirmed = True
                if not first and not changed:
                    return
                self._viewSize = (width, height)
                self._viewPad = pad
                if self._dragging:
                    return
                _cancelCallbackSafe(self._sizeSyncCallbackID)
                self._sizeSyncCallbackID = BigWorld.callback(0.0, self._syncAfterViewSize)

        def _syncAfterViewSize(self):
            self._sizeSyncCallbackID = None
            if not self._isWindowUsable():
                return
            self._syncPosition()
            self._logSizeState()

        def _logSizeState(self):
            state = (tuple(self._viewSize), self._viewPad, tuple(self._position))
            if state == self._loggedState:
                return
            self._loggedState = state
            self.logWindowState('onSize')

        def _onViewFinalized(self, token=None):
            logger.debug('[Watch:%s] view finalized token=%s current=%s', self._name, token, self._token)
            if token is not None and token != self._token:
                return
            self._unbindGuiResetter()
            _cancelCallbackSafe(self._sizeSyncCallbackID)
            self._sizeSyncCallbackID = None
            self._window = None
            self._model = None
            self._nativeReady = False
            self._sizeConfirmed = False
            self._stableScale = None
            self._scaleSample = None
            self._parentUid = None
            self._token += 1
            self._stopDragTicker()

        def _isWindowUsable(self):
            if self._destroyed or self._window is None:
                return False
            if getattr(self._window, 'proxy', None) is None:
                return False
            try:
                return self._window.windowStatus not in _WINDOW_DEAD_STATUSES
            except Exception:
                return False

        def _ensureWindow(self):
            if self._destroyed or self._suspended:
                return
            if self._window is not None:
                if self._parentUid is None:
                    return
                try:
                    current = dependency.instance(IGuiLoader).windowsManager.getMainWindow()
                except Exception:
                    current = None
                currentUid = getattr(current, 'uniqueID', None)
                if current is None or currentUid is None or currentUid == self._parentUid:
                    return
                self._dropWindow()
            _cancelCallbackSafe(self._loadCallbackID)
            self._loadCallbackID = None
            if gamefaceResMap is None:
                return
            self._token += 1
            self._settleFrames = _LOAD_SETTLE_FRAMES
            token = self._token
            if gamefaceResMap.isResMapValidated:
                self._load(token)
            else:
                gamefaceOnReady(lambda: self._load(token))

        def _retryLoad(self, token, retry, reason):
            if retry >= _LOAD_RETRY_LIMIT:
                logger.error('[Watch:%s] load abandoned after %d retries: %s', self._name, retry, reason)
                return
            self._loadCallbackID = BigWorld.callback(_LOAD_RETRY_DELAY, lambda: self._load(token, retry + 1))

        def _load(self, token, retry=0):
            self._loadCallbackID = None
            if token != self._token or self._destroyed or self._suspended or self._window is not None:
                return
            appReady = _isHostAppInitialized(self._mode)
            if appReady is False:
                self._retryLoad(token, retry, 'host app not initialized')
                return
            try:
                manager = dependency.instance(IGuiLoader).windowsManager
                parent = manager.getMainWindow()
            except Exception:
                manager = None
                parent = None
            if parent is None or parent.proxy is None or parent.windowStatus != WindowStatus.LOADED:
                self._retryLoad(token, retry, 'main window not loaded')
                return
            if self.parentGate is not None:
                try:
                    allowed = bool(self.parentGate(parent))
                except Exception:
                    logger.exception('[Watch:%s] parent gate failed', self._name)
                    allowed = False
                if not allowed:
                    self._retryLoad(token, retry, 'parent gate closed')
                    return
            if self._mode == 'garage' and manager is not None and _WINDOW_BUSY_STATUSES:
                try:
                    busy = bool(manager.findWindows(
                        lambda window: getattr(window, 'windowStatus', None) in _WINDOW_BUSY_STATUSES))
                except Exception:
                    busy = False
                if busy:
                    self._retryLoad(token, retry, 'lobby still busy')
                    return
            if self._settleFrames > 0:
                self._settleFrames -= 1
                self._loadCallbackID = BigWorld.callback(_LOAD_SETTLE_HOLD, lambda: self._load(token, retry))
                return
            try:
                logger.debug('[Watch:%s] create parent=%s retry=%d appReady=%s', self._name,
                             getattr(parent, 'uniqueID', None), retry, appReady)
                self._parentUid = getattr(parent, 'uniqueID', None)
                self._window = _ClockWindow(_ClockView(self), parent, self._name, self._windowLayer())
                self._window.load()
            except Exception:
                logger.exception('[Watch] Failed to load overlay %s', self._name)
                self._window = None
                self._model = None
                self._parentUid = None
                return

        def _dropWindow(self):
            self._unbindGuiResetter()
            _cancelCallbackSafe(self._sizeSyncCallbackID)
            self._sizeSyncCallbackID = None
            _cancelCallbackSafe(self._loadCallbackID)
            self._loadCallbackID = None
            self._token += 1
            window = self._window
            self._window = None
            self._model = None
            self._nativeReady = False
            self._sizeConfirmed = False
            self._stableScale = None
            self._scaleSample = None
            self._parentUid = None
            self._shift = [0, 0]
            self._stopDragTicker()
            if window is not None:
                logger.debug('[Watch:%s] drop scheduled', self._name)
                try:
                    BigWorld.callback(0.0, lambda: _destroyWindowSafe(window))
                except Exception:
                    logger.exception('[Watch] deferred destroy scheduling failed for %s', self._name)

        def _windowScale(self):
            cached = self._stableScale
            fallback = (cached, cached) if cached is not None else (1.0, 1.0)
            window = self._window
            if not self._isWindowUsable():
                return fallback
            try:
                nativeW, nativeH = window.size[:2]
                nativeW = float(nativeW)
                nativeH = float(nativeH)
            except Exception:
                return fallback
            viewW = float(self._viewSize[0] + self._viewPad * 2)
            viewH = float(self._viewSize[1] + self._viewPad * 2)
            if nativeW <= 10 or nativeH <= 10 or viewW <= 10 or viewH <= 10:
                return fallback
            sample = (int(nativeW), int(nativeH), int(viewW), int(viewH))
            confirmed = sample == self._scaleSample
            self._scaleSample = sample
            scaleW = viewW / nativeW
            scaleH = viewH / nativeH
            if abs(scaleW - scaleH) > 0.1 or not 0.4 <= scaleW <= 4.0:
                return fallback
            raw = scaleW if viewW >= viewH else scaleH
            if cached is None:
                self._stableScale = raw
                return (raw, raw)
            if abs(raw - cached) / cached > 0.05:
                if not confirmed:
                    return fallback
                self._stableScale = raw
                return (raw, raw)
            return (cached, cached)

        def _move(self):
            if not self._isWindowUsable() or not self._nativeReady or not self._sizeConfirmed:
                return
            self._clampPosition()
            scaleX, scaleY = self._windowScale()
            originX = int(self._position[0]) - self._viewPad
            originY = int(self._position[1]) - self._viewPad
            try:
                self._lastMove = (originX, originY,
                                  self._window.move(int(round(originX / scaleX)),
                                                    int(round(originY / scaleY))))
            except Exception:
                logger.exception('[Watch] move failed for %s', self._name)
                return
            self._syncShift(originX, originY, scaleX, scaleY)

        def _syncShift(self, wantX, wantY, scaleX, scaleY):
            if not self._isWindowUsable() or not self._nativeReady:
                return
            try:
                actualX, actualY = self._window.position[:2]
            except Exception:
                return
            self._publishShift((int(round(wantX - actualX * scaleX)),
                                int(round(wantY - actualY * scaleY))))

        def _syncPosition(self):
            if self._legacyOffset and self._sizeConfirmed:
                self._convertLegacyOffset()
            screenWidth, screenHeight = _screenResolution()
            width, height = self._viewSize
            offsetX, offsetY = self._offset[0], self._offset[1]
            anchorX, anchorY = self._anchor[0], self._anchor[1]
            xPos = offsetX if anchorX == _ANCHOR_LEFT else screenWidth + offsetX - width
            yPos = offsetY if anchorY == _ANCHOR_TOP else screenHeight + offsetY - height
            self._position = [int(xPos), int(yPos)]
            self._move()

        def _syncOffsetFromPosition(self):
            screenWidth, screenHeight = _screenResolution()
            xPos, yPos = int(self._position[0]), int(self._position[1])
            width, height = self._viewSize
            if (xPos + width * 0.5) < screenWidth * 0.5:
                anchorX, offsetX = _ANCHOR_LEFT, xPos
            else:
                anchorX, offsetX = _ANCHOR_RIGHT, xPos + width - screenWidth
            if (yPos + height * 0.5) < screenHeight * 0.5:
                anchorY, offsetY = _ANCHOR_TOP, yPos
            else:
                anchorY, offsetY = _ANCHOR_BOTTOM, yPos + height - screenHeight
            self._offset = [int(offsetX), int(offsetY)]
            self._anchor = [anchorX, anchorY]

        def _savedKey(self):
            return (self._offset[0], self._offset[1], self._anchor[0], self._anchor[1])

        def _convertLegacyOffset(self):
            self._legacyOffset = False
            screenWidth, screenHeight = _screenResolution()
            width = self._viewSize[0]
            offsetX, offsetY = self._offset[0], self._offset[1]
            if self._mode == 'battle':
                xPos = offsetX if offsetX >= 0 else screenWidth + offsetX
                yPos = offsetY if offsetY >= 0 else screenHeight + offsetY
            else:
                xPos = screenWidth - width + offsetX
                yPos = offsetY
            self._position = [int(xPos), int(yPos)]
            self._clampPosition()
            self._syncOffsetFromPosition()
            try:
                self._setState([self._offset[0], self._offset[1]], list(self._anchor))
            except Exception:
                logger.exception('[Watch] offset migration failed for %s', self._name)
                self._legacyOffset = True
                return
            self._lastSaved = self._savedKey()
            self._positionDirty = False

        def _bindGuiResetter(self):
            if self._guiResetterBound or g_guiResetters is None:
                return
            g_guiResetters.add(self._onScreenResize)
            self._guiResetterBound = True

        def _unbindGuiResetter(self):
            _cancelCallbackSafe(self._resizeCallbackID)
            self._resizeCallbackID = None
            if not self._guiResetterBound:
                return
            try:
                g_guiResetters.discard(self._onScreenResize)
            except Exception:
                pass
            self._guiResetterBound = False

        def _onScreenResize(self):
            _invalidateScreenResolution()
            if not self._isWindowUsable():
                return
            self._syncPosition()
            self.logWindowState('resize')
            _cancelCallbackSafe(self._resizeCallbackID)
            self._resizeCallbackID = BigWorld.callback(0.2, self._resizeResync)

        def _resizeResync(self):
            self._resizeCallbackID = None
            _invalidateScreenResolution()
            if not self._isWindowUsable():
                return
            self.publish()
            self._syncPosition()
            self.logWindowState('resize+0.2s')

        def _bindScaleListener(self):
            if self._scaleBound or ServicesLocator is None:
                return
            try:
                ServicesLocator.settingsCore.interfaceScale.onScaleChanged += self._onScaleChanged
                self._scaleBound = True
            except Exception:
                pass

        def _unbindScaleListener(self):
            if not self._scaleBound:
                return
            self._scaleBound = False
            try:
                ServicesLocator.settingsCore.interfaceScale.onScaleChanged -= self._onScaleChanged
            except Exception:
                pass

        def _onScaleChanged(self, *args):
            self._stableScale = None
            self._scaleSample = None
            self.publish()
            self._syncPosition()
            self.logWindowState('scale')

        def _dragTickerWanted(self):
            return (self._active
                    and not self._destroyed
                    and not self._suspended
                    and self._visible
                    and self._nativeReady
                    and self._isWindowUsable())

        def _syncDragTicker(self):
            if self._dragTickerWanted():
                self._startDragTicker()
            else:
                self._stopDragTicker()

        def _startDragTicker(self):
            if self._dragCallbackID is not None:
                return
            self._dragIdleTicks = 0
            self._pressArmed = False
            self._mouseWasDown = True
            self._dragCallbackID = BigWorld.callback(_DRAG_TICK_HOVER, self._updateDragState)

        def _stopDragTicker(self):
            _cancelCallbackSafe(self._dragCallbackID)
            self._dragCallbackID = None
            if self._dragging:
                self._finishDrag()
            self._dragging = False
            self._dragMoved = False
            self._mouseWasDown = False
            self._pressArmed = False
            self._dragIdleTicks = 0
            self._dragStartCursor = None
            self._dragStartPosition = None

        def _updateDragState(self):
            self._dragCallbackID = None
            if not self._dragTickerWanted():
                if self._dragging:
                    self._finishDrag()
                self._dragging = False
                self._mouseWasDown = False
                self._pressArmed = False
                return
            interval = _DRAG_TICK_IDLE
            try:
                interval = self._handleMouseDrag()
            except Exception:
                logger.exception('[Watch] drag tick failed for %s', self._name)
            if self._dragCallbackID is None and self._dragTickerWanted():
                self._dragCallbackID = BigWorld.callback(interval, self._updateDragState)

        def _handleMouseDrag(self):
            cursor = GUI.mcursor()
            if not cursor.visible or not cursor.inWindow or not cursor.inFocus:
                if self._dragging:
                    self._finishDrag()
                self._dragging = False
                self._mouseWasDown = False
                self._pressArmed = False
                self._dragIdleTicks += 1
                if self._dragIdleTicks >= _DRAG_IDLE_GRACE:
                    return _DRAG_TICK_SLEEP
                return _DRAG_TICK_IDLE
            mouseDown = BigWorld.isKeyDown(Keys.KEY_LEFTMOUSE)
            cursorPos = _cursorPixels(cursor)
            if not self._dragging and not self._isCursorNear(cursorPos):
                self._mouseWasDown = mouseDown
                self._pressArmed = False
                self._dragIdleTicks += 1
                return _DRAG_TICK_IDLE
            self._dragIdleTicks = 0
            if not self._pressArmed:
                if mouseDown:
                    self._mouseWasDown = True
                    return _DRAG_TICK_HOVER
                self._pressArmed = True
                self._mouseWasDown = False
            if mouseDown and not self._mouseWasDown:
                over = self._isCursorOver(cursorPos)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('[Watch:%s] press cursor=%s pos=%s viewSize=%s pad=%s shift=%s '
                                 'nativePos=%s nativeSize=%s over=%s',
                                 self._name, cursorPos, tuple(self._position), self._viewSize,
                                 self._viewPad, self._shift, getattr(self._window, 'position', None),
                                 getattr(self._window, 'size', None), over)
                if over:
                    self._dragging = True
                    self._dragMoved = False
                    self._dragStartCursor = cursorPos
                    self._dragStartPosition = tuple(self._position)
            elif not mouseDown:
                if self._dragging:
                    self._finishDrag()
                self._dragging = False
            if self._dragging and self._dragStartCursor is not None and self._dragStartPosition is not None:
                dx = cursorPos[0] - self._dragStartCursor[0]
                dy = cursorPos[1] - self._dragStartCursor[1]
                if self._dragMoved or dx * dx + dy * dy >= _DRAG_THRESHOLD * _DRAG_THRESHOLD:
                    self._dragMoved = True
                    self._setPosition(self._dragStartPosition[0] + dx, self._dragStartPosition[1] + dy)
            self._mouseWasDown = mouseDown
            return _DRAG_TICK_ACTIVE if self._dragging else _DRAG_TICK_HOVER

        def _finishDrag(self):
            self._dragging = False
            moved = self._dragMoved
            self._dragMoved = False
            self._flushPosition()
            if moved:
                self.logWindowState('dragEnd')

        def _isCursorNear(self, cursorPos):
            left, top = self._position[0], self._position[1]
            width, height = self._viewSize
            return (left - _DRAG_NEAR_PAD <= cursorPos[0] <= left + width + _DRAG_NEAR_PAD and
                    top - _DRAG_NEAR_PAD <= cursorPos[1] <= top + height + _DRAG_NEAR_PAD)

        def _isCursorOver(self, cursorPos):
            if not self._visible or not self._isWindowUsable():
                return False
            left, top = self._position[0], self._position[1]
            width, height = self._viewSize
            return (left - _GRAB_PAD <= cursorPos[0] <= left + width + _GRAB_PAD and
                    top - _GRAB_PAD <= cursorPos[1] <= top + height + _GRAB_PAD)

        def _bottomMargin(self):
            return _GARAGE_BOTTOM_MARGIN if self._mode == 'garage' else 0

        def _applyEdgeSnap(self, x, y):
            threshold = _GARAGE_EDGE_SNAP if self._mode == 'garage' else 0
            if threshold <= 0:
                return (x, y)
            screenWidth, _ = _screenResolution()
            width = self._viewSize[0]
            if x <= threshold:
                x = 0
            elif x + width >= screenWidth - threshold:
                x = screenWidth - width
            if y <= threshold:
                y = 0
            return (x, y)

        def _setPosition(self, x, y):
            x, y = self._applyEdgeSnap(x, y)
            cx, cy = clampCoordinates(x, y, self._viewSize, 0, 0, self._bottomMargin())
            if cx == self._position[0] and cy == self._position[1]:
                return
            self._position[0] = cx
            self._position[1] = cy
            self._positionDirty = True
            self._move()

        def _clampPosition(self):
            cx, cy = clampCoordinates(self._position[0], self._position[1], self._viewSize, 0, 0, self._bottomMargin())
            self._position[0] = cx
            self._position[1] = cy

        def _loadPosition(self):
            if self._positionLoaded:
                return
            self._positionLoaded = True
            defaultOffset, defaultAnchor = self._getDefault()
            offset, anchor, legacy = list(defaultOffset), list(defaultAnchor), False
            try:
                offset, anchor, legacy = self._getState()
            except Exception:
                logger.exception('[Watch] failed to read the stored position for %s', self._name)
            self._offset = list(offset)
            self._anchor = _toAnchorList(anchor, defaultAnchor)
            self._legacyOffset = bool(legacy)
            self._lastSaved = self._savedKey()
            self._positionDirty = False

        def _flushPosition(self):
            if not self._positionDirty:
                return
            self._syncOffsetFromPosition()
            current = self._savedKey()
            if self._lastSaved == current:
                self._positionDirty = False
                return
            try:
                self._setState([self._offset[0], self._offset[1]], list(self._anchor))
            except Exception:
                logger.exception('[Watch] failed to store the position for %s', self._name)
                return
            self._lastSaved = current
            self._positionDirty = False

    def _makeOverlay(name, mode, size, getState, setState, getDefault):
        return _ClockOverlay(name, mode, size, getState, setState, getDefault)

else:

    class _NullOverlay(object):
        def enable(self):
            pass

        def disable(self):
            pass

        def setVisible(self, value):
            pass

        def refresh(self):
            pass

        def suspend(self):
            pass

        def resume(self):
            pass

        def logWindowState(self, tag):
            pass

    def _makeOverlay(name, mode, size, getState, setState, getDefault):
        return _NullOverlay()


def _battleState():
    return (list(g_config.battleOffset), list(g_config.battleAnchor), bool(g_config.legacyBattle))


def _garageState():
    return (list(g_config.garageOffset), list(g_config.garageAnchor), bool(g_config.legacyGarage))


def _battleDefaults():
    return (list(_DEFAULT_BATTLE_OFFSET), list(_DEFAULT_BATTLE_ANCHOR))


def _garageDefaults():
    return (list(_DEFAULT_GARAGE_OFFSET), list(_DEFAULT_GARAGE_ANCHOR))


class _BattleClock(object):
    def __init__(self):
        self._overlay = _makeOverlay(
            _BATTLE_NAME, 'battle', _BATTLE_SIZE,
            _battleState, g_config.setBattleOffset, _battleDefaults)
        self._pageReady = False
        self._guiBound = False
        self._configBound = False
        self._hiddenByUI = False
        self._hiddenByStats = False

    def onBattlePageReady(self):
        self._pageReady = True
        self._hiddenByUI = False
        self._hiddenByStats = False
        self._bindGUI()
        self._bindConfig()
        if not (g_configParams.enabled.value and g_configParams.battleEnabled.value):
            return
        self._overlay.enable()
        self._overlay.setVisible(self._isVisible())

    def onBattlePageDisposed(self):
        self._pageReady = False
        self._unbindGUI()
        self._unbindConfig()
        self._overlay.disable()

    def suspend(self):
        self._overlay.suspend()

    def resume(self):
        self._overlay.resume()

    def fini(self):
        self.onBattlePageDisposed()

    def _bindConfig(self):
        if self._configBound:
            return
        self._configBound = True
        g_config.onConfigChanged += self._onConfigChanged

    def _unbindConfig(self):
        if not self._configBound:
            return
        self._configBound = False
        try:
            g_config.onConfigChanged -= self._onConfigChanged
        except Exception:
            pass

    def _onConfigChanged(self):
        if not (g_configParams.enabled.value and g_configParams.battleEnabled.value):
            self._overlay.disable()
            return
        if self._pageReady:
            self._overlay.enable()
            self._overlay.setVisible(self._isVisible())

    def _bindGUI(self):
        if self._guiBound:
            return
        self._guiBound = True
        try:
            g_eventBus.addListener(GameEvent.GUI_VISIBILITY, self._onGUIVisibility, scope=EVENT_BUS_SCOPE.BATTLE)
            g_eventBus.addListener(GameEvent.FULL_STATS, self._onToggleStats, scope=EVENT_BUS_SCOPE.BATTLE)
            g_eventBus.addListener(GameEvent.FULL_STATS_QUEST_PROGRESS, self._onToggleStats, scope=EVENT_BUS_SCOPE.BATTLE)
            g_eventBus.addListener(GameEvent.FULL_STATS_PERSONAL_RESERVES, self._onToggleStats, scope=EVENT_BUS_SCOPE.BATTLE)
        except Exception:
            pass

    def _unbindGUI(self):
        if not self._guiBound:
            return
        self._guiBound = False
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
            self._overlay.setVisible(self._isVisible())

    def _onToggleStats(self, event):
        hidden = event.ctx.get('isDown', False)
        if hidden != self._hiddenByStats:
            self._hiddenByStats = hidden
            self._overlay.setVisible(self._isVisible())

    def _isVisible(self):
        return not self._hiddenByUI and not self._hiddenByStats


class _GarageClock(object):
    def __init__(self):
        self._overlay = _makeOverlay(
            _GARAGE_NAME, 'garage', _GARAGE_SIZE,
            _garageState, g_config.setGarageOffset, _garageDefaults)
        self._stateMachine = None
        self._smCallbackID = None
        self._isGarage = False
        self._configBound = False
        self._settleCbId = None
        self._frameCbId = None
        self._settleWaits = 0
        self._settleFrames = 0
        self._ensureReason = None
        self._hangarSpaceBound = False
        self._gateBound = False

    def bind(self, retry=0):
        _cancelCallbackSafe(self._smCallbackID)
        self._smCallbackID = None
        stateMachine = getLobbyStateMachine()
        if stateMachine is None:
            if retry < 100:
                self._smCallbackID = BigWorld.callback(0.1, lambda: self.bind(retry + 1))
            return
        if self._stateMachine is not stateMachine:
            self.unbind()
            self._stateMachine = stateMachine
            stateMachine.onVisibleRouteChanged += self._onVisibleRouteChanged
        if not self._configBound:
            self._configBound = True
            g_config.onConfigChanged += self._onConfigChanged
        if not self._gateBound and hasattr(self._overlay, 'parentGate'):
            self._gateBound = True
            self._overlay.parentGate = self._isParentReady
        self._bindHangarSpace()
        self._onVisibleRouteChanged(getattr(stateMachine, 'visibleRouteInfo', None))

    def unbind(self):
        self._cancelSettle()
        self._unbindHangarSpace()
        if self._smCallbackID is not None:
            _cancelCallbackSafe(self._smCallbackID)
            self._smCallbackID = None
        if self._stateMachine is not None:
            try:
                self._stateMachine.onVisibleRouteChanged -= self._onVisibleRouteChanged
            except Exception:
                pass
            self._stateMachine = None
        if self._configBound:
            self._configBound = False
            try:
                g_config.onConfigChanged -= self._onConfigChanged
            except Exception:
                pass
        self._isGarage = False

    def disable(self):
        self._cancelSettle()
        self.unbind()
        self._overlay.disable()

    def fini(self):
        self.disable()

    def _onVisibleRouteChanged(self, routeInfo):
        state = getattr(routeInfo, 'state', None)
        self._isGarage = self._checkGarageState(state)
        if self._shouldShow():
            self._requestEnsure('route')
        else:
            self._cancelSettle()
            self._overlay.disable()

    def _checkGarageState(self, state):
        if state is None:
            return False
        sm = self._stateMachine
        if sm is not None and (DefaultHangarState is not None or LegacyHangarState is not None):
            try:
                targets = []
                if DefaultHangarState is not None:
                    targets.append(sm.getStateByCls(DefaultHangarState))
                if LegacyHangarState is not None:
                    targets.append(sm.getStateByCls(LegacyHangarState))
                targets = [target for target in targets if target is not None]
                if state in targets:
                    return True
            except Exception:
                pass
        return _isHangarState(state)

    def _onConfigChanged(self):
        self._onVisibleRouteChanged(getattr(self._stateMachine, 'visibleRouteInfo', None))

    def _shouldShow(self):
        try:
            return bool(_GF_OK
                        and self._isGarage
                        and g_configParams.enabled.value
                        and g_configParams.garageEnabled.value)
        except Exception:
            logger.exception('[Watch] garage visibility check failed')
            return False

    def _isParentReady(self, parent):
        if not _isHangarSpaceReady():
            return False
        try:
            return parent.windowStatus == WindowStatus.LOADED
        except Exception:
            return False

    def _requestEnsure(self, reason):
        self._ensureReason = reason
        self._settleWaits = 0
        self._scheduleSettle(_GARAGE_SETTLE_DELAY)

    def _scheduleSettle(self, delay):
        _cancelCallbackSafe(self._settleCbId)
        self._settleCbId = None
        _cancelCallbackSafe(self._frameCbId)
        self._frameCbId = None
        try:
            self._settleCbId = BigWorld.callback(delay, self._settleTick)
        except Exception:
            logger.exception('[Watch] failed to schedule garage settle')

    def _cancelSettle(self):
        _cancelCallbackSafe(self._settleCbId)
        self._settleCbId = None
        _cancelCallbackSafe(self._frameCbId)
        self._frameCbId = None
        self._settleWaits = 0
        self._settleFrames = 0

    def _retrySettle(self):
        self._settleWaits += 1
        if self._settleWaits > _GARAGE_SETTLE_MAX_WAITS:
            logger.error('[Watch] garage settle budget exhausted, reason=%s', self._ensureReason)
            return False
        self._scheduleSettle(_GARAGE_SETTLE_RETRY)
        return True

    def _settleTick(self):
        self._settleCbId = None
        try:
            if not self._shouldShow():
                return
            if not _isHangarSettled():
                self._retrySettle()
                return
            self._settleFrames = _GARAGE_SETTLE_FRAMES
            self._frameTick()
        except Exception:
            logger.exception('[Watch] garage settle tick failed')

    def _frameTick(self):
        self._frameCbId = None
        try:
            if not self._shouldShow():
                return
            if self._settleFrames > 0:
                self._settleFrames -= 1
                self._frameCbId = BigWorld.callback(_GARAGE_SETTLE_HOLD, self._frameTick)
                return
            if not _isHangarSettled():
                logger.debug('[Watch] hangar unsettled at commit, waits=%d', self._settleWaits)
                self._retrySettle()
                return
            self._commitEnsure()
        except Exception:
            logger.exception('[Watch] garage frame tick failed')

    def _commitEnsure(self):
        if not self._shouldShow():
            return
        self._settleWaits = 0
        self._overlay.enable()
        self._overlay.setVisible(True)

    def _bindHangarSpace(self):
        if self._hangarSpaceBound:
            return
        space = _hangarSpace()
        if space is None:
            return
        try:
            space.onSpaceCreate += self._onHangarSpaceCreate
            space.onSpaceDestroy += self._onHangarSpaceDestroy
        except Exception:
            logger.exception('[Watch] failed to bind hangar space events')
            return
        self._hangarSpaceBound = True
        logger.debug('[Watch] hangar space events bound')

    def _unbindHangarSpace(self):
        if not self._hangarSpaceBound:
            return
        self._hangarSpaceBound = False
        space = _hangarSpace()
        if space is None:
            return
        try:
            space.onSpaceCreate -= self._onHangarSpaceCreate
            space.onSpaceDestroy -= self._onHangarSpaceDestroy
        except Exception:
            logger.exception('[Watch] failed to unbind hangar space events')

    def _onHangarSpaceCreate(self, *_):
        try:
            if self._isGarage:
                self._requestEnsure('space')
        except Exception:
            logger.exception('[Watch] hangar space create handler failed')

    def _onHangarSpaceDestroy(self, *_):
        try:
            self._cancelSettle()
            self._overlay.disable()
        except Exception:
            logger.exception('[Watch] hangar space destroy handler failed')


_ORIGINAL_BATTLE_POPULATE = None
_ORIGINAL_BATTLE_DISPOSE = None
_HOOKS_INSTALLED = False


def _battlePagePopulate(self, *args, **kwargs):
    result = _ORIGINAL_BATTLE_POPULATE(self, *args, **kwargs)
    try:
        _g_WatchMod.onBattlePageReady()
    except Exception:
        logger.exception('[Watch] battle page ready hook failed')
    return result


def _battlePageDispose(self, *args, **kwargs):
    try:
        _g_WatchMod.onBattlePageDisposed()
    except Exception:
        logger.exception('[Watch] battle page dispose hook failed')
    return _ORIGINAL_BATTLE_DISPOSE(self, *args, **kwargs)


def _installHooks():
    global _HOOKS_INSTALLED, _ORIGINAL_BATTLE_POPULATE, _ORIGINAL_BATTLE_DISPOSE
    if _HOOKS_INSTALLED or SharedPage is None:
        return
    _ORIGINAL_BATTLE_POPULATE = SharedPage._populate
    _ORIGINAL_BATTLE_DISPOSE = SharedPage._dispose
    SharedPage._populate = _battlePagePopulate
    SharedPage._dispose = _battlePageDispose
    _HOOKS_INSTALLED = True


def _restoreHooks():
    global _HOOKS_INSTALLED
    if not _HOOKS_INSTALLED or SharedPage is None:
        return
    if SharedPage._populate is _battlePagePopulate:
        SharedPage._populate = _ORIGINAL_BATTLE_POPULATE
    if SharedPage._dispose is _battlePageDispose:
        SharedPage._dispose = _ORIGINAL_BATTLE_DISPOSE
    _HOOKS_INSTALLED = False


class _WatchMod(object):
    def __init__(self):
        self._battleClock = _BattleClock()
        self._garageClock = _GarageClock()
        self._eventsBound = False

    def init(self):
        if self._eventsBound:
            return
        self._eventsBound = True
        if _GF_OK:
            _installHooks()
        _installScreenResolutionWatcher()
        g_playerEvents.onAccountShowGUI += self._onAccountShowGUI
        g_playerEvents.onAvatarBecomePlayer += self._onAvatarBecomePlayer
        g_playerEvents.onAvatarBecomeNonPlayer += self._onAvatarBecomeNonPlayer
        g_playerEvents.onAccountBecomeNonPlayer += self._onAccountBecomeNonPlayer
        g_playerEvents.onDisconnected += self._onDisconnected
        logger.debug('[Watch] Initialized v%s', __version__)

    def fini(self):
        if self._eventsBound:
            self._eventsBound = False
            g_playerEvents.onAccountShowGUI -= self._onAccountShowGUI
            g_playerEvents.onAvatarBecomePlayer -= self._onAvatarBecomePlayer
            g_playerEvents.onAvatarBecomeNonPlayer -= self._onAvatarBecomeNonPlayer
            g_playerEvents.onAccountBecomeNonPlayer -= self._onAccountBecomeNonPlayer
            g_playerEvents.onDisconnected -= self._onDisconnected
        _restoreHooks()
        _removeScreenResolutionWatcher()
        self._garageClock.fini()
        self._battleClock.fini()
        g_config.fini()
        logger.debug('[Watch] Finalized')

    def onBattlePageReady(self):
        self._garageClock.disable()
        self._battleClock.onBattlePageReady()

    def onBattlePageDisposed(self):
        self._battleClock.onBattlePageDisposed()

    def _onAccountShowGUI(self, ctx):
        self._battleClock.onBattlePageDisposed()
        self._garageClock.bind()

    def _onAvatarBecomePlayer(self):
        self._garageClock.disable()

    def _onAvatarBecomeNonPlayer(self):
        self._battleClock.onBattlePageDisposed()

    def _onAccountBecomeNonPlayer(self):
        self._battleClock.onBattlePageDisposed()

    def _onDisconnected(self):
        self._garageClock.disable()
        self._battleClock.onBattlePageDisposed()


_g_WatchMod = _WatchMod()


def init():
    try:
        _g_WatchMod.init()
    except Exception:
        logger.exception('[Watch] Failed to initialize')


def fini():
    try:
        _g_WatchMod.fini()
    except Exception:
        logger.exception('[Watch] Failed to finalize')

