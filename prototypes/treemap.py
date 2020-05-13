import os
import sys

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from pynput import keyboard

def on_press(key):
    try:
        print('alphanumeric key {0} pressed'.format(
            key.char))
    except AttributeError:
        print('special key {0} pressed'.format(
            key))

def on_release(key):
    print('{0} released'.format(
        key))
    if key == keyboard.Key.esc:
        # Stop listener
        return False

# ...or, in a non-blocking fashion:
listener = keyboarda.Listener(
    on_press=on_press,
    on_release=on_release)
listener.start()

#------------------------------------------------------------------------------
# Treemap
#------------------------------------------------------------------------------

# Squarified Treemap Layout
# Implements algorithm from Bruls, Huizing, van Wijk, "Squarified Treemaps"
#   (but not using their pseudocode)

def normalize_sizes(sizes, dx, dy):
    total_size = sum(sizes)
    total_area = dx * dy
    sizes = map(float, sizes)
    sizes = map(lambda size: size * total_area / total_size, sizes)
    return list(sizes)

def pad_rectangle(rect):
    if rect['dx'] > 2:
        rect['x'] += 1
        rect['dx'] -= 2
    if rect['dy'] > 2:
        rect['y'] += 1
        rect['dy'] -= 2

def layoutrow(sizes, x, y, dx, dy):
    # generate rects for each size in sizes
    # dx >= dy
    # they will fill up height dy, and width will be determined by their area
    # sizes should be pre-normalized wrt dx * dy (i.e., they should be same units)
    covered_area = sum(sizes)
    width = covered_area / dy
    rects = []
    for size in sizes:
        rects.append({'x': x, 'y': y, 'dx': width, 'dy': size / width})
        y += size / width
    return rects

def layoutcol(sizes, x, y, dx, dy):
    # generate rects for each size in sizes
    # dx < dy
    # they will fill up width dx, and height will be determined by their area
    # sizes should be pre-normalized wrt dx * dy (i.e., they should be same units)
    covered_area = sum(sizes)
    height = covered_area / dx
    rects = []
    for size in sizes:
        rects.append({'x': x, 'y': y, 'dx': size / height, 'dy': height})
        x += size / height
    return rects

def layout(sizes, x, y, dx, dy):
    return layoutrow(sizes, x, y, dx, dy) if dx >= dy else layoutcol(sizes, x, y, dx, dy)

def leftoverrow(sizes, x, y, dx, dy):
    # compute remaining area when dx >= dy
    covered_area = sum(sizes)
    width = covered_area / dy
    leftover_x = x + width
    leftover_y = y
    leftover_dx = dx - width
    leftover_dy = dy
    return (leftover_x, leftover_y, leftover_dx, leftover_dy)

def leftovercol(sizes, x, y, dx, dy):
    # compute remaining area when dx >= dy
    covered_area = sum(sizes)
    height = covered_area / dx
    leftover_x = x
    leftover_y = y + height
    leftover_dx = dx
    leftover_dy = dy - height
    return (leftover_x, leftover_y, leftover_dx, leftover_dy)

def leftover(sizes, x, y, dx, dy):
    return leftoverrow(sizes, x, y, dx, dy) if dx >= dy else leftovercol(sizes, x, y, dx, dy)

def worst_ratio(sizes, x, y, dx, dy):
    return max([max(rect['dx'] / rect['dy'], rect['dy'] / rect['dx']) for rect in layout(sizes, x, y, dx, dy)])

def squarify(sizes, x, y, dx, dy):
    # sizes should be pre-normalized wrt dx * dy (i.e., they should be same units)
    # or dx * dy == sum(sizes)
    # sizes should be sorted biggest to smallest
    sizes = list(map(float, sizes))

    if len(sizes) == 0:
        return []

    if len(sizes) == 1:
        return layout(sizes, x, y, dx, dy)

    # figure out where 'split' should be
    i = 1
    while i < len(sizes) and worst_ratio(sizes[:i], x, y, dx, dy) >= worst_ratio(sizes[:(i+1)], x, y, dx, dy):
        i += 1
    current = sizes[:i]
    remaining = sizes[i:]

    (leftover_x, leftover_y, leftover_dx, leftover_dy) = leftover(current, x, y, dx, dy)
    return layout(current, x, y, dx, dy) + \
            squarify(remaining, leftover_x, leftover_y, leftover_dx, leftover_dy)

def padded_squarify(sizes, x, y, dx, dy):
    rects = squarify(sizes, x, y, dx, dy)
    for rect in rects:
        pad_rectangle(rect)
    return rects

#####################################################################

