using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Threading;

using Tobii.Research;
using Gma.System.MouseKeyHook;
using OpenCvSharp;
using OpenCvSharp.UserInterface;
using System.Drawing.Imaging;

namespace keyhole
{

    public class ScreenGaze
    {
        // source data
        GazePoint m_GazeData; 

        // on-screen gaze coordinates
        public System.Drawing.Point m_GazeLeft = new System.Drawing.Point(0, 0);
        public System.Drawing.Point m_GazeRight = new System.Drawing.Point(0, 0);
        public System.Drawing.Point m_GazePoint = new System.Drawing.Point(0, 0);

        // on-screen rectangle that approximates user gaze
        public Rectangle m_GazeRect = new Rectangle();

        public ScreenGaze() { }

        public ScreenGaze(ScreenGaze other)
        {
            m_GazeLeft.X = other.m_GazeLeft.X;
            m_GazeLeft.Y = other.m_GazeLeft.Y;
            m_GazeRight.X = other.m_GazeRight.X;
            m_GazeRight.Y = other.m_GazeRight.Y;
            m_GazePoint.X = other.m_GazePoint.X;
            m_GazePoint.Y = other.m_GazePoint.Y;
            m_GazeRect.Location = other.m_GazeRect.Location;
            m_GazeRect.Size = other.m_GazeRect.Size;
        }
    }
    
    public class GazeTarget
    {
        public Rectangle Rect;
        public string Label;
        public int X;
        public int Y;

        public GazeTarget(string label, Rectangle onScreenTarget)
        {
            this.Rect = onScreenTarget;
            this.X = onScreenTarget.X + onScreenTarget.Width / 2;
            this.Y = onScreenTarget.Y + onScreenTarget.Height / 2;
            this.Label = label;
        }

    }

    public class Keyhole
    {
        private IKeyboardMouseEvents m_Events;

        private IEyeTracker m_EyeTracker;
        public Rectangle Screen;
        public ScreenGaze ScreenGaze;
        public ScreenGaze ScreenGazeSnapshot;

        private Bitmap m_LastScreenCrop;
        private Bitmap m_LastScreenCropCV;

        public List<GazeTarget> GazeTargets;

        public Form window;
        private bool m_Active;
        private bool m_Dirty;

        private ThreadStart m_Ts;
        private Thread m_DrawThread;
        public Keys m_overlayKey;

        public Keyhole(Keys overlayKey)
        {
            m_overlayKey = overlayKey;
            m_Ts = new ThreadStart(DrawLoop);
            m_DrawThread = new Thread(m_Ts);

            // setup eye tracker
            m_EyeTracker = EyeTrackingOperations.FindAllEyeTrackers().FirstOrDefault();
            m_EyeTracker.GazeDataReceived += GazeDataReceived;

            // init gaze points
            ScreenGaze = new ScreenGaze();
            GazeTargets = new List<GazeTarget>();

            Screen = System.Windows.Forms.Screen.PrimaryScreen.Bounds;
            window = new Form1(this);
            m_Active = false;

            // keyboard / mouse
            m_Events = Hook.GlobalEvents();
            m_Events.KeyDown += OnKeyDown;
            //m_Events.KeyUp += OnKeyUp;
            //m_Events.KeyPress += HookManager_KeyPress;
            m_Events.MouseMove += OnMouseMove;

            m_DrawThread.Start();
        }

        private void DrawLoop()
        {

            while (true)
            {
                lock (ScreenGaze)
                {
                    if (m_Dirty)
                    {
                        window.Invalidate();
                        m_Dirty = false;
                    }
                }

                // ~30 fps, probably unecesssary
                Thread.Sleep(33);
            }
        }

        private void HookManager_KeyPress(object sender, KeyPressEventArgs e)
        {
            //Console.WriteLine(string.Format("KeyPress \t\t {0}\n", e));
        }

