#include <opencv2\highgui\highgui.hpp>
#include <opencv2\opencv.hpp>
#include <windows.h>
#include "DisplayImage.h"

static HDC hdc;
static HWND hWindowMain;
static BITMAPINFO BitmapInfo;
static bool SetupBitMapInfoSet = false;
static RECT rt;
static bool HaveImage = false;
cv::Mat LastImage;
cv::Mat NoDataAvalable(1080, 1920, CV_8UC3, cv::Scalar(10, 100, 150));

static void SetupBitMapInfo(BITMAPINFO* BitmapInfo, cv::Mat* frame);
static void CreateNoDataAvalable(void);

static void SetupBitMapInfo(BITMAPINFO* BitmapInfo, cv::Mat* frame)
{
    int depth = frame->depth();
    int channels = frame->channels();
    int width = frame->cols;
    int height = frame->rows;

    unsigned int pixelSize = (8 << (depth / 2)) * channels; // pixelSize >= 8
    unsigned long bmplineSize = ((width * pixelSize + 31) >> 5) << 2;   // 

    BitmapInfo->bmiHeader.biSize = 40;
    BitmapInfo->bmiHeader.biWidth = width;
    BitmapInfo->bmiHeader.biHeight = height;
    BitmapInfo->bmiHeader.biPlanes = 1;
    BitmapInfo->bmiHeader.biBitCount = pixelSize;
    BitmapInfo->bmiHeader.biCompression = 0;
    BitmapInfo->bmiHeader.biSizeImage = height * bmplineSize;
    BitmapInfo->bmiHeader.biXPelsPerMeter = 0;
    BitmapInfo->bmiHeader.biYPelsPerMeter = 0;
    BitmapInfo->bmiHeader.biClrUsed = 0;
    BitmapInfo->bmiHeader.biClrImportant = 0;
    memset(&BitmapInfo->bmiColors, 0, sizeof(BitmapInfo->bmiColors));
}


bool InitializeImageDisplay(HWND hWndMain)
{
    hWindowMain = hWndMain;
    hdc = GetDC(hWindowMain);
    SetStretchBltMode(hdc, COLORONCOLOR);
    SetupBitMapInfoSet = false;
    CreateNoDataAvalable();
    return true;
}
static void CreateNoDataAvalable(void)
{
  cv::String Text = cv::format("NO DATA");

  int baseline;
  float FontSize = 3.0; //12.0;
  int Thinkness = 4;

  NoDataAvalable.setTo(cv::Scalar(128, 128, 128));
  cv::Size TextSize = cv::getTextSize(Text, cv::FONT_HERSHEY_COMPLEX, FontSize, Thinkness, &baseline); // Get font size

  int textX = (NoDataAvalable.cols - TextSize.width) / 2;
  int textY = (NoDataAvalable.rows + TextSize.height) / 2;
  cv::putText(NoDataAvalable, Text, cv::Point(textX, textY), cv::FONT_HERSHEY_COMPLEX, FontSize, cv::Scalar(255, 255, 255), Thinkness * Thinkness, cv::LINE_AA);
  cv::putText(NoDataAvalable, Text, cv::Point(textX, textY), cv::FONT_HERSHEY_COMPLEX, FontSize, cv::Scalar(0, 0, 0), Thinkness, cv::LINE_AA);
  printf("frame size %d %d\n", NoDataAvalable.cols, NoDataAvalable.rows);
  cv::resize(NoDataAvalable, NoDataAvalable, cv::Size(NoDataAvalable.cols / 2, NoDataAvalable.rows / 2));
}

void SetDisplayNoData(void)
{
  cv::Mat Temp = NoDataAvalable.clone();
  ProcessImage(Temp);
}

bool ProcessImage(cv::Mat & ImageIn)
{

 if (!ImageIn.empty())
   {
     flip(ImageIn, ImageIn, -1);
     flip(ImageIn, ImageIn, 1);
     LastImage = ImageIn.clone();
     HaveImage = true;
     
     DisplayImage();
   }
  return false;
}

bool DisplayImage(void)
{
    if (HaveImage)
    {
        GetClientRect(hWindowMain, &rt);

        if (!SetupBitMapInfoSet)
        {
            SetupBitMapInfo(&BitmapInfo, &LastImage);
            SetupBitMapInfoSet = true;
        }
#define SCALE 1.3
        StretchDIBits(hdc,
            rt.left + 5, rt.top + 100, (int)((rt.right - rt.left) / SCALE), (int)((rt.bottom - rt.top) / SCALE),
            0, 0, BitmapInfo.bmiHeader.biWidth, BitmapInfo.bmiHeader.biHeight,
            LastImage.data, &BitmapInfo, DIB_RGB_COLORS, SRCCOPY);  //DIB_RGB_COLORS
        return true;
    }
    else  return false;
}
 
//-----------------------------------------------------------------
// END of File
//-----------------------------------------------------------------