class QTreeMap(QWidget):

    def __init__(self, parent):
        super(QTreeMap, self).__init__(parent)

        self._width  = parent.screen_width
        self._height = parent.screen_height
        self.resize(self._width, self._height)

        # TODO
        self._rectangles = []

    def test_layout(self, values):
        values = normalize_sizes(values, self._width, self._height)
        self._rectangles = squarify(values, 0, 0, self._width, self._height)
        self.parent().rectangles = self._rectangles

    def paintEvent(self, paint_event):
        """
        Draw the treemap.
        """

        painter = QPainter()
        painter.begin(self)
        self.drawRectangles(painter)
        painter.end()

    def drawRectangles(self, qp):

        color = QColor(0xFF, 0xFF, 0xFF)
        #color.setNamedColor('#d4d4d4')
        p = QPen(color)
        p.setWidth(3)
        qp.setPen(p)

        font = qp.font()
        font.setPixelSize(100)
        qp.setFont(font)

        qp.setBrush(QColor(200, 0, 0, 150))
        for i, rect in enumerate(self._rectangles):
            qp.drawRect(rect['x'], rect['y'], rect['dx'], rect['dy'])
            qp.drawText(rect['x']+(rect['dx']/2.5), rect['y']+(rect['dy']/1.7), chr(0x41+i))

#------------------------------------------------------------------------------
# Main Window
#------------------------------------------------------------------------------

import cv2
import numpy as np

def non_max_suppression_slow(boxes, overlapThresh):
    if len(boxes) == 0:
        return []
    pick = []
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    idxs = np.argsort(y2)

    while len(idxs) > 0:
        last = len(idxs) - 1
        i = idxs[last]
        pick.append(i)
        suppress = [last]
        for pos in range(0, last):
            j = idxs[pos]
            xx1 = max(x1[i], x1[j])
            yy1 = max(y1[i], y1[j])
            xx2 = min(x2[i], x2[j])
            yy2 = min(y2[i], y2[j])

            w = max(0, xx2 - xx1 + 1)
            h = max(0, yy2 - yy1 + 1)

            overlap = float(w * h) / area[j]
            if overlap > overlapThresh:
                suppress.append(pos)
        idxs = np.delete(idxs, suppress)
    return boxes[pick]

#------------------------------------------------------------------------------
# util 
#------------------------------------------------------------------------------

def get_screen_size():
    screen = QApplication.primaryScreen()
    size = screen.size()
    rect = screen.availableGeometry()
    print('Screen: %s' % screen.name())
    print('Size: %d x %d' % (size.width(), size.height()))
    print('Available: %d x %d' % (rect.width(), rect.height()))
    return (size.width(), size.height())

#------------------------------------------------------------------------------
# eye tracking version
#------------------------------------------------------------------------------

import time
import math
import tobii_research as tr

class Keyhole(object):

    def __init__(self):

        self.keybinder = WinKeyBinder()
        self.keybinder.init()

        # grab screen res
        self.width, self.height = get_screen_size()

        # eye position
        self._eye_x = 0
        self._eye_y = 0

        # setup tracker
        self.t = tr.find_all_eyetrackers()[0]
        self.t.subscribe_to(tr.EYETRACKER_GAZE_DATA, self.gaze_data_callback)
        
        self.qt_rects = []

    @property
    def eye_position(self):
        return (self._eye_x, self._eye_y)

    @property
    def gaze_rect(self):

        eye_x, eye_y = self.eye_position
        print self.eye_position
        rect = QRect(0,0,250,250)
        rect.moveCenter(QPoint(eye_x, eye_y))

        # bound the rect to the screen
        if rect.left() < 0:
            rect.moveLeft(0)
        if rect.top() < 0:
            rect.moveTop(0)
        if rect.right() > self.width:
            rect.moveRight(self.width)
        if rect.bottom() > self.height:
            rect.moveBottom(self.height)

        return rect
        
    def gaze_data_callback(self, gaze_data):
        lpx, lpy = gaze_data.left_eye.gaze_point.position_on_display_area
        rpx, rpy = gaze_data.right_eye.gaze_point.position_on_display_area

        if math.isnan(lpx) or math.isnan(rpx):
            return

        lx, ly = (lpx*self.width, lpy*self.height)
        rx, ry = (rpx*self.width, rpy*self.height)

        self._eye_x = (lx + rx) / 2.0
        self._eye_y = (ly + ry) / 2.0

    def do_cv(self):

        crop = self.gaze_rect

        #self.hide()
        screen = QApplication.primaryScreen().grabWindow(0)
        #self.show()

        cropped = screen.copy(crop)
        dir_path = os.path.dirname(os.path.realpath(__file__))
        img_path = os.path.join(dir_path, "grab.png")
        cropped.save(img_path, "png")

        # CV
        image = cv2.imread(img_path, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, 10, 17, 17)
        #edged = cv2.Canny(gray, 30, 200)
        edged = cv2.Canny(gray, 80, 200)
        #cv2.imshow('EDGED', edged)

        # dilate / thicken objects
        edged = cv2.dilate(edged, None, iterations=1)
        #cv2.imshow('dilated', edged)

        cnts, hier = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        #
        # Remove lines & big contours
        #

        # loop over the (sorted) contours
        #cnts = sorted(cnts, key = cv2.contourArea, reverse = True)
        rects = []
        good_cnts = []
        for c in cnts:
            (x, y, w, h) = cv2.boundingRect(c)

            aspect_ratio = float(w)/h
            #print aspect_ratio
            if (aspect_ratio > 3 or aspect_ratio < 0.2) and (h < 8 or w < 8):
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 0, 255), 1)
                print "BAD RATIO", aspect_ratio
                continue

            if w*h > 6000:
                #cv2.rectangle(image, (x, y), (x + w, y + h), (255, 0, 0), 1)
                print "BAD SIZE", w, h
                continue

            #cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 1)
            good_cnts.append(c)
            rects.append((x,y,x+w,y+h))

        #cv2.imshow('CONTOURS', image)

        rects = np.array(rects)
        pick = non_max_suppression_slow(rects, 0.3)
        qt_rects = []

        # show selection
        for c in pick:
            (x, y, x2, y2) = c
            cv2.rectangle(image, (x, y), (x2, y2), (0, 255, 0), 1)
            qt_rects.append(QRect(QPoint(crop.left()+x, crop.top()+y), QPoint(crop.left()+x2, crop.top()+y2)))

        #cv2.imshow('FEATURES', image)

        self.qt_rects = qt_rects

