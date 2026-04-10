package com.watch
{
    import flash.display.MovieClip;
    import flash.events.Event;
    import net.wg.infrastructure.base.AbstractView;
    import net.wg.infrastructure.events.LoaderEvent;
    import net.wg.infrastructure.managers.impl.ContainerManagerBase;

    public class WatchGarageInjector extends AbstractView
    {
        private var _panel:WatchGarageClock = null;

        public var py_onDragEnd:Function = null;
        public var py_onPanelReady:Function = null;

        private var _configDone:Boolean = false;
        private var _pendingCalls:Array = [];
        private var _notifyFrameCount:int = 0;

        public function WatchGarageInjector()
        {
            super();
        }

        override protected function configUI():void
        {
            super.configUI();

            _createPanel();
            _configDone = true;
            _replayPendingCalls();

            var cm:ContainerManagerBase = App.containerMgr as ContainerManagerBase;
            if (cm && cm.loader)
            {
                cm.loader.addEventListener(LoaderEvent.VIEW_LOADED, _onViewLoaded);
            }

            if (App.instance && App.instance.stage)
            {
                App.instance.stage.addEventListener(Event.RESIZE, _onResize);
            }

            _notifyFrameCount = 0;
            addEventListener(Event.ENTER_FRAME, _onNotifyFrame);
        }

        private function _onNotifyFrame(event:Event):void
        {
            _notifyFrameCount++;
            if (_notifyFrameCount < 3) return;
            removeEventListener(Event.ENTER_FRAME, _onNotifyFrame);
            if (py_onPanelReady != null)
            {
                py_onPanelReady();
            }
        }

        override protected function nextFrameAfterPopulateHandler():void
        {
            super.nextFrameAfterPopulateHandler();
            if (parent != App.instance)
            {
                (App.instance as MovieClip).addChild(this);
            }
        }

        override protected function onDispose():void
        {
            removeEventListener(Event.ENTER_FRAME, _onNotifyFrame);
            var cm:ContainerManagerBase = App.containerMgr as ContainerManagerBase;
            if (cm && cm.loader)
            {
                cm.loader.removeEventListener(LoaderEvent.VIEW_LOADED, _onViewLoaded);
            }
            if (App.instance && App.instance.stage)
            {
                App.instance.stage.removeEventListener(Event.RESIZE, _onResize);
            }
            _destroyPanel();
            _pendingCalls = [];
            py_onDragEnd = null;
            py_onPanelReady = null;
            _configDone = false;
            super.onDispose();
        }

        private function _onResize(event:Event):void
        {
            if (_panel)
            {
                _panel.updatePosition();
            }
        }

        private function _onViewLoaded(event:LoaderEvent):void
        {
            if (_panel)
            {
                _panel.updatePosition();
            }
        }

        private function _createPanel():void
        {
            if (_panel) return;
            _panel = new WatchGarageClock();
            _panel.addEventListener(WatchPanelEvent.OFFSET_CHANGED, _onOffsetChanged);
            (App.instance as MovieClip).addChild(_panel);
        }

        private function _destroyPanel():void
        {
            if (_panel)
            {
                _panel.removeEventListener(WatchPanelEvent.OFFSET_CHANGED, _onOffsetChanged);
                _panel.dispose();
                if (_panel.parent)
                {
                    _panel.parent.removeChild(_panel);
                }
                _panel = null;
            }
        }

        private function _replayPendingCalls():void
        {
            if (_pendingCalls.length == 0) return;
            var calls:Array = _pendingCalls;
            _pendingCalls = [];
            for (var i:int = 0; i < calls.length; i++)
            {
                var call:Object = calls[i];
                var fn:Function = call.fn as Function;
                if (fn != null)
                {
                    fn.apply(null, call.args);
                }
            }
        }

        private function _onOffsetChanged(event:WatchPanelEvent):void
        {
            if (py_onDragEnd != null)
                py_onDragEnd(event.data);
        }

        public function as_setSettings(settings:Object):void
        {
            if (!_configDone)
            {
                _pendingCalls.push({fn: this.as_setSettings, args: [settings]});
                return;
            }
            if (_panel)
            {
                if (settings.hasOwnProperty("offset"))
                    _panel.setPositionOffset(settings.offset as Array);
                if (settings.hasOwnProperty("color"))
                    _panel.setTimeColor(uint(settings.color));
            }
        }

        public function as_updateTime(timeStr:String, dateStr:String):void
        {
            if (!_configDone)
            {
                _pendingCalls.push({fn: this.as_updateTime, args: [timeStr, dateStr]});
                return;
            }
            if (_panel)
            {
                _panel.setTimeData(timeStr, dateStr);
            }
        }

        public function as_setVisible(value:Boolean):void
        {
            if (!_configDone)
            {
                _pendingCalls.push({fn: this.as_setVisible, args: [value]});
                return;
            }
            if (_panel)
            {
                _panel.setVisibleState(value);
            }
        }

        public function as_setPosition(offset:Array):void
        {
            if (!_configDone)
            {
                _pendingCalls.push({fn: this.as_setPosition, args: [offset]});
                return;
            }
            if (_panel)
            {
                _panel.setPositionOffset(offset);
            }
        }

        public function as_setColor(color:uint):void
        {
            if (!_configDone)
            {
                _pendingCalls.push({fn: this.as_setColor, args: [color]});
                return;
            }
            if (_panel)
            {
                _panel.setTimeColor(color);
            }
        }
    }
}