        private void OnKeyDown(object sender, KeyEventArgs e)
        {
            //Console.WriteLine(string.Format("KeyDown  \t\t {0}\n", e.KeyCode));

            // activate keyhole overlay
            if (e.KeyCode == m_overlayKey)
            {
                this.GazeSnapshot();
                goto handled;
            }

            // ignore all keypresses when the overlay is not active
            else if (!m_Active)
                return;

            //----------------------------------------------------------------
            //            KEYHOLE OVERLAY IS ACTIVE AND VISIBLE
            //----------------------------------------------------------------

            //
            // if the keyhole overlay had poor results, the user can hit the delete key
            // to save a copy of the source capture to disk for future improvement
            //

            if (e.KeyCode == Keys.Delete)
            {
                this.SaveHardTestcase();
                this.ClearGazeSnapshot();
                goto handled;
            }

            // cancel keyhole overlay
            else if (e.KeyCode == Keys.Escape)
            {
                this.ClearGazeSnapshot();
                goto handled;
            }

            // i
            if (SelectTarget(e.KeyCode) == false)
                Console.WriteLine(string.Format("Invalid key_target {0}", e.KeyCode));

            this.ClearGazeSnapshot();

        handled:
            e.Handled = true;
        }

        private void OnMouseMove(object sender, MouseEventArgs e)
        {
            if (!m_Active)
                return;
            this.ClearGazeSnapshot();
        }

        public Boolean SelectTarget(Keys key_target)
        {

            // search for an onscreen gaze target matching the keypress
            GazeTarget found = null;
            foreach (var target in GazeTargets)
            {
                if (target.Label.Length > 0 && target.Label[0] == Convert.ToChar(key_target))
                {
                    found = target;
                    break;
                }
            }

            // a corresponding onscreen gaze target was not found
            if (found == null)
            {
                Console.WriteLine(string.Format("No gaze target for {0}", key_target));
                return false;
            }

            // click the target
            Console.WriteLine(string.Format("Clicking target for '{0}'", found.Label));
            DoMouseClick(found.X, found.Y);
            return true;
        }

        //--------------------------------------------------------------------
        // Low Level Functions
        //--------------------------------------------------------------------

        private void GazeDataReceived(object sender, GazeDataEventArgs e)
        {
            lock (ScreenGaze)
            {
                this.UpdateGazePoint(e);
                this.UpdateGazeRect();
            }
        }

        private void UpdateGazePoint(GazeDataEventArgs e)
        {
            double lx, ly, rx, ry;

            // no good data to operate on...
            if (e.RightEye.GazePoint.Validity == Validity.Invalid && e.LeftEye.GazePoint.Validity == Validity.Invalid)
                return;

            if (e.LeftEye.GazePoint.Validity == Validity.Invalid)
            {
                lx = e.RightEye.GazePoint.PositionOnDisplayArea.X * Screen.Width;
                ly = e.RightEye.GazePoint.PositionOnDisplayArea.Y * Screen.Height;
            }
            else
            {
                lx = e.LeftEye.GazePoint.PositionOnDisplayArea.X * Screen.Width;
                ly = e.LeftEye.GazePoint.PositionOnDisplayArea.Y * Screen.Height;
            }

            if (e.RightEye.GazePoint.Validity == Validity.Invalid)
            {
                rx = e.LeftEye.GazePoint.PositionOnDisplayArea.X * Screen.Width;
                ry = e.LeftEye.GazePoint.PositionOnDisplayArea.Y * Screen.Height;
            }
            else
            {
                rx = e.RightEye.GazePoint.PositionOnDisplayArea.X * Screen.Width;
                ry = e.RightEye.GazePoint.PositionOnDisplayArea.Y * Screen.Height;
            }
             
            //
            // prefer right eye for left side of screen, inverse for right side
            //

            if (lx > Screen.Width * 0.65)
            {
                rx = lx;
                ry = ly;
                //Console.WriteLine("USING LEFT EYE");
            }
            else if (rx < Screen.Width * 0.35)
            {
                lx = rx;
                ly = ry;
            }

            // average together the gaze points of both eyes
            var gaze_x = (lx + rx) / 2.0;
            var gaze_y = (ly + ry) / 2.0;

            // smooth the new point, based on the last point
            var alpha = 0.15f;
            var smooth_x = (int)(gaze_x * alpha + ScreenGaze.m_GazePoint.X * (1.0 - alpha));
            var smooth_y = (int)(gaze_y * alpha + ScreenGaze.m_GazePoint.Y * (1.0 - alpha));

            // bound to screen
            var bound_x = Math.Min(Screen.Width, Math.Max(smooth_x, 0));
            var bound_y = Math.Min(Screen.Height, Math.Max(smooth_y, 0));

            // 
            var NewGazePoint = new System.Drawing.Point(bound_x, bound_y);

            // deadzone for less jitter, ignore under 10px changes
            if (GetDistance(NewGazePoint, ScreenGaze.m_GazePoint) < 3.0)
                return;

            ScreenGaze.m_GazePoint = NewGazePoint;
            //m_Dirty = true;
        }

