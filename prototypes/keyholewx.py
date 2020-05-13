import os
import sys
import time
import math

# deps
import wx
import cv2
import numpy as np
import tobii_research as tr
from pynput import keyboard, mouse

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

#------------------------------------------------------------------------------
# Keyhole
#------------------------------------------------------------------------------

class Keyhole(object):

    def __init__(self):
        super(Keyhole, self).__init__()
        self.qt_rects = []
        self._awaiting_choice = False
        self.win = wx.Frame(None, wx.ID_ANY, "Overlay", style=wx.BORDER_NONE|wx.STAY_ON_TOP|wx.TRANSPARENT_WINDOW)
        self.win.SetTransparent(100)
        self.overlay = wx.Panel(self.win, -1, style=wx.TRANSPARENT_WINDOW)
        #self.overlay.SetTransparent(100)
        self.overlay.SetBackgroundColour('red')

        # grab screen res
        self.width, self.height = wx.GetDisplaySize()

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

    def run(self):
        while true:
            time.sleep(.1)

    def show_targets(self):
        self.do_cv()
        self.draw_cv()

    def draw_cv(self):
        self.win.ShowFullScreen(True)

        self.overlay.Pen = wx.Pen("#FF0000")
        for i, rect in enumerate(self.qt_rects):

            ## draw the cv rect
            #qp.setPen(op)
            #qp.setBrush(ob)
            #qp.drawRect(rect)

            ## compute letterbox rect
            #letter_rect = fm.boundingRect(chr(0x41+i))
            #letter_rect.moveCenter(rect.center())

            ## compute letterbox rect
            #letter_box_rect = letter_rect.marginsAdded(QMargins(4,2,4,2))

            ## draw letterbox
            #qp.setPen(letter_box_pen)
            #qp.setBrush(letter_box_brush)
            #qp.drawRect(letter_box_rect)

            ## draw letter 
            #qp.setPen(Qt.white)
            #qp.drawText(letter_rect, 0, chr(0x41+i))

            self.overlay.DrawRectangle(rect.x, rect.y, rect.width, rect.height)

    def _on_press(self, key):
        print "pressed", key

        if key == keyboard.Key.f20:
            try:
                self.show_targets()
            except Exception as e:
                print e
        elif key == keyboard.Key.esc:
            self.clear_cv()

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

        GAZE_WIDTH, GAZE_HEIGHT = (250, 250)
        rect = wx.Rect(0,0,GAZE_WIDTH, GAZE_HEIGHT)

        # center the gaze rect around the eye position
        rect.SetX(eye_x - GAZE_WIDTH/2)
        rect.SetY(eye_y - GAZE_HEIGHT/2)

        # bound the rect to the screen
        if rect.Left < 0:
            rect.Left = 0
        if rect.Top < 0:
            rect.Top = 0
        if rect.Right > self.width:
            rect.Right = self.width
        if rect.Bottom > self.height:
            rect.Bottom = self.height

        return rect

    @property
    def gaze_image(self):
        print 'Taking screenshot...'
        rect = self.gaze_rect

        #Create a DC for the whole screen area
        dcScreen = wx.ScreenDC()

        #Create a Bitmap that will hold the screenshot image later on
        #Note that the Bitmap must have a size big enough to hold the screenshot
        #-1 means using the current default colour depth
        bmp = wx.Bitmap(rect.width, rect.height)

        #Create a memory DC that will be used for actually taking the screenshot
        memDC = wx.MemoryDC()

        #Tell the memory DC to use our Bitmap
        #all drawing action on the memory DC will go to the Bitmap now
        memDC.SelectObject(bmp)

        #Blit (in this case copy) the actual screen on the memory DC
        #and thus the Bitmap
        memDC.Blit( 0, #Copy to this X coordinate
                    0, #Copy to this Y coordinate
                    rect.width, #Copy this width
                    rect.height, #Copy this height
                    dcScreen, #From where do we copy?
                    rect.x, #What's the X offset in the original DC?
                    rect.y  #What's the Y offset in the original DC?
                    )

        #Select the Bitmap out of the memory DC by selecting a new
        #uninitialized Bitmap
        memDC.SelectObject(wx.NullBitmap)

        img = bmp.ConvertToImage()
        return (rect, img)
        
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
        dir_path = os.path.dirname(os.path.realpath(__file__))
        img_path = os.path.join(dir_path, "grab.png")
        
        rect, img = self.gaze_image
        img.SaveFile(img_path, wx.BITMAP_TYPE_PNG)

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
            qt_rects.append(wx.Rect(rect.x + x, rect.y + y, x2, y2)) 

        #cv2.imshow('FEATURES', image)

        self.qt_rects = qt_rects
        self._awaiting_choice = True
        #self.updated.emit()

    def clear_cv(self):
        print "hiding..."
        self.qt_rects = []
        self._awaiting_choice = False
        self.win.Show(False)
        #self.updated.emit()

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

def main(argc, argv):
    app = wx.App(False)
    k = Keyhole()
    app.MainLoop()

if __name__ == "__main__":
    main(len(sys.argv), sys.argv)
