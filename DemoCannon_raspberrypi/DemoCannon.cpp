#include <iostream>
#include <string>
#include <vector>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <opencv2/core/core.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <opencv2/features2d/features2d.hpp>
#include <opencv2/features2d.hpp>
#include "opencv2/video/tracking.hpp"
#include "opencv2/imgproc/imgproc.hpp"
#include "CvImageMatch.h"
#include "ObjectDetector.h"


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


int main(int /*argc*/, char** /*argv*/)
{
	char in;

			RunMode = USE_TENSORFLOW_LITE;

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
		detector = new ObjectDetector("../TfLite-2.17/Data/detect.tflite", false);
	}
	char Filename[1024];
	char PathFile[1024];
	char Path[] = "./";
	char Folder[] = "images";
	char ext[] = "jpg";

	int count = 1;
	while (1)
	{
		sprintf(Filename, "Capture%d", count);
		sprintf(PathFile, "%s%s/%s.%s", Path, Folder, Filename,ext);

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
		char name[1024];
		sprintf(name, "./images/result_image%d.jpg", count);
    		cv::imwrite(name, image);
#if 1
		printf("before wait\n");
		int c = waitKey();
		if ((char)c == 27) break;
		printf("after wait\n");
#endif
		count++;
	}

	return 0;
}
