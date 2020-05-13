import os
import sys
import time
import math

import cv2
import numpy as np
import tobii_research as tr
from pynput import keyboard, mouse

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

class Keyhole(QObject):
    updated = pyqtSignal()
    strike = pyqtSignal()
    escape = pyqtSignal()

    def __init__(self, parent):
        super(Keyhole, self).__init__(parent)
        self.qt_rects = []
        self._awaiting_choice = False

        # grab screen res
        self.width, self.height = get_screen_size()

        # eye position
        self._eye_x = 0
        self._eye_y = 0

        # setup tracker
        self.t = tr.find_all_eyetrackers()[0]
        self.t.subscribe_to(tr.EYETRACKER_GAZE_DATA, self.gaze_data_callback)

        # listen for keyboard events
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release)
        self.listener.start()
        self.mouse = mouse.Controller()

        self.strike.connect(self.show_overlay)
        self.escape.connect(self.clear_cv)

    def show_overlay(self):
        
        self.overlay = KeyholeView(self.parent(), self)
        self.overlay.showFullScreen()
        self.do_cv()

    def _on_press(self, key):
        print "pressed", key

        if key == keyboard.Key.f20:
            self.strike.emit()
        elif key == keyboard.Key.esc:
            self.escape.emit()

        if not self._awaiting_choice:
            return

        try:
            selection = key.char
        except AttributeError:
            return

        index = ord(selection) - 0x61

        if 0 <= index < len(self.qt_rects):
            print "WHOOP", key
            pos = self.qt_rects[index].center()
            self.clear_cv()
            self.mouse.position = (pos.x(), pos.y())
            self.mouse.click(mouse.Button.left)

    def _on_release(self, key):
        #print "released", key
        pass

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
        self._awaiting_choice = True
        self.updated.emit()

    def clear_cv(self):
        print "hiding..."
        self.qt_rects = []
        self._awaiting_choice = False
        self.updated.emit()

class KeyholeView(QWidget):

    def __init__(self, parent, controller):
        super(KeyholeView, self).__init__(parent)

        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        #self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        #self.setFocusPolicy(Qt.NoFocus)

        self.controller = controller
        #self.controller.updated.connect(self.update)

        self.timer = QTimer()
        self.timer.timeout.connect(self.repaint)
        self.timer.start(100)

    def paintEvent(self, event=None):
        painter = QPainter(self)
        self.drawRectangles(painter)
        self.raise_()
        print self.isWindow()

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
# util 
#------------------------------------------------------------------------------

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

def get_screen_size():
    screen = QApplication.primaryScreen()
    size = screen.size()
    rect = screen.availableGeometry()
    print('Screen: %s' % screen.name())
    print('Size: %d x %d' % (size.width(), size.height()))
    print('Available: %d x %d' % (rect.width(), rect.height()))
    return (size.width(), size.height())


#------------------------------------------------------------------------------
# Main
#------------------------------------------------------------------------------

def main(argc, argv):
    app = QApplication(argv)

    m = QMainWindow()
    k = Keyhole(m)
    app.exec_()

if __name__ == "__main__":
    main(len(sys.argv), sys.argv)