        private void UpdateGazeRect()
        {
            var distance = (int)Math.Sqrt((Math.Pow(Screen.Width / 2 - ScreenGaze.m_GazePoint.X, 2) + Math.Pow(Screen.Height / 2 - ScreenGaze.m_GazePoint.Y, 2)));

            // compute a rect for the current gaze
            int width = 120 + distance / 12;
            int height = 120 + distance / 12;

            Rectangle rect = new Rectangle(0, 0, width, height);
            Rectangle centered_rect = CenterRectangle(rect, ScreenGaze.m_GazePoint);
            Rectangle bounded_rect = BoundRectangle(centered_rect, Screen);

            ScreenGaze.m_GazeRect = bounded_rect;
        }

        private static double GetDistance(System.Drawing.Point p1, System.Drawing.Point p2)
        {
            return Math.Sqrt(Math.Pow((p2.X - p1.X), 2) + Math.Pow((p2.Y - p1.Y), 2));
        }

        //--------------------------------------------------------------------
        // High Level Functions
        //--------------------------------------------------------------------

        private void GazeSnapshot()
        {

            // 
            // make a copy of the current gaze data
            //

            lock (ScreenGaze)
                ScreenGazeSnapshot = new ScreenGaze(ScreenGaze);

            //
            // take a screenshot of the desktop and crop it to the user gaze
            //

            var screenshot = this.TakeScreenshot();
            var crop = new Bitmap(ScreenGazeSnapshot.m_GazeRect.Width, ScreenGazeSnapshot.m_GazeRect.Height);
            Graphics g = Graphics.FromImage(crop);
            g.DrawImage(screenshot, -ScreenGazeSnapshot.m_GazeRect.X, -ScreenGazeSnapshot.m_GazeRect.Y);

            //
            // use 'CV' techniques to identify on-screen click targets
            //

            var rects = do_cv(crop);

            //
            // convert the on-screen 'rectangles' to higher level 'gaze targets' for rendering
            //

            // TODO: we should put this in a config somewhere and allow the user to specify it
            var allowedLabels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789";

            GazeTargets.Clear();
            for (int i = 0; i < rects.Count; i++)
            {
                var r = rects[i];

                // TODO: we only assign as many unique labels as we have...
                var targetLabel = "";
                if (i < allowedLabels.Length)
                    targetLabel = allowedLabels[i].ToString();

                GazeTargets.Add(new GazeTarget(targetLabel, new Rectangle(r.X, r.Y, r.Width, r.Height)));
            }

            Console.WriteLine("done");
            m_Active = true;
            m_Dirty = true;
        }

        private void ClearGazeSnapshot()
        {
            m_Active = false;
            GazeTargets.Clear();
            m_Dirty = true;
        }

