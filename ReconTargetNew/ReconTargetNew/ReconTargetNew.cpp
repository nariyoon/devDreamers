#include <iostream>
#include <string>
#include <vector>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <windows.h>
#include <opencv2/core/core.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <opencv2/features2d/features2d.hpp>
#include <opencv2/features2d.hpp>
#include "opencv2/video/tracking.hpp"
#include "opencv2/imgproc/imgproc.hpp"
#include "CvImageMatch.h"
#include "ObjectDetector.h"

#if  defined(_WIN32) || defined(_WIN64)
#pragma comment(lib,"Shlwapi.lib")
#ifdef _DEBUG
#pragma comment(lib,"..\\..\\..\\opencv\\build\\x64\\vc16\\lib\\opencv_world490d.lib")
#pragma comment(lib,"..\\tflite-dist\\libs\\windows_x86_64\\tensorflowlite_c.dll.if.lib")
#else
#pragma comment(lib,"..\\..\\..\\opencv\\build\\x64\\vc16\\lib\\opencv_world490.lib")
#pragma comment(lib,"..\\tflite-dist\\libs\\windows_x86_64\\tensorflowlite_c.dll.if.lib")
#endif
#endif

using namespace cv;
using namespace std;


static ObjectDetector* detector=NULL;


typedef enum
{
	NONE,
	USE_IMAGE_MATCH,
	USE_TENSORFLOW_LITE
} TRunMode;

static TRunMode RunMode = NONE;

CHAR GetCh(VOID)
{
	HANDLE hStdin = GetStdHandle(STD_INPUT_HANDLE);
	INPUT_RECORD irInputRecord;
	DWORD dwEventsRead;
	CHAR cChar;

	while (ReadConsoleInputA(hStdin, &irInputRecord, 1, &dwEventsRead)) /* Read key press */
		if (irInputRecord.EventType == KEY_EVENT
			&& irInputRecord.Event.KeyEvent.wVirtualKeyCode != VK_SHIFT
			&& irInputRecord.Event.KeyEvent.wVirtualKeyCode != VK_MENU
			&& irInputRecord.Event.KeyEvent.wVirtualKeyCode != VK_CONTROL)
		{
			cChar = irInputRecord.Event.KeyEvent.uChar.AsciiChar;
			ReadConsoleInputA(hStdin, &irInputRecord, 1, &dwEventsRead); /* Read key release */
			return cChar;
		}
	return EOF;
}

int main(int /*argc*/, char** /*argv*/)
{
	char in;

	while (1)
	{
		printf("\nEnter Mode (I)mage Match or (T)ensorFLow Lite (E)xit :");
		in = GetCh();
		if ((in == 'i') || (in == 'I'))
		{
			RunMode = USE_IMAGE_MATCH;
			break;
		}
		else if ((in == 't') || (in == 'T'))
		{
			RunMode = USE_TENSORFLOW_LITE;
			break;
		}
		else if ((in == 'e') || (in == 'E'))
		{
			return(0);
		}
		else printf("Invalid Value\n");
	}
  
	namedWindow("Targets", 1);

	if (RunMode == USE_IMAGE_MATCH)
	{
		printf("Image Match Mode\n");
		DetectedMatches = new  TDetectedMatches[MAX_DETECTED_MATCHES];
		if (LoadRefImages(symbols) == -1) {
			printf("Error reading reference symbols\n");
			return -1;
		}
	}
	else
	{
		printf("TensorFlow Lite Mode\n");
		detector = new ObjectDetector("../../../TfLite-2.17/Data/detect.tflite", false);
	}
	char Filename[1024];
	char PathFile[1024];
	char Path[] = "../../";
	char Folder[] = "images";
	char ext[] = "jpg";

	int count = 1;
	while (1)
	{
		sprintf_s(Filename, "Capture%d", count);
		sprintf_s(PathFile, "%s%s/%s.%s", Path, Folder, Filename,ext);

		Mat image = imread(PathFile, 1);
		if (image.empty())
		{
			cout << "Couldn't load " << Filename << endl;
			exit(0);
		}
		if (RunMode == USE_IMAGE_MATCH)
		{
			FindTargets(image);
			DrawTargets(image);
			WriteFile(Path, Folder, Filename, ext, image);
		}
		else
		{
			DetectResult* res = detector->detect(image);
			for (int i = 0; i < detector->DETECT_NUM; ++i)
			{
				int labelnum = res[i].label;
				float score = res[i].score;
				float xmin = res[i].xmin;
				float xmax = res[i].xmax;
				float ymin = res[i].ymin;
				float ymax = res[i].ymax;
				int baseline = 0;

				if (score < 0.10) continue;

				cv::rectangle(image, Point((int)xmin, (int)ymin), Point((int)xmax, (int)ymax), Scalar(10, 255, 0), 2);
				cv::String label = to_string(labelnum) + ": " + to_string(int(score * 100)) + "%";

				Size labelSize = cv::getTextSize(label, cv::FONT_HERSHEY_SIMPLEX, 0.7, 2, &baseline); // Get font size
				int label_ymin = std::max((int)ymin, (int)(labelSize.height + 10)); // Make sure not to draw label too close to top of window
				rectangle(image, Point((int)xmin, label_ymin - labelSize.height - 10), Point((int)xmin + labelSize.width, label_ymin + baseline - 10), Scalar(255, 255, 255), cv::FILLED); // Draw white box to put label text in
				putText(image, label, Point((int)xmin, label_ymin - 7), cv::FONT_HERSHEY_SIMPLEX, 0.7, Scalar(0, 0, 0), 2); // Draw label text
			}
			delete[] res;
		}
		resize(image, image, Size(image.cols / 2, image.rows / 2));
		imshow("Targets", image);
#if 1
		//printf("before wait\n");
		int c = waitKey();
		if ((char)c == 27) break;
		//printf("after wait\n");
#endif
		count++;
	}

	return 0;
}
