package com.watch
{
    import flash.display.Sprite;
    import flash.text.TextField;
    import flash.text.TextFieldAutoSize;
    import flash.filters.DropShadowFilter;
    import flash.geom.Point;
    import flash.events.MouseEvent;
    import flash.utils.clearTimeout;
    import flash.utils.setTimeout;

    public class WatchGarageClock extends Sprite
    {
        private static const PANEL_WIDTH:int = 220;
        private static const PAD_V:int = 8;

        private static const FONT_FACE:String = "$FieldFont";
        private static const FONT_SIZE_TIME:int = 28;
        private static const FONT_SIZE_DATE:int = 14;

        private static const COLOR_DATE:uint = 0x8899AA;

        private static const BOUNDARY_GAP:int = 10;
        private static const DRAG_DELAY:int = 150;
        private static const DRAG_THRESHOLD:int = 20;

        private var _dragHit:Sprite;
        private var _timeField:TextField;
        private var _dateField:TextField;

        private var _textShadow:DropShadowFilter;
        private var _clickPoint:Point;
        private var _clickOffset:Point;
        private var _reusablePoint:Point;

        private var _panelHeight:int = 58;
        private var _isVisible:Boolean = true;
        private var _disposed:Boolean = false;
        private var _timeColor:uint = 0xFFFFFF;

        private var _isDragging:Boolean = false;
        private var _isDragTest:Boolean = false;
        private var _dragTimeout:uint = 0;
        private var _offset:Array = [0, 0];

        public function WatchGarageClock()
        {
            super();
            mouseEnabled = false;
            mouseChildren = true;
            _clickPoint = new Point();
            _clickOffset = new Point();
            _reusablePoint = new Point();
            _textShadow = new DropShadowFilter(1, 45, 0x000000, 0.8, 2, 2, 1.2, 1);

            _timeField = _mkTf();
            _dateField = _mkTf();
            addChild(_timeField);
            addChild(_dateField);

            _createDragHit();
            _setupDragListeners();
        }

        public function dispose():void
        {
            if (_disposed) return;
            _disposed = true;
            _teardownDragListeners();
            _clearDragTimeout();
            _killTf(_timeField); _timeField = null;
            _killTf(_dateField); _dateField = null;
            if (_dragHit) { _dragHit.graphics.clear(); if (contains(_dragHit)) removeChild(_dragHit); _dragHit = null; }
            _textShadow = null;
            _clickPoint = null;
            _clickOffset = null;
            _reusablePoint = null;
        }

        public function setTimeData(timeStr:String, dateStr:String):void
        {
            if (_disposed) return;

            _timeField.htmlText = _fmt(timeStr, FONT_SIZE_TIME, _timeColor);
            _timeField.x = int(PANEL_WIDTH - _timeField.textWidth - 4);
            _timeField.y = PAD_V - 2;

            _dateField.htmlText = _fmt(dateStr, FONT_SIZE_DATE, COLOR_DATE);
            _dateField.x = int(PANEL_WIDTH - _dateField.textWidth - 4);
            _dateField.y = PAD_V + FONT_SIZE_TIME + 2;

            _panelHeight = PAD_V + FONT_SIZE_TIME + FONT_SIZE_DATE + PAD_V + 6;
            _redrawDragHit();
        }

        public function setVisibleState(value:Boolean):void
        {
            if (_disposed) return;
            _isVisible = value;
            this.visible = value;
        }

        public function updatePosition():void
        {
            if (_disposed) return;
            _syncPosition();
        }

        public function setPositionOffset(offset:Array):void
        {
            if (_disposed) return;
            if (offset && offset.length >= 2)
            {
                _offset[0] = int(offset[0]);
                _offset[1] = int(offset[1]);
            }
            _syncPosition();
        }

        public function setTimeColor(color:uint):void
        {
            if (_disposed) return;
            _timeColor = color;
        }

        private function _mkTf():TextField
        {
            var tf:TextField = new TextField();
            tf.selectable = false;
            tf.mouseEnabled = false;
            tf.autoSize = TextFieldAutoSize.LEFT;
            tf.multiline = false;
            tf.wordWrap = false;
            tf.filters = [_textShadow];
            return tf;
        }

        private function _killTf(tf:TextField):void
        {
            if (tf == null) return;
            tf.filters = [];
            tf.htmlText = "";
            if (contains(tf)) removeChild(tf);
        }

        private function _fmt(text:String, size:int, color:uint):String
        {
            return '<font face="' + FONT_FACE + '" size="' + size + '" color="' + _hex(color) + '"><b>' + text + '</b></font>';
        }

        private static function _hex(color:uint):String
        {
            var h:String = color.toString(16).toUpperCase();
            while (h.length < 6) h = "0" + h;
            return "#" + h;
        }

        private function _createDragHit():void
        {
            _dragHit = new Sprite();
            _dragHit.buttonMode = true;
            _dragHit.useHandCursor = true;
            _redrawDragHit();
            addChild(_dragHit);
        }

        private function _redrawDragHit():void
        {
            if (!_dragHit) return;
            _dragHit.graphics.clear();
            _dragHit.graphics.beginFill(0x000000, 0.0);
            _dragHit.graphics.drawRect(0, 0, PANEL_WIDTH, _panelHeight);
            _dragHit.graphics.endFill();
        }

        private function _setupDragListeners():void
        {
            if (!_dragHit) return;
            _dragHit.addEventListener(MouseEvent.MOUSE_DOWN, _onDragMouseDown);
        }

        private function _teardownDragListeners():void
        {
            if (_dragHit) _dragHit.removeEventListener(MouseEvent.MOUSE_DOWN, _onDragMouseDown);
            _removeStageListeners();
        }

        private function _addStageListeners():void
        {
            if (stage)
            {
                stage.addEventListener(MouseEvent.MOUSE_UP, _onDragMouseUp);
                stage.addEventListener(MouseEvent.MOUSE_MOVE, _onDragMouseMove);
            }
        }

        private function _removeStageListeners():void
        {
            if (stage)
            {
                stage.removeEventListener(MouseEvent.MOUSE_UP, _onDragMouseUp);
                stage.removeEventListener(MouseEvent.MOUSE_MOVE, _onDragMouseMove);
            }
        }

        private function _clearDragTimeout():void
        {
            if (_dragTimeout != 0) { clearTimeout(_dragTimeout); _dragTimeout = 0; }
        }

        private function _onDragMouseDown(e:MouseEvent):void
        {
            if (_disposed || !stage) return;
            _clickPoint.x = stage.mouseX;
            _clickPoint.y = stage.mouseY;
            _clickOffset.x = this.x - _clickPoint.x;
            _clickOffset.y = this.y - _clickPoint.y;
            _isDragTest = true;
            _clearDragTimeout();
            _dragTimeout = setTimeout(_beginDrag, DRAG_DELAY);
            _addStageListeners();
        }

        private function _beginDrag():void
        {
            _isDragTest = false;
            _isDragging = true;
            _dragTimeout = 0;
        }

        private function _onDragMouseMove(e:MouseEvent):void
        {
            if (_disposed || !stage) return;
            if (!_isDragging && _isDragTest)
            {
                var dx:Number = stage.mouseX - _clickPoint.x;
                var dy:Number = stage.mouseY - _clickPoint.y;
                if (dx * dx + dy * dy > DRAG_THRESHOLD * DRAG_THRESHOLD)
                {
                    _clearDragTimeout();
                    _beginDrag();
                    return;
                }
            }
            if (_isDragging)
            {
                _clampToScreen(_clickOffset.x + stage.mouseX, _clickOffset.y + stage.mouseY);
                this.x = _reusablePoint.x;
                this.y = _reusablePoint.y;
            }
        }

        private function _onDragMouseUp(e:MouseEvent):void
        {
            _clearDragTimeout();
            if (_isDragging)
            {
                _offset[0] = int(this.x);
                _offset[1] = int(this.y);
                dispatchEvent(new WatchPanelEvent(WatchPanelEvent.OFFSET_CHANGED, _offset));
            }
            _isDragTest = false;
            _isDragging = false;
            _removeStageListeners();
        }

        private function _clampToScreen(px:Number, py:Number):void
        {
            var sw:int = App.appWidth > 0 ? App.appWidth : 1920;
            var sh:int = App.appHeight > 0 ? App.appHeight : 1080;
            _reusablePoint.x = int(Math.max(BOUNDARY_GAP, Math.min(sw - PANEL_WIDTH - BOUNDARY_GAP, px)));
            _reusablePoint.y = int(Math.max(BOUNDARY_GAP, Math.min(sh - _panelHeight - BOUNDARY_GAP, py)));
        }

        private function _syncPosition():void
        {
            if (_isDragging || _disposed) return;
            _clampToScreen(_offset[0], _offset[1]);
            this.x = _reusablePoint.x;
            this.y = _reusablePoint.y;
        }
    }
}
