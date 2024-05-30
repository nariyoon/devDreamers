#include <iostream>
#include <fstream>
#include "opencv2/core.hpp"
#include "opencv2/highgui.hpp"
#include "opencv2/imgproc.hpp"
#include "ObjectDetector.h"
#include "NetworkTCP.h"
#include "TcpSendRecvJpeg.h"
#include "IsRPI.h"

#define WIDTH  1920
#define HEIGHT 1080

#if IsPi5
#include "lgpio.h"
#include <lccv.hpp>
#endif

#if IsPi5
#define USE_USB_WEB_CAM 0 //Change to 1 to use usb camera on PI
#else
#define USE_USB_WEB_CAM 1
#endif

using namespace std;
using namespace cv;

static TTcpListenPort    *TcpListenPort=NULL;
static TTcpConnectedPort *TcpConnectedPort=NULL;

static void CleanUp(void)
{
 CloseTcpConnectedPort(&TcpConnectedPort); // Close network port;
 CloseTcpListenPort(&TcpListenPort);  // Close listen port
 printf("restored\n");
}

void runObjectDetection() {
	Mat src = imread("../Data/Capture1.jpg");

	ObjectDetector detector = ObjectDetector("../Data/detect.tflite", false);
	DetectResult* res = detector.detect(src);
	for (int i = 0; i < detector.DETECT_NUM; ++i) {
		int labelnum = res[i].label;
		float score = res[i].score;
		float xmin = res[i].xmin;
		float xmax = res[i].xmax;
		float ymin = res[i].ymin;
		float ymax = res[i].ymax;
                int baseline=0;
                
                if (score<0.10) continue;
                    
                cv::rectangle(src, Point(xmin,ymin), Point(xmax,ymax), Scalar(10, 255, 0), 2);
                cv::String label =to_string(labelnum) + ": " + to_string(int(score*100))+ "%";
               
                Size labelSize= cv::getTextSize(label, cv::FONT_HERSHEY_SIMPLEX, 0.7, 2,&baseline); // Get font size
                int label_ymin = std::max((int)ymin, (int)(labelSize.height + 10)); // Make sure not to draw label too close to top of window
                rectangle(src, Point(xmin, label_ymin-labelSize.height-10), Point(xmin+labelSize.width, label_ymin+baseline-10), Scalar(255, 255, 255), cv::FILLED); // Draw white box to put label text in
                putText(src, label, Point(xmin, label_ymin-7), cv::FONT_HERSHEY_SIMPLEX, 0.7, Scalar(0, 0, 0), 2); // Draw label text
		}

                cv::resize(src, src, Size(src.cols/1,src.rows/1));
                if (IsPi5)   
                   {  
                   // if (IsPi5) flip(src, src,-1);       // if running on PI5 flip(-1)=180 degrees    
                    TcpSendImageAsJpeg(TcpConnectedPort,src);
                   }
                else imshow("test", src);

	waitKey(0);
}

