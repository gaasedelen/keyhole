using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Runtime.InteropServices;


namespace keyhole
{

    public partial class Form1 : CSWinFormLayeredWindow.PerPixelAlphaForm
    {
        private Keyhole parent;

        // top level graphics
        private Bitmap m_Bitmap;
        private Graphics m_Graphics;

        // screen overlay
        private SolidBrush overlayBackground = new System.Drawing.SolidBrush(Color.FromArgb(64, 128, 128, 128));
        private Pen overlayBorder = new System.Drawing.Pen(Color.Red);

        // a 'bad' target rect
        private SolidBrush badTargetBackground = new System.Drawing.SolidBrush(Color.FromArgb(64, 255, 0, 0));
        private Pen badTargetBorder = new System.Drawing.Pen(Color.Red);

        // target rect
        private SolidBrush targetBackground = new System.Drawing.SolidBrush(Color.FromArgb(64, 0, 255, 0));
        private Pen targetBorder = new System.Drawing.Pen(Color.Lime);

        // target labels
        private Font labelFont = new Font("Consolas", 10);
        private SolidBrush labelBackground = new System.Drawing.SolidBrush(Color.FromArgb(255, 60, 60, 60));
        private Pen labelBorder = new System.Drawing.Pen(Color.FromArgb(255, 160, 160, 160));
        private SolidBrush labelTextColor = new System.Drawing.SolidBrush(Color.White);

        public Form1(Keyhole parent)
        {
            this.parent = parent;
            this.m_Bitmap = new Bitmap(parent.Screen.Width, parent.Screen.Height, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
            this.m_Graphics = Graphics.FromImage(this.m_Bitmap);
            this.m_Graphics.CompositingMode = System.Drawing.Drawing2D.CompositingMode.SourceCopy;
            InitializeComponent();
        }

        private void Form1_Load(object sender, EventArgs e)
        {
            // nothing
        }

        protected override void OnPaint(PaintEventArgs e)
        {

            // draw overlay bg and outline
            m_Graphics.FillRectangle(Brushes.Transparent, parent.Screen);
            //m_Graphics.FillRectangle(overlayBackground, 0, 0, this.Size.Width, this.Size.Height);
            //m_Graphics.DrawRectangle(overlayBorder, 0, 0, this.Size.Width - 1, this.Size.Height - 1);

            // draw gaze rect
            if (parent.GazeTargets.Count > 0)
            {
                m_Graphics.FillRectangle(Brushes.Transparent, parent.ScreenGazeSnapshot.m_GazeRect);
                m_Graphics.DrawRectangle(overlayBorder, parent.ScreenGazeSnapshot.m_GazeRect);
            }

            // draw object rects
            foreach (var target in parent.GazeTargets)
            {

                // draw matching rect
                if (target.Label.Length > 0)
                {
                    m_Graphics.FillRectangle(targetBackground, target.Rect);
                    m_Graphics.DrawRectangle(targetBorder, target.Rect);
                }

                // NOTE: we draw red rects around the targets we couldn't supply labels with for debug
                else
                {
                    m_Graphics.FillRectangle(badTargetBackground, target.Rect);
                    m_Graphics.DrawRectangle(badTargetBorder, target.Rect);
                    continue;
                }

                // compute size of char
                //var s1 = TextRenderer.MeasureText(target.Label, labelFont, ClientSize, TextFormatFlags.NoPadding);
                //var s2 = TextRenderer.MeasureText(target.Label + target.Label, labelFont, ClientSize, TextFormatFlags.NoPadding);
                //var textSize = Size.Ceiling(new SizeF(s2.Width-s1.Width, s1.Height));
                //var textSize = TextRenderer.MeasureText(target.Label, labelFont, ClientSize, TextFormatFlags.NoPadding);
                var textSize = new Size(11, 15);
                var labelPadding = new Size(2, 0);
                //Console.WriteLine(textSize);

                // compute rect for labels
                var textRect = new Rectangle(target.X - textSize.Width / 2, target.Y - textSize.Height / 2, textSize.Width, textSize.Height);
                var labelRect = new Rectangle(
                    textRect.X - labelPadding.Width / 2, 
                    textRect.Y - labelPadding.Height / 2, 
                    textRect.Width + labelPadding.Width, 
                    textRect.Height + labelPadding.Height
                );

                // draw labels
                this.m_Graphics.CompositingMode = System.Drawing.Drawing2D.CompositingMode.SourceOver;

                m_Graphics.FillRectangle(labelBackground, labelRect);
                m_Graphics.DrawRectangle(labelBorder, labelRect);
                m_Graphics.DrawString(target.Label, labelFont, labelTextColor, textRect);

                this.m_Graphics.CompositingMode = System.Drawing.Drawing2D.CompositingMode.SourceCopy;

            }

            this.SelectBitmap(this.m_Bitmap);
        }
    }
}