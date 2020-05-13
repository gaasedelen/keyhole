import wx
import time

app = wx.App(False)
s = wx.ScreenDC()
s.Pen = wx.Pen("#FF0000")

start = time.time()
while time.time() - start < 5.0:
    s.DrawRectangle(60,60,200,2000)
print "EXITING"