void runObjectDetectionLive() {
#if USE_USB_WEB_CAM
cv::VideoCapture *capt=NULL;
#else
static lccv::PiCamera * cap=NULL;
#endif

#if USE_USB_WEB_CAM
    //cap=new cv::VideoCapture("/dev/video8",cv::CAP_V4L);
	cap=new cv::VideoCapture(0);
    if(!cap->isOpened()) {
        std::cout<<"Failed to open camera."<<std::endl;
        delete cap;
        return;
    }
#else
    cap= new lccv::PiCamera();
    cap->options->video_width=WIDTH;
    cap->options->video_height=HEIGHT;
    cap->options->framerate=30;
    cap->options->verbose=true;
    cap->startVideo();
#endif
	ObjectDetector detector = ObjectDetector("../Data/detect.tflite", false, false);
	int i = 0;
	long long duration = 0;
	double fps = 0;
	while (true) {
		Mat frame;
#if USE_USB_WEB_CAM
    // wait for a new frame from camera and store it into 'frame'
    cap->read(frame);
    // check if we succeeded
    if (frame.empty())
    {
      printf("ERROR! blank frame grabbed\n");
      continue;
    }
#else
        //if(!cap->getVideoFrame(frame,1000)){
        //   printf("ERROR! blank frame grabbed\n");
        //    continue;
       // }
       frame=imread("../Data/Capture1.jpg");

#endif
		auto start = chrono::high_resolution_clock::now();
		DetectResult* res = detector.detect(frame);
		auto stop = chrono::high_resolution_clock::now();
		for (int i = 0; i < detector.DETECT_NUM; ++i) {
                        
			int labelnum = res[i].label;
			float score = res[i].score;
			float xmin = res[i].xmin;
			float xmax = res[i].xmax;
			float ymin = res[i].ymin;
			float ymax = res[i].ymax;
                        int baseline=0;
                        
                        if (score<0.10) continue;

                        cv::rectangle(frame, Point(xmin,ymin), Point(xmax,ymax), Scalar(10, 255, 0), 2);
                        cv::String label =to_string(labelnum) + ": " + to_string(int(score*100))+ "%";
               
                        Size labelSize= cv::getTextSize(label, cv::FONT_HERSHEY_SIMPLEX, 0.7, 2,&baseline); // Get font size
                        int label_ymin = std::max((int)ymin, (int)(labelSize.height + 10)); // Make sure not to draw label too close to top of window
                        rectangle(frame, Point(xmin, label_ymin-labelSize.height-10), Point(xmin+labelSize.width, label_ymin+baseline-10), Scalar(255, 255, 255), cv::FILLED); // Draw white box to put label text in
                        putText(frame, label, Point(xmin, label_ymin-7), cv::FONT_HERSHEY_SIMPLEX, 0.7, Scalar(0, 0, 0), 2); // Draw label text
		}

		auto d = chrono::duration_cast<chrono::milliseconds>(stop - start);
		duration += d.count();
		if (++i % 5 == 0) {
			fps = (1000.0 / duration) * 5;
			duration = 0;
		}
                cv::String label =to_string((int)fps)+ " fps";
                int baseline=0;

                Size labelSize= cv::getTextSize(label, cv::FONT_HERSHEY_SIMPLEX, 0.7, 2,&baseline); // Get font size
                int label_ymin = 30; 
                rectangle(frame, Point(30, label_ymin-labelSize.height-10), Point(30+labelSize.width, label_ymin+baseline-10), Scalar(255, 255, 255), cv::FILLED); // Draw white box to put label text in
                putText(frame, label, Point(30, label_ymin-7), cv::FONT_HERSHEY_SIMPLEX, 0.7, Scalar(0, 0, 0), 2); // Draw label text

                cv::resize(frame, frame, Size(frame.cols/2,frame.rows/2));
                if (IsPi5)   
                   {  
                    //if (IsPi5) flip(frame, frame,-1);       // if running on PI5 flip(-1)=180 degrees    
                    if (TcpSendImageAsJpeg(TcpConnectedPort,frame)<0)  break;
                   }
                else imshow("frame", frame);


		int k = waitKey(50);
		if (k > 0) {
			break;
		}
	}
}


int main(int argc, const char** argv)
{
  struct sockaddr_in cli_addr;
  socklen_t          clilen;

 printf("Tensorflow Lite Version %s\n",TfLiteVersion());

 if (IsPi5)
{
   if (argc !=2) {
       fprintf(stderr,"usage %s port\n", argv[0]);
       exit(0);
    }

   printf("Listening for connections\n");
   
   if  ((TcpListenPort=OpenTcpListenPort(atoi(argv[1])))==NULL)  // Open UDP Network port
     {
       printf("OpenTcpListenPortFailed\n");
       return(-1);
     }

   clilen = sizeof(cli_addr);
   if  ((TcpConnectedPort=AcceptTcpConnection(TcpListenPort,&cli_addr,&clilen))==NULL)
     {
       printf("AcceptTcpConnection Failed\n");
       return(-1);
     }
 }
   printf("Accepted connection Request\n");
	runObjectDetectionLive();
	//runObjectDetection();
   CleanUp();
}
