//------------------------------------------------------------------------------------------------
// File: SendImageTCP.cpp
// Project: LG Exec Ed Program
// Versions:
// 1.0 April 2017 - initial version
// This program Sends a jpeg image From the Camera via a TCP Stream to a remote destination. 
//----------------------------------------------------------------------------------------------

#include <stdio.h>
#include <stdlib.h>
#include <opencv2/core/core.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <iostream>
#include "NetworkTCP.h"
#include "TcpSendRecvJpeg.h"
#include <lccv.hpp>

using namespace cv;
using namespace std;

#define USE_USB_WEB_CAM 0

//----------------------------------------------------------------
// main - This is the main program for the RecvImageUDP demo 
// program  contains the control loop
//---------------------------------------------------------------

int main(int argc, char *argv[])
{

  Mat                image;          // camera image in Mat format 
  TTcpListenPort    *TcpListenPort;
  TTcpConnectedPort *TcpConnectedPort;
  struct sockaddr_in cli_addr;
  socklen_t          clilen;
  int key;

    if (argc !=2) 
    {
       fprintf(stderr,"usage %s port\n", argv[0]);
       exit(0);
    }

    int capture_width = 1920 ;
    int capture_height = 1080 ;
    int display_width = 1920 ;
    int display_height = 1080 ;
    int framerate = 30 ;


#if  USE_USB_WEB_CAM
   cv::VideoCapture capture("/dev/video8",cv::CAP_V4L);
 
    if(!capture.isOpened()) {
        std::cout<<"Failed to open camera."<<std::endl;
        return (-1);
    }

#else // Built-in camera

    lccv::PiCamera capture;
    capture.options->video_width=capture_width;
    capture.options->video_height=capture_height;
    capture.options->framerate=framerate;
    capture.options->verbose=true;
    capture.startVideo();
#endif


   if  ((TcpListenPort=OpenTcpListenPort(atoi(argv[1])))==NULL)  // Open UDP Network port
     {
       printf("OpenTcpListenPortFailed\n");
       return(-1); 
     }

    
   clilen = sizeof(cli_addr);
    
   printf("Listening for connections\n");

   if  ((TcpConnectedPort=AcceptTcpConnection(TcpListenPort,&cli_addr,&clilen))==NULL)
     {  
       printf("AcceptTcpConnection Failed\n");
       return(-1); 
     }

   printf("Accepted connection Request\n");
   

  do
   {

#if USE_USB_WEB_CAM
    // wait for a new frame from camera and store it into 'frame'
    capture.read(image);
    // check if we succeeded
    if (image.empty())
    {
      printf("ERROR! blank frame grabbed\n");
      continue;
    }
#else
    if(!capture.getVideoFrame(image,1000)){
            printf("ERROR! blank frame grabbed\n");
            continue;
        }
#endif
	
	
    // Send processed UDP image
    if (TcpSendImageAsJpeg(TcpConnectedPort,image)<0)  break;   
    key = (waitKey(10) & 0xFF);
    //printf("%d\n",key);
   } while (key!= 'q'); // loop until user hits quit

 CloseTcpConnectedPort(&TcpConnectedPort); // Close network port;
 CloseTcpListenPort(&TcpListenPort);  // Close listen port
#if USE_USB_WEB_CAM
capture.release();
#else
capture.stopVideo();
#endif

 return 0; 
}
//-----------------------------------------------------------------
// END main
//-----------------------------------------------------------------
//-----------------------------------------------------------------
// END of File
//-----------------------------------------------------------------
