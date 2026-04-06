package com.watch
{
    import flash.display.Sprite;
    import flash.display.Shape;
    import flash.display.GradientType;
    import flash.display.SpreadMethod;
    import flash.display.Graphics;
    import flash.text.TextField;
    import flash.text.TextFieldAutoSize;
    import flash.filters.DropShadowFilter;
    import flash.filters.GlowFilter;
    import flash.geom.Matrix;
    import flash.geom.Point;
    import flash.events.MouseEvent;
    import flash.utils.clearTimeout;
    import flash.utils.setTimeout;
    import net.wg.data.constants.Cursors;

    public class WatchBattleClock extends WatchBattleDisplayable
    {
        private static const PANEL_WIDTH:int = 160;
        private static const PANEL_HEIGHT:int = 38;
        private static const PAD_H:int = 10;
        private static const PAD_V:int = 8;

        private static const FONT_FACE:String = "$FieldFont";
        private static const FONT_SIZE_TIME:int = 24;

        private static const BG_COLOR_TOP:uint = 0x1e1e1e;
        private static const BG_COLOR_BOT:uint = 0x111111;
        private static const BG_ALPHA_TOP:Number = 0.67;
        private static const BG_ALPHA_BOT:Number = 0.73;

        private static const BOUNDARY_GAP:int = 5;
        private static const DRAG_DELAY:int = 150;
        private static const DRAG_THRESHOLD:int = 20;

        private var _background:Shape;
        private var _dragHit:Sprite;
        private var _timeField:TextField;
        private var _textShadow:DropShadowFilter;
        private var _matrix:Matrix;
        private var _clickPoint:Point;
        private var _clickOffset:Point;
        private var _reusablePoint:Point;

        private var _scaleFactor:Number = 1.0;
        private var _panelWidth:int = PANEL_WIDTH;
        private var _panelHeight:int = PANEL_HEIGHT;
        private var _timeColor:uint = 0xFFFFFF;

        private var _offset:Array = [0, 0];
        private var _isDragging:Boolean = false;
        private var _isDragTest:Boolean = false;
        private var _dragTimeout:uint = 0;
        private var _initialized:Boolean = false;
        private var _disposed:Boolean = false;
        private var _cleanedUp:Boolean = false;

        public function WatchBattleClock()
        {
            super();
            mouseEnabled = false;
            mouseChildren = true;
            _clickPoint = new Point();
            _clickOffset = new Point();
            _reusablePoint = new Point();
            _matrix = new Matrix();
            _textShadow = new DropShadowFilter(1, 45, 0x000000, 0.8, 2, 2, 1.2, 1);
        }

        override protected function onPopulate():void
        {
            super.onPopulate();
            _background = new Shape();
            _background.filters = [new GlowFilter(0x000000, 0.4, 6, 6, 1, 1)];
            addChild(_background);

            _timeField = _mkTf();
            addChild(_timeField);

            _createDragHit();
            _initialized = true;
            visible = false;
            _drawBackground();
            _setupDragListeners();
        }

        override protected function onDispose():void
        {
            if (_disposed) return;
            _disposed = true;
            _performFullCleanup();
            _killTf(_timeField); _timeField = null;
            if (_background) { _background.graphics.clear(); if (contains(_background)) removeChild(_background); _background = null; }
            if (_dragHit) { _dragHit.graphics.clear(); if (contains(_dragHit)) removeChild(_dragHit); _dragHit = null; }
            _textShadow = null;
            _matrix = null;
            _clickPoint = null;
            _clickOffset = null;
            _reusablePoint = null;
            super.onDispose();
        }

        public function cleanup():void
        {
            if (_cleanedUp) return;
            _performFullCleanup();
        }

        private function _performFullCleanup():void
        {
            if (_cleanedUp) return;
            _cleanedUp = true;
            _teardownDragListeners();
            _clearDragTimeout();
            _resetCursor();
            _isDragging = false;
            _isDragTest = false;
            finiBattle();
            if (parent) parent.removeChild(this);
            battlePage = null;
            componentName = null;
        }

        override protected function onResized():void
        {
            if (_disposed || _isDragging) return;
            _syncPosition();
        }

        public function as_updateTime(timeStr:String):void
        {
            if (!_initialized || _disposed) return;
            _timeField.htmlText = _fmt(timeStr, _s(FONT_SIZE_TIME), _timeColor);
            _timeField.x = int((_panelWidth - _timeField.textWidth - 4) / 2);
            _timeField.y = int((_panelHeight - _timeField.textHeight) / 2) - 1;
        }

        public function as_setVisible(isVisible:Boolean):void
        {
            if (_disposed) return;
            this.visible = isVisible;
        }

        public function as_setPosition(offset:Array):void
        {
            if (!_initialized || _disposed) return;
            if (offset && offset.length >= 2)
            {
                _offset[0] = int(offset[0]);
                _offset[1] = int(offset[1]);
            }
            _syncPosition();
        }

        public function as_setScale(factor:Number):void
        {
            if (!_initialized || _disposed) return;
            _scaleFactor = factor;
            _panelWidth = int(PANEL_WIDTH * _scaleFactor);
            _panelHeight = int(PANEL_HEIGHT * _scaleFactor);
            _drawBackground();
            _redrawDragHit();
            _syncPosition();
        }

        public function as_setColor(color:uint):void
        {
            if (_disposed) return;
            _timeColor = color;
        }

        private function _drawBackground():void
        {
            if (!_background || _disposed) return;
            var g:Graphics = _background.graphics;
            g.clear();
            _matrix.identity();
            _matrix.createGradientBox(_panelWidth, _panelHeight, Math.PI / 2, 0, 0);
            g.beginGradientFill(GradientType.LINEAR,
                [BG_COLOR_TOP, BG_COLOR_BOT],
                [BG_ALPHA_TOP, BG_ALPHA_BOT],
                [0, 255], _matrix, SpreadMethod.PAD);
            g.drawRect(0, 0, _panelWidth, _panelHeight);
            g.endFill();
        }

        private function _s(val:int):int
        {
            return int(val * _scaleFactor);
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
            _dragHit.graphics.drawRect(0, 0, _panelWidth, _panelHeight);
            _dragHit.graphics.endFill();
        }

        private function _setupDragListeners():void
        {
            if (!_dragHit) return;
            _dragHit.addEventListener(MouseEvent.MOUSE_DOWN, _onDragMouseDown);
            _dragHit.addEventListener(MouseEvent.MOUSE_OVER, _onDragMouseOver);
            _dragHit.addEventListener(MouseEvent.MOUSE_OUT, _onDragMouseOut);
        }

        private function _teardownDragListeners():void
        {
            if (_dragHit)
            {
                _dragHit.removeEventListener(MouseEvent.MOUSE_DOWN, _onDragMouseDown);
                _dragHit.removeEventListener(MouseEvent.MOUSE_OVER, _onDragMouseOver);
                _dragHit.removeEventListener(MouseEvent.MOUSE_OUT, _onDragMouseOut);
            }
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

        private function _resetCursor():void
        {
            try { App.cursor.forceSetCursor(Cursors.ARROW); } catch (e:Error) {}
        }

        private function _onDragMouseDown(e:MouseEvent):void
        {
            if (_disposed || _cleanedUp || !stage) return;
            _clickPoint.x = stage.mouseX;
            _clickPoint.y = stage.mouseY;
            _clickOffset.x = x - _clickPoint.x;
            _clickOffset.y = y - _clickPoint.y;
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
            App.cursor.forceSetCursor(Cursors.MOVE);
        }

        private function _onDragMouseMove(e:MouseEvent):void
        {
            if (_disposed || _cleanedUp || !stage) return;
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
                x = _reusablePoint.x;
                y = _reusablePoint.y;
            }
        }

        private function _onDragMouseUp(e:MouseEvent):void
        {
            _clearDragTimeout();
            if (_isDragging)
            {
                _getAnchor();
                _offset[0] = int(x - _reusablePoint.x);
                _offset[1] = int(y - _reusablePoint.y);
                _syncPosition();
                App.cursor.forceSetCursor(Cursors.DRAG_OPEN);
                dispatchEvent(new WatchPanelEvent(WatchPanelEvent.OFFSET_CHANGED, _offset));
            }
            _isDragTest = false;
            _isDragging = false;
            _removeStageListeners();
        }

        private function _onDragMouseOver(e:MouseEvent):void
        {
            if (_disposed || _cleanedUp) return;
            App.cursor.forceSetCursor(Cursors.DRAG_OPEN);
        }

        private function _onDragMouseOut(e:MouseEvent):void
        {
            if (_disposed || _cleanedUp) return;
            if (!_isDragging) App.cursor.forceSetCursor(Cursors.ARROW);
        }

        private function _getAnchor():void
        {
            _reusablePoint.x = int(App.appWidth * 0.5 - _panelWidth * 0.5);
            _reusablePoint.y = BOUNDARY_GAP;
        }

        private function _clampToScreen(px:Number, py:Number):void
        {
            _reusablePoint.x = int(Math.max(BOUNDARY_GAP, Math.min(App.appWidth - _panelWidth - BOUNDARY_GAP, px)));
            _reusablePoint.y = int(Math.max(BOUNDARY_GAP, Math.min(App.appHeight - _panelHeight - BOUNDARY_GAP, py)));
        }

        private function _syncPosition():void
        {
            if (_isDragging || _disposed) return;
            _getAnchor();
            _clampToScreen(_reusablePoint.x + _offset[0], _reusablePoint.y + _offset[1]);
            x = _reusablePoint.x;
            y = _reusablePoint.y;
        }
    }
}