class KeyholeView(QMainWindow):
    REGIONS = [0x41+i for i in range(26)]

    def __init__(self, controller):
        super(KeyholeView, self).__init__()

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.controller = controller
        #self.controller.keybinder.

        ## Create the treemap
        #regions = [50 for x in range(26)]
        #self.tm = QTreeMap(self)
        #self.tm.test_layout(regions)

        ## Center the treemap
        #qr = self.tm.frameGeometry()
        #cp = QDesktopWidget().availableGeometry().center()
        #self.tm.move(0,0)

    def magic_key(self):
        print "got magic key"
        self.controller.do_cv()
        self.update()

    def paintEvent(self, event=None):
        painter = QPainter(self)

        #painter.setOpacity(0.5)
        #painter.setBrush(Qt.white)
        #painter.setPen(QPen(Qt.black))

        #painter.begin(self)
        #painter.drawRect(self.rect())
        self.drawRectangles(painter)
        #painter.end()

    def drawRectangles(self, qp):

        # cv rect outline
        op = QPen(QColor(0, 255, 0))
        op.setWidth(1)
        ob = QBrush(QColor(0, 255, 0, 100))

        # letter box border
        letter_box_pen = QPen(QColor(180, 180, 180)) 
        letter_box_pen.setWidth(1)

        # letter box background fill
        letter_box_brush = QBrush(QColor(64, 64, 64)) 

        # letter box text color 
        tp = QPen(Qt.white)
        f = qp.font()
        f.setPixelSize(11)
        qp.setFont(f)
        
        fm = QFontMetrics(f)

        for i, rect in enumerate(self.controller.qt_rects):

            # draw the cv rect
            qp.setPen(op)
            qp.setBrush(ob)
            qp.drawRect(rect)

            # compute letterbox rect
            letter_rect = fm.boundingRect(chr(0x41+i))
            letter_rect.moveCenter(rect.center())

            # compute letterbox rect
            letter_box_rect = letter_rect.marginsAdded(QMargins(4,2,4,2))

            # draw letterbox
            qp.setPen(letter_box_pen)
            qp.setBrush(letter_box_brush)
            qp.drawRect(letter_box_rect)

            # draw letter 
            qp.setPen(Qt.white)
            qp.drawText(letter_rect, 0, chr(0x41+i))

#------------------------------------------------------------------------------
# Main
#------------------------------------------------------------------------------

class WinEventFilter(QAbstractNativeEventFilter):
    def __init__(self, keybinder):
        self.keybinder = keybinder
        super(WinEventFilter, self).__init__()

    def nativeEventFilter(self, eventType, message):
        ret = self.keybinder.handler(eventType, message)
        return ret, 0

def main(argc, argv):
    app = QApplication(argv)

    k = Keyhole()
    kv = KeyholeView(k)

    # k.keybinder.register_hotkey(kv.winId(), "F20", kv.magic_key)

    # # Install a native event filter to receive events from the OS
    # win_event_filter = WinEventFilter(k.keybinder)
    # event_dispatcher = QAbstractEventDispatcher.instance()
    # event_dispatcher.installNativeEventFilter(win_event_filter)

    kv.showFullScreen()
    app.exec_()

    # k.keybinder.unregister_hotkey(kv.winId(), "F20")

if __name__ == "__main__":
    main(len(sys.argv), sys.argv)