        private List<OpenCvSharp.Rect> do_cv(Bitmap crop)
        {

            // convert the given image to an openCV mat(erial)
            var image = OpenCvSharp.Extensions.BitmapConverter.ToMat(crop);
            //new CvWindowEx(image);

            // apply some image filters to the given image to improve CV operations
            var gray = new Mat();
            Cv2.CvtColor(image, gray, ColorConversionCodes.BGR2GRAY);
            var gray2 = new Mat();
            Cv2.BilateralFilter(gray, gray2, 10, 17, 17);
            var edged = new Mat();
            Cv2.Canny(gray, edged, 80, 200);
            //new CvWindowEx(edged);

            // dilate / thicken the shapes in the given image
            var dilated = new Mat();
            Cv2.Dilate(edged, dilated, null);
            //new CvWindowEx(edged);

            //
            // use openCV to compute 'contours' (or boxes) around 'features' in
            // in the area of interest (the cropped screenshot)
            //

            OpenCvSharp.Point[][] contours;
            OpenCvSharp.HierarchyIndex[] hierarchy;
            Cv2.FindContours(dilated, out contours, out hierarchy, RetrievalModes.Tree, ContourApproximationModes.ApproxSimple);

            //----------------------------------------------------------------
            //          OBJECT CONTOUR / CLICK TARGET FILTRATION
            //----------------------------------------------------------------

            var filteredContours = new List<OpenCvSharp.Rect>();
            foreach (var c in contours)
            {
                var contourRect = Cv2.BoundingRect(c);
                double aspectRatio = contourRect.Width / contourRect.Height;

                // discard contours that look like 'lines' such as the edge of a window
                if ((aspectRatio > 3 || aspectRatio < 0.2) && (contourRect.Height < 8 || contourRect.Width < 8))
                {
                    //Cv2.Rectangle(image, contourRect, new Scalar(0, 0, 255, 255));
                    Console.WriteLine("Bad ratio... " + aspectRatio);
                    continue;
                }

                // discard contours deemed 'too large'
                if (contourRect.Width * contourRect.Height > 6000)
                {
                    //Cv2.Rectangle(image, contourRect, new Scalar(255, 0, 0, 255));
                    Console.WriteLine("Bad size... " + contourRect.Width);
                    continue;
                }

                filteredContours.Add(contourRect);
                //Cv2.Rectangle(image, contourRect, new Scalar(255, 255, 0, 255));
            }
            //new CvWindowEx(image);

            //----------------------------------------------------------------
            //          CLICK TARGET COORDINATE TRANSLATION
            //----------------------------------------------------------------

            // TODO we should probably move this outside of this function

            var transRects = new List<Rect>();
            var goodRects = NonMaxSuppression(filteredContours, 0.3f);
            Console.WriteLine(goodRects.Count);

            foreach (var rect in goodRects)
            {
                Cv2.Rectangle(image, rect, new Scalar(0, 255, 0, 255));
                transRects.Add(new Rect(ScreenGazeSnapshot.m_GazeRect.X + rect.X, ScreenGazeSnapshot.m_GazeRect.Y + rect.Y, rect.Width, rect.Height));
            }
            //new CvWindowEx(image);

            // save the 'rendered' cv results incase we want to dump it to disk later
            m_LastScreenCrop = crop;
            m_LastScreenCropCV = OpenCvSharp.Extensions.BitmapConverter.ToBitmap(image);

            // return the results
            return transRects;
        }
        private void SaveHardTestcase()
        {

            var screenshot = this.TakeScreenshot(false);
            var crop = new Bitmap(ScreenGazeSnapshot.m_GazeRect.Width, ScreenGazeSnapshot.m_GazeRect.Height);
            Graphics g = Graphics.FromImage(crop);
            g.DrawImage(screenshot, -ScreenGazeSnapshot.m_GazeRect.X, -ScreenGazeSnapshot.m_GazeRect.Y);

            // take the current timestamp
            TimeSpan t = DateTime.UtcNow - new DateTime(1970, 1, 1);
            int timestamp = (int)t.TotalSeconds;

            // create the directory that stores 'hard' testcases (if it does not exist
            var dirKeyholeData = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Keyhole");
            var dirKeyholeHard = Path.Combine(dirKeyholeData, "hard");
            System.IO.Directory.CreateDirectory(dirKeyholeHard);

            // write images
            var filepathTestcase = Path.Combine(dirKeyholeHard, timestamp.ToString() + ".png");
            var filepathTestcaseLabels = Path.Combine(dirKeyholeHard, timestamp.ToString() + "_labels.png");
            m_LastScreenCrop.Save(filepathTestcase, ImageFormat.Png); // raw crop, without labels
            crop.Save(filepathTestcaseLabels, ImageFormat.Png);       // crop, with (bad) labels

        }

        //--------------------------------------------------------------------
        // NonMaxSuppression Adapted from
        //  - https://github.com/martinkersner/non-maximum-suppression-cpp/blob/master/nms.cpp
        //  - https://www.pyimagesearch.com/2015/02/16/faster-non-maximum-suppression-python/
        //--------------------------------------------------------------------

