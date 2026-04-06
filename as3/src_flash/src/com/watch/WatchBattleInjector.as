package com.watch
{
    import flash.events.Event;
    import net.wg.data.constants.generated.LAYER_NAMES;
    import net.wg.gui.battle.views.BaseBattlePage;
    import net.wg.gui.components.containers.MainViewContainer;
    import net.wg.infrastructure.base.AbstractView;

    public class WatchBattleInjector extends AbstractView
    {
        private static const COMPONENT_NAME:String = "WatchBattleClockMain";
        private static const MAX_RETRIES:int = 60;

        private static var _activeComponent:WatchBattleClock = null;

        public var py_onDragEnd:Function = null;

        private var _retryCount:int = 0;

        public function WatchBattleInjector()
        {
            super();
        }

        override protected function onPopulate():void
        {
            super.onPopulate();
            _retryCount = 0;
            _tryAttach();
        }

        private function _tryAttach():void
        {
            if (_activeComponent != null) return;

            var mainViewContainer:MainViewContainer = MainViewContainer(
                App.containerMgr.getContainer(
                    LAYER_NAMES.LAYER_ORDER.indexOf(LAYER_NAMES.VIEWS)
                )
            );

            var page:BaseBattlePage = null;
            for (var i:int = 0; i < mainViewContainer.numChildren; i++)
            {
                page = mainViewContainer.getChildAt(i) as BaseBattlePage;
                if (page) break;
            }

            if (!page)
            {
                _retryCount++;
                if (_retryCount < MAX_RETRIES)
                {
                    addEventListener(Event.ENTER_FRAME, _onRetryFrame);
                }
                return;
            }

            removeEventListener(Event.ENTER_FRAME, _onRetryFrame);

            var comp:WatchBattleClock = new WatchBattleClock();
            comp.componentName = COMPONENT_NAME;
            comp.battlePage = page;
            comp.initBattle();
            comp.addEventListener(WatchPanelEvent.OFFSET_CHANGED, _onOffsetChanged);
            _activeComponent = comp;

            mainViewContainer.setFocusedView(mainViewContainer.getTopmostView());
        }

        private function _onRetryFrame(e:Event):void
        {
            removeEventListener(Event.ENTER_FRAME, _onRetryFrame);
            _tryAttach();
        }

        override protected function onDispose():void
        {
            removeEventListener(Event.ENTER_FRAME, _onRetryFrame);
            _destroyComponent();
            py_onDragEnd = null;
            super.onDispose();
        }

        private function _destroyComponent():void
        {
            if (_activeComponent)
            {
                _activeComponent.removeEventListener(WatchPanelEvent.OFFSET_CHANGED, _onOffsetChanged);
                _activeComponent.cleanup();
                _activeComponent = null;
            }
        }

        private function _onOffsetChanged(event:WatchPanelEvent):void
        {
            if (py_onDragEnd != null)
            {
                py_onDragEnd(event.data);
            }
        }
    }
}
