package com.watch
{
    import flash.events.Event;
    import net.wg.gui.battle.components.BattleUIDisplayable;
    import net.wg.gui.battle.views.BaseBattlePage;

    public class WatchBattleDisplayable extends BattleUIDisplayable
    {
        public var battlePage:BaseBattlePage;
        public var componentName:String;

        public function WatchBattleDisplayable()
        {
            super();
        }

        public function initBattle():void
        {
            if (!this.battlePage) return;
            if (!this.battlePage.contains(this))
            {
                this.battlePage.addChild(this);
            }
            if (!this.battlePage.isFlashComponentRegisteredS(this.componentName))
            {
                this.battlePage.registerFlashComponentS(this, this.componentName);
            }
        }

        public function finiBattle():void
        {
            if (this.battlePage && this.componentName)
            {
                try
                {
                    if (this.battlePage.isFlashComponentRegisteredS(this.componentName))
                    {
                        this.battlePage.unregisterFlashComponentS(this.componentName);
                    }
                }
                catch (e:Error) {}
                try
                {
                    if (this.battlePage.contains(this))
                    {
                        this.battlePage.removeChild(this);
                    }
                }
                catch (e:Error) {}
            }
        }

        override protected function onPopulate():void
        {
            super.onPopulate();
            if (this.battlePage)
            {
                this.battlePage.addEventListener(Event.RESIZE, _handleResize);
            }
        }

        override protected function onDispose():void
        {
            if (this.battlePage)
            {
                this.battlePage.removeEventListener(Event.RESIZE, _handleResize);
            }
            this.finiBattle();
            this.battlePage = null;
            this.componentName = null;
            super.onDispose();
        }

        private function _handleResize(e:Event):void
        {
            this.onResized();
        }

        protected function onResized():void
        {
        }
    }
}