        List<OpenCvSharp.Rect> NonMaxSuppression(List<OpenCvSharp.Rect> boxes, float overlapThreshold)
        {

            // nothing to proccess
            if (!boxes.Any())
                return new List<OpenCvSharp.Rect>();

            // convert rects to float Lists
            var floatBoxes = new List<List<float>>();
            foreach (var r in boxes)
                floatBoxes.Add(new List<float>(new float[] { r.X, r.Y, r.BottomRight.X, r.BottomRight.Y }));

            // grab the coordinates of the bounding boxes
            var x1 = GetPointFromRect(floatBoxes, 0);
            var y1 = GetPointFromRect(floatBoxes, 1);
            var x2 = GetPointFromRect(floatBoxes, 2);
            var y2 = GetPointFromRect(floatBoxes, 3);

            // compute the area of the bounding boxes and sort the bounding
            // boxes by the bottom-right y-coordinate of the bounding box
            var area = ComputeArea(x1, y1, x2, y2);
            var idxs = argsort(y2);

            var pick = new List<int>();

            // keep looping while some indexes still remain in the indexes list
            while (idxs.Count > 0)
            {
                // grab the last index in the indexes list and add the
                // index value to the list of picked indexes
                int last = idxs.Count - 1;
                int i = idxs[last];
                pick.Add(i);

                // find the largest (x, y) coordinates for the start of
                // the bounding box and the smallest (x, y) coordinates
                // for the end of the bounding box
                var idxsWoLast = RemoveLast(idxs);

                var xx1 = Maximum(x1[i], CopyByIndexes(x1, idxsWoLast));
                var yy1 = Maximum(y1[i], CopyByIndexes(y1, idxsWoLast));
                var xx2 = Minimum(x2[i], CopyByIndexes(x2, idxsWoLast));
                var yy2 = Minimum(y2[i], CopyByIndexes(y2, idxsWoLast));

                // compute the width and height of the bounding box
                var w = Maximum(0, Subtract(xx2, xx1));
                var h = Maximum(0, Subtract(yy2, yy1));

                // compute the ratio of overlap
                var overlap = Divide(Multiply(w, h), CopyByIndexes(area, idxsWoLast));

                // delete all indexes from the index list that have
                var deleteIdxs = WhereLarger(overlap, overlapThreshold);
                deleteIdxs.Add(last);
                idxs = RemoveByIndexes(idxs, deleteIdxs);
            }

            return FilterList(boxes, pick);
        }

        List<float> GetPointFromRect(List<List<float>> rects, int pos)
        {
            var points = new List<float>();
  
            foreach (var r in rects)
                points.Add(r[pos]);
  
          return points;
        }

        List<float> ComputeArea(List<float> x1, List<float> y1, List<float> x2, List<float> y2)
        {
            var area = new List<float>();
            var len = x1.Count;

            for (var idx = 0; idx < len; ++idx)
            {
                float tmpArea = (x2[idx] - x1[idx] + 1) * (y2[idx] - y1[idx] + 1);
                area.Add(tmpArea);
            }

            return area;
        }

        List<int> argsort(List<float> v)
        {
            // initialize original index locations
            var idx = Enumerable.Range(0, v.Count).ToList();

            // sort indexes based on comparing values in v
            idx.Sort((X, Y) => ((v[X]).CompareTo(v[Y])));
  
            // return sorted list
            return idx;
        }

        List<float> Maximum(float num, List<float> vec)
        {
            var maxVec = new List<float>(vec);
            var len = vec.Count;
  
            for (var idx = 0; idx < len; ++idx)
                if (vec[idx] < num)
                    maxVec[idx] = num;
  
            return maxVec;
        }

        List<float> Minimum(float num, List<float> vec)
        {
            var minVec = new List<float>(vec);
            var len = vec.Count;

            for (var idx = 0; idx < len; ++idx)
                if (vec[idx] > num)
                    minVec[idx] = num;

            return minVec;
        }

        List<float> CopyByIndexes(List<float> vec, List<int> idxs)
        {
            var resultVec = new List<float>();
  
            foreach (var idx in idxs)
                resultVec.Add(vec[idx]);
  
            return resultVec;
        }

        List<int> RemoveLast(List<int> vec)
        {
            var result = new List<int>(vec);
            result.RemoveAt(result.Count - 1);
            return result;
        }

        List<float> Subtract(List<float> vec1, List<float> vec2)
        {
            var result = new List<float>();
            var len = vec1.Count;

            for (var idx = 0; idx < len; ++idx)
                result.Add(vec1[idx] - vec2[idx] + 1);

            return result;
        }

        List<float> Multiply(List<float> vec1, List<float> vec2)
        {
            var result = new List<float>();
            var len = vec1.Count;

            for (var idx = 0; idx < len; ++idx)
                result.Add(vec1[idx] * vec2[idx]);

            return result;
        }

        List<float> Divide(List<float> vec1, List<float> vec2)
        {
            var result = new List<float>();
            var len = vec1.Count;

            for (var idx = 0; idx < len; ++idx)
                result.Add(vec1[idx] / vec2[idx]);

            return result;
        }

        List<int> WhereLarger(List<float> vec, float threshold)
        {
            var result = new List<int>();
            var len = vec.Count;

            for (var idx = 0; idx < len; ++idx)
                if (vec[idx] > threshold)
                    result.Add(idx);

            return result;
        }

