package com.watch
{
    import flash.events.Event;

    public class WatchPanelEvent extends Event
    {
        public static const OFFSET_CHANGED:String = "WatchPanelEvent.OFFSET_CHANGED";

        private var _data:* = null;

        public function WatchPanelEvent(type:String, data:* = null, bubbles:Boolean = true, cancelable:Boolean = false)
        {
            super(type, bubbles, cancelable);
            _data = data;
        }

        override public function clone():Event
        {
            return new WatchPanelEvent(type, _data, bubbles, cancelable);
        }

        public function get data():*
        {
            return _data;
        }
    }
}
