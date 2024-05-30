//------------------------------------------------------------------------------------------------
// File: TcpSendRecvJpeg.cpp
// Project: LG Exec Ed Program
// Versions:
// 1.0 April 2017 - initial version
// Send and receives OpenCV Mat Images in a Tcp Stream commpressed as Jpeg images 
//------------------------------------------------------------------------------------------------
#include <opencv2/highgui/highgui.hpp>
#include "TcpSendRecvJpeg.h"
#include "Message.h"

static  int init_values[2] = { cv::IMWRITE_JPEG_QUALITY,80 }; //default(95) 0-100
static  std::vector<int> param (&init_values[0], &init_values[0]+2);
static  std::vector<uchar> sendbuff;//buffer for coding

//-----------------------------------------------------------------
// TcpSendImageAsJpeg - Sends a Open CV Mat Image commressed as a 
// jpeg image in side a TCP Stream on the specified TCP local port
// and Destination. return bytes sent on success and -1 on failure
//-----------------------------------------------------------------
int TcpSendImageAsJpeg(TTcpConnectedPort * TcpConnectedPort,cv::Mat Image)
{
    TMesssageHeader MsgHdr;
    MsgHdr.Type=htonl(MT_IMAGE);
    cv::imencode(".jpg", Image, sendbuff, param);
    MsgHdr.Len=htonl(sendbuff.size()); // convert image size to network format
    if (WriteDataTcp(TcpConnectedPort,(unsigned char *)&MsgHdr,sizeof(TMesssageHeader))!=sizeof(TMesssageHeader))
    return(-1);
    return(WriteDataTcp(TcpConnectedPort,sendbuff.data(), sendbuff.size()));
}

//-----------------------------------------------------------------
// END TcpSendImageAsJpeg
//-----------------------------------------------------------------
//-----------------------------------------------------------------
// TcpRecvImageAsJpeg - Sends a Open CV Mat Image commressed as a 
// jpeg image in side a TCP Stream on the specified TCP local port
// returns true on success and false on failure
//-----------------------------------------------------------------
bool TcpRecvImageAsJpeg(TTcpConnectedPort * TcpConnectedPort,cv::Mat *Image)
{
  TMesssageHeader MsgHdr;
  unsigned char *buff;	/* receive buffer */   
  
  if (ReadDataTcp(TcpConnectedPort,(unsigned char *)&MsgHdr,sizeof(TMesssageHeader))!=sizeof(TMesssageHeader)) return(false);
  
  MsgHdr.Len=ntohl(MsgHdr.Len); // convert image size to host format
  MsgHdr.Type=htonl(MsgHdr.Type);
  if (MsgHdr.Len<0) return false;
  if (MsgHdr.Type!=MT_IMAGE)
    {
     printf("TcpRecvImageAsJpeg recived non imagage mt %d\n",MsgHdr.Type);
     return false;
    }

  buff = new (std::nothrow) unsigned char [MsgHdr.Len];
  if (buff==NULL) return false;

  if((ReadDataTcp(TcpConnectedPort,buff,MsgHdr.Len))==MsgHdr.Len)
   {
     cv::imdecode(cv::Mat(MsgHdr.Len,1,CV_8UC1,buff), cv::IMREAD_COLOR, Image );
     delete [] buff;
     if (!(*Image).empty()) return true;
     else return false;
   }
   delete [] buff;
   return false;
}

//-----------------------------------------------------------------
// END TcpRecvImageAsJpeg
//-----------------------------------------------------------------
//-----------------------------------------------------------------
// END of File
//-----------------------------------------------------------------