        List<int> RemoveByIndexes(List<int> vec, List<int> idxs)
        {
            var resultVec = new List<int>(vec);
            var offset = 0;

            foreach (var idx in idxs) {
                resultVec.RemoveAt(idx + offset);
                offset -= 1;
            }

            return resultVec;
        }

        List<OpenCvSharp.Rect> BoxesToRectangles(List<List<float>> boxes)
        {
            var rectangles = new List<OpenCvSharp.Rect>();

            foreach (var box in boxes)
                rectangles.Add(new OpenCvSharp.Rect((int)box[0], (int)box[1], (int)(box[2] - box[0]), (int)(box[3] - box[1])));

            return rectangles;
        }

        List<OpenCvSharp.Rect> FilterList(List<OpenCvSharp.Rect> vec, List<int> idxs)
        {
            var resultVec = new List<OpenCvSharp.Rect>();

            foreach (var idx in idxs)
                resultVec.Add(vec[idx]);
  
            return resultVec;
        }

        //
        // screen utils
        //

        Rectangle CenterRectangle(Rectangle rect, System.Drawing.Point center)
        {
            rect.X = center.X - rect.Width / 2;
            rect.Y = center.Y - rect.Height / 2;
            return rect;
        }

        Rectangle BoundRectangle(Rectangle subject, Rectangle bounds)
        {

            // bound x axis
            if (subject.X < bounds.X)
                subject.X = bounds.X;
            if (subject.Right > bounds.Right)
                subject.X = bounds.Right - subject.Width;

            // bound y axis
            if (subject.Y < bounds.Y)
                subject.Y = bounds.Y;
            if (subject.Bottom > bounds.Bottom)
                subject.Y = bounds.Bottom - subject.Height;

            return subject;
        }

        private Bitmap TakeScreenshot(Boolean hideKeyhole = true)
        {
            // Hide the Form
            if (hideKeyhole)
                window.Hide();

            // Create the Bitmap
            Bitmap printscreen = new Bitmap(Screen.Width, Screen.Height);
            Graphics graphics = Graphics.FromImage(printscreen as Image);

            // Take screenshot
            graphics.CopyFromScreen(0, 0, 0, 0, printscreen.Size);

            //Show Form
            window.Show();

            return printscreen;
        }

        //
        // mouse utils
        // 

        [DllImport("user32.dll", CharSet = CharSet.Auto, CallingConvention = CallingConvention.StdCall)]
        public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint cButtons, uint dwExtraInfo);
        //Mouse actions
        private const int MOUSEEVENTF_LEFTDOWN = 0x02;
        private const int MOUSEEVENTF_LEFTUP = 0x04;
        private const int MOUSEEVENTF_RIGHTDOWN = 0x08;
        private const int MOUSEEVENTF_RIGHTUP = 0x10;

        public void DoMouseClick(int x, int y)
        {
            Cursor.Position = new System.Drawing.Point(x, y);
            //Thread.Sleep(500);
            mouse_event(MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_LEFTUP, 0, 0, 0, 0);
        }

    }

    static class Program
    {
        /// <summary>
        /// The main entry point for the application.
        /// </summary>
        [STAThread]
        static void Main()
        {
            Console.WriteLine("                                                         ");
            Console.WriteLine(" -[ Keyhole v0.1 -- https://github.com/gaasedelen/keyhole");
            Console.WriteLine("                                                         ");
            Console.WriteLine("     ... an exprimental accessibility technology         ");
            Console.WriteLine("                                                         ");
            Console.WriteLine("                      by markus gaasedelen, (c) 2020     ");
            Console.WriteLine("                                                         ");
            Console.WriteLine("---------------------------------------------------------");

            var argv = Environment.GetCommandLineArgs();

            // the default 'hotkey' for the keyhole overlay (F20, lol)
            var overlayKey = Keys.F20;

            // if the user specifies an arg to the program, this will be the default key
            if(argv.Length == 3 && argv[1] == "-k")
            {
                overlayKey = (Keys)System.Enum.Parse(typeof(Keys), argv[2]);
            }

            Console.WriteLine("Using '" + overlayKey.ToString() + "' as the default hotkey, use -k <key> to change...");

            Keyhole k = new Keyhole(overlayKey);
            Application.Run(k.window);
        }

        private static void EyeTracker_EventErrorOccurred(object sender, EventErrorEventArgs e)
        {
            Console.WriteLine("An error occured at time stamp {0}.", e.SystemTimeStamp);
            Console.WriteLine(e.Message);
        }

    }
}
