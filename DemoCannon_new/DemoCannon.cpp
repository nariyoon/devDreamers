//------------------------------------------------------------------------------------------------
// File: Cannon.cpp
// Project: LG Exec Ed Program
// Versions:
// 1.0 April 2024 - initial version
//------------------------------------------------------------------------------------------------
#include <opencv2/core/core.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <math.h>
#include <stdio.h>
#include <signal.h>
#include <pthread.h>
#include <sys/select.h>
#include "NetworkTCP.h"
#include "TcpSendRecvJpeg.h"
#include "Message.h"
#include "KeyboardSetup.h"
#include "IsRPI.h"
#include <lccv.hpp>
#include "ServoPi.h"
//nclude "ObjectDetector.h"
#include "lgpio.h"
#include "CvImageMatch.h"
#include "ssd1306.h"
#include <csignal>

#define PORT            5000
#define PAN_SERVO       1
#define TILT_SERVO      2
#define MIN_TILT         (-35.0f)
#define MAX_TILT         ( 35.0f)
#define MIN_PAN          (-85.0f)
#define MAX_PAN          ( 85.0f)
#define ANGLE_VALUE      (75)


#define WIDTH           1920
#define HEIGHT          1080

#define INC             0.5f

#define USE_USB_WEB_CAM 0

using namespace cv;
using namespace std;


typedef enum
{
	NOT_ACTIVE,
	ACTIVATE,
	NEW_TARGET,
	LOOKING_FOR_TARGET,
	TRACKING,
	TRACKING_STABLE,
	ENGAGEMENT_IN_PROGRESS,
	ENGAGEMENT_COMPLETE
} TEngagementState;


typedef struct
{
	int                       NumberOfTartgets;
	int                       FiringOrder[10];
	int                       CurrentIndex;
	bool                      HaveFiringOrder;
	volatile TEngagementState State;
	int                       StableCount;
	float                     LastPan;
	float                     LastTilt;   
	int                       Target;
} TAutoEngage;


static TAutoEngage            AutoEngage;
static float                  Pan = 10.0f;
static float                  Tilt = 0.0f;
static float 		      CenterPan = 10.0f;
static float 		      CenterTilt = 0.0f;
static size_t 		      fireCnt = 0;

static unsigned char          RunCmds=0;
static int                    gpioid;
static uint8_t                i2c_node_address = 1;
static bool                   HaveOLED=false;
static int                    OLED_Font=0;
static pthread_t              NetworkThreadID=-1;
static pthread_t              EngagementThreadID=-1;
static pthread_t              SendImageThreadID=-1;
static volatile SystemState_t SystemState= SAFE;
static pthread_mutex_t        TCP_Mutex;
static pthread_mutex_t        GPIO_Mutex;
static pthread_mutex_t        I2C_Mutex;
static pthread_mutex_t        Engmnt_Mutex;
static pthread_mutex_t        Engmnt_Mutex2;
static pthread_mutexattr_t    TCP_MutexAttr;
static pthread_mutexattr_t    GPIO_MutexAttr;
static pthread_mutexattr_t    I2C_MutexAttr;
static pthread_mutexattr_t    Engmnt_MutexAttr;
static pthread_cond_t         Engagement_cv;
static pthread_cond_t         Engagement_cv2;
static float                  xCorrect=60.0,yCorrect=-90.0;
static volatile bool          isConnected=false;
static Servo                  *Servos=NULL;
//static TMesssageNextTargetDiff CalMsg;
static unsigned char CalBuff[16];


#if USE_USB_WEB_CAM
cv::VideoCapture       * capture=NULL;
#else
static lccv::PiCamera  * capture=NULL;
#endif


static Mat NoDataAvalable;

static TTcpListenPort    *TcpListenPort=NULL;
static TTcpConnectedPort *TcpConnectedPort=NULL;

static void   Setup_Control_C_Signal_Handler_And_Keyboard_No_Enter(void);
static void   CleanUp(void);
static void   Control_C_Handler(int s);
static void   HandleInputChar(Mat &image);
static void * NetworkInputThread(void *data);
static void * EngagementThread(void *data); 
static void * SendJpegThread(void *data); 
static int    PrintfSend(const char *fmt, ...); 
static bool   GetFrame( Mat &frame);
static void   CreateNoDataAvalable(void);
static int    SendSystemState(SystemState_t State);
static bool   compare_float(float x, float y, float epsilon = 0.5f);
static float  ServoAngle(int Num,float &Angle) ;
static uint32_t sendFloat(float& number);
static int    SendSystemCalibrate();


//------------------------------------------------------------------------------------------------
// static void ReadOffsets
//------------------------------------------------------------------------------------------------
static void ReadOffsets(void)
{
	FILE * fp;
	float x,y;
	char xs[100],ys[100];
	int retval=0;

	fp = fopen ("Correct.ini", "r");
	retval+=fscanf(fp, "%s %f", xs,&x);
	retval+=fscanf(fp, "%s %f", ys,&y);
	if (retval==4)
	{
		if ((strcmp(xs,"xCorrect")==0) && (strcmp(ys,"yCorrect")==0))
		{
			xCorrect=x;
			yCorrect=y;
			CenterPan = xCorrect;
			CenterTilt = yCorrect;
			Pan = xCorrect;
			Tilt = yCorrect;
			//printf("Read Offsets:\n");
			//printf("xCorrect= %f\n",CenterPan);
			//printf("yCorrect= %f\n",CenterTilt);
		}
	}
	//cal.Pan = sendFloat(CenterPan);                                                                                                       cal.Tilt = sendFloat(CenterTilt); 
	fclose(fp);

}
//------------------------------------------------------------------------------------------------
// END  static void readOffsets
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void readOffsets
//------------------------------------------------------------------------------------------------
float receiveFloat(uint32_t num) {
	num = ntohl(num);
	float number;
	memcpy(&number, &num, sizeof(num));
	return number;
}

static void WriteOffsets(void)
{
	FILE * fp;
	float x,y;
	char xs[100],ys[100];
	int retval=0;

	fp = fopen ("Correct.ini", "w+");
	rewind(fp);
	fprintf(fp,"xCorrect %f\n", CenterPan);
	fprintf(fp,"yCorrect %f\n", CenterTilt);

	//printf("Wrote Offsets:\n");
	//printf("xCorrect= %f\n",CenterPan);
	//printf("yCorrect= %f\n",CenterTilt);
	fclose(fp);

}
//------------------------------------------------------------------------------------------------
// END  static void readOffsets
//------------------------------------------------------------------------------------------------

//------------------------------------------------------------------------------------------------
// static bool compare_float
//------------------------------------------------------------------------------------------------
static bool compare_float(float x, float y, float epsilon)
{
	if(fabs(x - y) < epsilon)
		return true; //they are same
	return false; //they are not same
}
//------------------------------------------------------------------------------------------------
// END static bool compare_float
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void ServoAngle
//------------------------------------------------------------------------------------------------
static float ServoAngle(int Num,float &Angle)     
{
	pthread_mutex_lock(&I2C_Mutex);
	if (Num==TILT_SERVO)
	{
		if (Angle< MIN_TILT) Angle=MIN_TILT; 
		else if (Angle > MAX_TILT) Angle=MAX_TILT; 
	}
	else if (Num==PAN_SERVO)
	{
		if (Angle< MIN_PAN) Angle = MIN_PAN;
		else if (Angle > MAX_PAN) Angle=MAX_PAN;
	}
	Servos->angle(Num,Angle);
	pthread_mutex_unlock(&I2C_Mutex);
	return Angle;
} 
//------------------------------------------------------------------------------------------------
// END static void ServoAngle
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void fire
//------------------------------------------------------------------------------------------------
static void fire(bool value)
{
	pthread_mutex_lock(&GPIO_Mutex);
	if (value) SystemState=(SystemState_t)(SystemState|FIRING);
	else SystemState=(SystemState_t)(SystemState & CLEAR_FIRING_MASK);
	lgGpioWrite(gpioid,17,value);
	pthread_mutex_unlock(&GPIO_Mutex) ;
}
//------------------------------------------------------------------------------------------------
// END static void fire
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void armed
//------------------------------------------------------------------------------------------------
static void armed(bool value)
{
	pthread_mutex_lock(&GPIO_Mutex);
	if (value) SystemState=(SystemState_t)(SystemState | ARMED);
	else SystemState=(SystemState_t)(SystemState & CLEAR_ARMED_MASK);
	pthread_mutex_unlock(&GPIO_Mutex);
}
//------------------------------------------------------------------------------------------------
// END static void armed
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void calibrate
//------------------------------------------------------------------------------------------------
static void calibrate(bool value)
{
	pthread_mutex_lock(&GPIO_Mutex);
	if (value) SystemState=(SystemState_t)(SystemState|CALIB_ON);
	else SystemState=(SystemState_t)(SystemState & CLEAR_CALIB_MASK);
	pthread_mutex_unlock(&GPIO_Mutex);
}
//------------------------------------------------------------------------------------------------
// END static void calibrate
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void laser
//------------------------------------------------------------------------------------------------
static void laser(bool value)
{
	pthread_mutex_lock(&GPIO_Mutex);
	if (value) 
		SystemState=(SystemState_t)(SystemState|LASER_ON);
	else SystemState=(SystemState_t)(SystemState & CLEAR_LASER_MASK);
	lgGpioWrite(gpioid,18, value);
	pthread_mutex_unlock(&GPIO_Mutex);
}
//------------------------------------------------------------------------------------------------
// END static void laser
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void ProcessTargetEngagements
//------------------------------------------------------------------------------------------------
static void ProcessTargetEngagements(TAutoEngage *Auto,int width,int height)
{

	bool NewState=false;

	switch(Auto->State)
	{
		case NOT_ACTIVE:
			break;
		case ACTIVATE:
			//printf("ACTIVATE \n");
			Auto->CurrentIndex=0;
			Auto->State=NEW_TARGET;

		case NEW_TARGET:
			//printf("start NEW_TARGET \n");
			//AutoEngage.Target=Auto->FiringOrder[Auto->CurrentIndex];
			Auto->StableCount=0;
			Auto->LastPan=-99999.99;
			Auto->LastTilt=-99999.99;
			NewState=true;
		case LOOKING_FOR_TARGET:
			printf("LOOKING_FOR_TARGET\n");
		case TRACKING:
			{
				int retval;
				TEngagementState state = LOOKING_FOR_TARGET;

			//	printf("Received.center.x,y :(%f,%f)\n", Pan, Tilt);

				ServoAngle(PAN_SERVO, Pan);
				ServoAngle(TILT_SERVO, Tilt);
				if (Pan == MAX_PAN || Pan == MIN_PAN || Tilt == MAX_TILT || Tilt == MIN_TILT) {
					SystemState = PREARMED;
					SendSystemState(SystemState);
					PrintfSend("Pan or Tilt reached min/max. Turn to PREARMED mode");
					return;
				}
				Auto->State = NOT_ACTIVE;
				state = NOT_ACTIVE;
			//	printf("state = TRACKING \n");

			}
			break;
		case ENGAGEMENT_IN_PROGRESS:
			{
//				printf("state == ENGAGEMENT_IN_PROGRESS \n");
			}
			break;      
		case ENGAGEMENT_COMPLETE:
			{
//				printf(" ENGAGEMENT_COMPLETE\n");
				Auto->State=NOT_ACTIVE;
				SystemState=PREARMED;
				SendSystemState(SystemState);
				PrintfSend("Target Completed");
				SendSystemState(SystemState);
			}
			break;  
		default: 
//			printf("Invaid State\n");
			break;    
	}
	return;
}
//------------------------------------------------------------------------------------------------
// END static void ProcessTargetEngagements
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void CreateNoDataAvalable
//------------------------------------------------------------------------------------------------
static void CreateNoDataAvalable(void)
{
	while (!GetFrame(NoDataAvalable)) printf("blank frame grabbed\n");    
	cv::String Text =format("NO DATA");

	int baseline;
	float FontSize=3.0; //12.0;
	int Thinkness=4;

	NoDataAvalable.setTo(cv::Scalar(128, 128, 128));
	Size TextSize= cv::getTextSize(Text, cv::FONT_HERSHEY_COMPLEX, FontSize,  Thinkness,&baseline); // Get font size

	int textX = (NoDataAvalable.cols- TextSize.width) / 2;
	int textY = (NoDataAvalable.rows + TextSize.height) / 2;
	putText(NoDataAvalable,Text,Point(textX , textY),cv::FONT_HERSHEY_COMPLEX,FontSize,Scalar(255,255,255),Thinkness*Thinkness,cv::LINE_AA);
	putText(NoDataAvalable,Text,Point(textX , textY),cv::FONT_HERSHEY_COMPLEX,FontSize,Scalar(0,0,0),Thinkness,cv::LINE_AA);
	//printf("frame size %d %d\n", NoDataAvalable.cols,NoDataAvalable.rows);
}
//------------------------------------------------------------------------------------------------
// END static void CreateNoDataAvalable
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static bool OpenCamera
//------------------------------------------------------------------------------------------------
static bool OpenCamera(void)
{
#if USE_USB_WEB_CAM
	capture=new cv::VideoCapture("/dev/video8",cv::CAP_V4L);
	if(!capture->isOpened()) {
		std::cout<<"Failed to open camera."<<std::endl;
		delete capture;
		return false;
	}

#else
	capture= new lccv::PiCamera();
	capture->options->video_width=WIDTH;
	capture->options->video_height=HEIGHT;
	capture->options->framerate=30;
	capture->options->verbose=true;
	capture->startVideo();
	usleep(500*1000);
#endif
	return(true);
}
//------------------------------------------------------------------------------------------------
// END static bool OpenCamera
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static bool GetFrame
//------------------------------------------------------------------------------------------------
static bool GetFrame(Mat &frame)
{
#if USE_USB_WEB_CAM
	// wait for a new frame from camera and store it into 'frame'
	capture->read(frame);
	// check if we succeeded
	if (frame.empty()) return(false);
#else
	if(!capture->getVideoFrame(frame,1000)) return(false);
#endif

	flip(frame, frame,-1);       // if running on PI5 flip(-1)=180 degrees

	return (true);
}
//------------------------------------------------------------------------------------------------
// END static bool GetFrame
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void CloseCamera
//------------------------------------------------------------------------------------------------
static void CloseCamera(void)
{
	if (capture!=NULL)  
	{
#if USE_USB_WEB_CAM
		capture->release();
#else    
		capture->stopVideo();
#endif 
		delete capture;
		capture=NULL;
	}
}
//------------------------------------------------------------------------------------------------
// END static void CloseCamera
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void OpenServos
//------------------------------------------------------------------------------------------------
static void OpenServos(void)
{
	Servos = new Servo(0x40, 0.750, 2.250);
}
//------------------------------------------------------------------------------------------------
// END static void OpenServos
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static bool CloseServos
//------------------------------------------------------------------------------------------------
static void CloseServos(void)
{
	if (Servos!=NULL)
	{
		delete Servos;
		Servos=NULL;
	}
}
//------------------------------------------------------------------------------------------------
// END static  CloseServos
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void OpenGPIO
//------------------------------------------------------------------------------------------------
static void OpenGPIO(void)
{
	gpioid = lgGpiochipOpen(4); //4 - PI 5
	lgGpioClaimOutput(gpioid,0,17,0); // Fire Cannon
	lgGpioClaimOutput(gpioid,0,18,0); // Laser
}
//------------------------------------------------------------------------------------------------
// END static void OpenGPIO
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void CloseGPIO
//------------------------------------------------------------------------------------------------
static void CloseGPIO(void)
{
	lgGpiochipClose(gpioid);
}
//------------------------------------------------------------------------------------------------
// END static void CloseGPIO
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static bool OLEDInit
//------------------------------------------------------------------------------------------------
static bool OLEDInit(void)
{
	uint8_t rc = 0;
	// open the I2C device node
	rc = ssd1306_init(i2c_node_address);

	if (rc != 0)
	{
		printf("no oled attached to /dev/i2c-%d\n", i2c_node_address);
		return (false);
	}
	rc= ssd1306_oled_default_config(64, 128);
	if (rc != 0)
	{
		printf("OLED DIsplay initialization failed\n");
		return (false);
	}
	rc=ssd1306_oled_clear_screen();
	if (rc != 0)
	{
		printf("OLED Clear screen Failed\n");
		return (false);

	}
	ssd1306_oled_set_rotate(0);
	ssd1306_oled_set_XY(0, 0);
	ssd1306_oled_write_line(OLED_Font, (char *) "READY");
	return(true); 
}
//------------------------------------------------------------------------------------------------
// END static bool OLEDInit
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void OLED_UpdateStatus
//------------------------------------------------------------------------------------------------
static void OLED_UpdateStatus(void)
{
	char Status[128];
	static SystemState_t LastSystemState=UNKNOWN;
	static SystemState_t LastSystemStateBase=UNKNOWN;
	SystemState_t SystemStateBase;
	if (!HaveOLED) return;
	pthread_mutex_lock(&I2C_Mutex);
	if (LastSystemState==SystemState)
	{
		pthread_mutex_unlock(&I2C_Mutex);
		return;
	}
	SystemStateBase=(SystemState_t)(SystemState & CLEAR_LASER_FIRING_ARMED_CALIB_MASK);
	if (SystemStateBase!=LastSystemStateBase)
	{
		LastSystemStateBase=SystemStateBase;
		ssd1306_oled_clear_line(0);  
		ssd1306_oled_set_XY(0, 0);
		if  (SystemStateBase==UNKNOWN)  strcpy(Status,"Unknown");
		else if  (SystemStateBase==SAFE)  strcpy(Status,"SAFE");
		else if  (SystemStateBase==PREARMED)  strcpy(Status,"PREARMED");
		else if  (SystemStateBase==ENGAGE_AUTO)  strcpy(Status,"ENGAGE AUTO");
		else if  (SystemStateBase==ARMED_MANUAL)  strcpy(Status,"ARMED_MANUAL");
		if (SystemState & ARMED) strcat(Status,"-ARMED");
		ssd1306_oled_write_line(OLED_Font, Status);
	}

	if((SystemState & LASER_ON)!=(LastSystemState & LASER_ON)||(LastSystemState==UNKNOWN))
	{
		ssd1306_oled_clear_line(1); 
		ssd1306_oled_set_XY(0, 1);
		if (SystemState & LASER_ON ) strcpy(Status,"LASER-ON");
		else strcpy(Status,"LASER-OFF");
		ssd1306_oled_write_line(OLED_Font, Status);
	}
	if((SystemState & FIRING)!=(LastSystemState & FIRING)||(LastSystemState==UNKNOWN))
	{
		ssd1306_oled_clear_line(2); 
		ssd1306_oled_set_XY(0, 2);
		if (SystemState & FIRING ) strcpy(Status,"FIRING-TRUE");
		else strcpy(Status,"FIRING-FALSE");
		ssd1306_oled_write_line(OLED_Font, Status);
	}
	LastSystemState=SystemState;
	pthread_mutex_unlock(&I2C_Mutex);
	return;
}
//------------------------------------------------------------------------------------------------
// END static void OLED_UpdateStatus
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void DrawCrosshair
//------------------------------------------------------------------------------------------------
/*static void DrawCrosshair(Mat &img, Point correct, const Scalar &color)
  {
// Use `shift` to try to gain sub-pixel accuracy
int shift = 10;
int m = pow(2, shift);

Point pt = Point((int)((img.cols/2-correct.x/2) * m), (int)((img.rows/2-correct.y/2) * m));

int size = int(10 * m);
int gap = int(4 * m);
line(img, Point(pt.x, pt.y-size), Point(pt.x, pt.y-gap), color, 1,LINE_8, shift);
line(img, Point(pt.x, pt.y+gap), Point(pt.x, pt.y+size), color, 1,LINE_8, shift);
line(img, Point(pt.x-size, pt.y), Point(pt.x-gap, pt.y), color, 1,LINE_8, shift);
line(img, Point(pt.x+gap, pt.y), Point(pt.x+size, pt.y), color, 1,LINE_8, shift);
line(img, pt, pt, color, 1,LINE_8, shift);
}*/
//------------------------------------------------------------------------------------------------
// END static void DrawCrosshair
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// main - This is the main program for the Gel Cannon and contains the control loop
//------------------------------------------------------------------------------------------------
int main(int argc, const char** argv)
{

	std::signal(SIGPIPE, SIG_IGN);
	float test1, test2;
	if (argc < 3) {
		Pan = 10.0f;
		Tilt = 0.0f;
		CenterPan = 10.0f;
		CenterTilt = 0.0f;
	} else {
		Pan = std::stof(argv[1]);
		Tilt = std::stof(argv[2]);
		CenterPan =  std::stof(argv[1]);
		CenterTilt =  std::stof(argv[2]);
	}
	while(1) {

		Mat                              Frame,ResizedFrame;      // camera image in Mat format 
		float                            avfps=0.0,FPS[16]={0.0,0.0,0.0,0.0,
			0.0,0.0,0.0,0.0,
			0.0,0.0,0.0,0.0,
			0.0,0.0,0.0,0.0};
		int                              retval,i,Fcnt = 0;
		struct sockaddr_in               cli_addr;
		socklen_t                        clilen;
		chrono::steady_clock::time_point Tbegin, Tend;

		ReadOffsets();

		AutoEngage.HaveFiringOrder=false;
		AutoEngage.NumberOfTartgets=0;
		AutoEngage.State=NOT_ACTIVE;

		pthread_mutexattr_init(&TCP_MutexAttr);
		pthread_mutexattr_settype(&TCP_MutexAttr, PTHREAD_MUTEX_RECURSIVE);
		pthread_mutexattr_init(&GPIO_MutexAttr);
		pthread_mutexattr_settype(&GPIO_MutexAttr, PTHREAD_MUTEX_RECURSIVE);
		pthread_mutexattr_init(&I2C_MutexAttr);
		pthread_mutexattr_settype(&I2C_MutexAttr, PTHREAD_MUTEX_RECURSIVE);
		pthread_mutexattr_init(&Engmnt_MutexAttr);
		pthread_mutexattr_settype(&Engmnt_MutexAttr, PTHREAD_MUTEX_ERRORCHECK);

		if (pthread_mutex_init(&TCP_Mutex, &TCP_MutexAttr)!=0) return -1;
		if (pthread_mutex_init(&GPIO_Mutex, &GPIO_MutexAttr)!=0) return -1; 
		if (pthread_mutex_init(&I2C_Mutex, &I2C_MutexAttr)!=0) return -1; 
		if (pthread_mutex_init(&Engmnt_Mutex, &Engmnt_MutexAttr)!=0) return -1; 

		HaveOLED=OLEDInit();

		if  ((TcpListenPort=OpenTcpListenPort(PORT))==NULL)  // Open UDP Network port
		{
			printf("OpenTcpListenPortFailed\n");
			return(-1);
		}

		OpenGPIO();
		laser(false);
		fire(false);
		calibrate(false);

		OpenServos();
		ServoAngle(PAN_SERVO, CenterPan);
		ServoAngle(TILT_SERVO, CenterTilt);

		//SendSystemCalibrate();
		Setup_Control_C_Signal_Handler_And_Keyboard_No_Enter(); // Set Control-c handler to properly exit clean

	//	printf("Listening for connections\n");
		clilen = sizeof(cli_addr);
		if  ((TcpConnectedPort=AcceptTcpConnection(TcpListenPort,&cli_addr,&clilen))==NULL)
		{
			printf("AcceptTcpConnection Failed\n");
			return(-1);
		}
		isConnected=true;
	//	printf("Accepted connection Request\n");
		CloseTcpListenPort(&TcpListenPort);  // Close listen port

		if (!OpenCamera())
		{
			printf("Could not Open Camera\n");
			return(-1);
		}
		else 
	//		printf("Opened Camera\n");
		CreateNoDataAvalable();

		if (pthread_create(&NetworkThreadID, NULL,NetworkInputThread, NULL)!=0)
		{
			printf("Failed to Create Network Input Thread\n");
			exit(0);
		}
		if (pthread_create(&EngagementThreadID, NULL,EngagementThread, NULL)!=0)
		{
			printf("Failed to Create ,Engagement Thread\n");
			exit(0);
		}

		do
		{
			if (!GetFrame(Frame))
			{
				printf("ERROR! blank frame grabbed\n");
				continue;
			}
			HandleInputChar(Frame);

			ProcessTargetEngagements(&AutoEngage,960,554);
			resize(Frame, ResizedFrame, Size(960, 544));


			if ((isConnected) && (TcpSendImageAsJpeg(TcpConnectedPort,ResizedFrame)<0)) {
				printf("Main Thread Exiting 1\n");
				break;
			}

		} while (isConnected);
		printf("Main Thread Exiting\n");
		SystemState= SAFE;
		CenterPan = 10.0f;
		CenterTilt = 0.0f;
		Pan = 10.0f;
		Tilt = 0.0f;
		RunCmds=0;
		gpioid;
		i2c_node_address = 1;
		HaveOLED=false;
		OLED_Font=0;
		NetworkThreadID=-1;
		EngagementThreadID=-1;
		SendImageThreadID=-1;
		SystemState= SAFE;
		Engmnt_MutexAttr;
		Engagement_cv;
		xCorrect=60.0,yCorrect=-90.0;
		isConnected=false;
		Servos=NULL;
		CleanUp();
	}
	printf("Program here to normal exit\n");

	return 0;
}
//------------------------------------------------------------------------------------------------
// End main
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void * EngagementThread
//------------------------------------------------------------------------------------------------
static void * EngagementThread(void *data) 
{
	int ret;
	while (1) {
		if ((ret = pthread_mutex_lock(&Engmnt_Mutex)) != 0) {

			printf("Engmnt_Mutex ERROR\n");
			break;
		}
	//	printf("Waiting for Engagement Order\n");
		if ((ret = pthread_cond_wait(&Engagement_cv, &Engmnt_Mutex)) != 0) {
			printf("Engagement  pthread_cond_wait ERROR\n");
			break;

		}

	//	printf("Engagment in Progress SystemState : %d\n", (int)SystemState);
		PrintfSend("Engaged, send system state %d\n", (int) SystemState);
		laser(true);
		//SendSystemState(SystemState);
		usleep(1500*1000);
		fire(true);

		AutoEngage.HaveFiringOrder=false;


		SendSystemState(SystemState);
		usleep(200*1000);
		fire(false);
		laser(false);
		armed(false);
		PrintfSend("Engaged Target %d",AutoEngage.Target);
		SendSystemState((SystemState_t)MT_COMPLETE);
		AutoEngage.State=NOT_ACTIVE;
		if ((ret = pthread_cond_signal(&Engagement_cv2)) != 0)
		{		printf("pthread_cond_signal Error\n");																	                                       exit(0);

		}

		if ((ret = pthread_mutex_unlock(&Engmnt_Mutex)) != 0) 
		{
			printf("Engagement pthread_cond_wait ERROR\n");
			break;
		}
	}

	return NULL;
}
//------------------------------------------------------------------------------------------------
// END static void * EngagementThread
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static int PrintfSend
//------------------------------------------------------------------------------------------------
static int PrintfSend(const char *fmt, ...) 
{
	char Buffer[2048];
	int  BytesWritten;
	int  retval;
	pthread_mutex_lock(&TCP_Mutex); 
	va_list args;
	va_start(args, fmt);
	BytesWritten=vsprintf(Buffer,fmt, args);
	va_end(args);
	if (BytesWritten>0)
	{
		TMesssageHeader MsgHdr;
		BytesWritten++;
		MsgHdr.Len=htonl(BytesWritten);
		MsgHdr.Type=htonl(MT_TEXT);
		if (WriteDataTcp(TcpConnectedPort,(unsigned char *)&MsgHdr, sizeof(TMesssageHeader))!=sizeof(TMesssageHeader)) 
		{
			pthread_mutex_unlock(&TCP_Mutex);
			return (-1);
		}
		retval=WriteDataTcp(TcpConnectedPort,(unsigned char *)Buffer,BytesWritten);
		pthread_mutex_unlock(&TCP_Mutex);
		return(retval);
	}
	else 
	{
		pthread_mutex_unlock(&TCP_Mutex);
		return(BytesWritten);
	}
}
//------------------------------------------------------------------------------------------------
// END static int PrintfSend
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static int SendSystemState
//------------------------------------------------------------------------------------------------
static int SendSystemState(SystemState_t State)
{
	TMesssageSystemState StateMsg;
	int                  retval;
	pthread_mutex_lock(&TCP_Mutex);
	StateMsg.State=(SystemState_t)htonl(State);
	StateMsg.Hdr.Len=htonl(sizeof(StateMsg.State));
	StateMsg.Hdr.Type=htonl(MT_STATE);
	OLED_UpdateStatus();
	retval=WriteDataTcp(TcpConnectedPort,(unsigned char *)&StateMsg,sizeof(TMesssageSystemState));
	pthread_mutex_unlock(&TCP_Mutex);
	return(retval);
} 
//------------------------------------------------------------------------------------------------
// END static int SendSystemState
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void ProcessPreArm
//------------------------------------------------------------------------------------------------
static void ProcessPreArm(char * Code)
{
	char Decode[]={0x61,0x60,0x76,0x75,0x67,0x7b,0x72,0x7c};
	size_t len = strlen(Code);
	for (int i = 0; i < len; i++) {
		printf("%02x", Code[i]); }

	if (SystemState==SAFE)
	{
		if ((Code[sizeof(Decode)]==0) && (strlen(Code)==sizeof(Decode)))
		{ 
			for (int i=0;i<sizeof(Decode);i++) Code[i]^=Decode[i];
			if (strcmp((const char*)Code,"PREARMED")==0)
			{
				SystemState=PREARMED;
				SendSystemState(SystemState);
SendSystemCalibrate();
				printf("passed");
			} 
		}
	}
}
//------------------------------------------------------------------------------------------------
// END static void ProcessPreArm
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void ProcessStateChangeRequest
//------------------------------------------------------------------------------------------------
static void ProcessStateChangeRequest(SystemState_t state)
{  
	static bool CalibrateWasOn=false;
	switch(state&CLEAR_LASER_FIRING_ARMED_CALIB_MASK)
	{
		case SAFE:
			{
				printf("SAFE\n");
				laser(false);
				calibrate(false);
				fire(false);
				//SystemState=(SystemState_t)(state & CLEAR_LASER_FIRING_ARMED_CALIB_MASK);
				SystemState=state;
				AutoEngage.State=NOT_ACTIVE;
				AutoEngage.HaveFiringOrder=false;
				AutoEngage.NumberOfTartgets=0;
			}
			break;
		case PREARMED:
			{ 
				printf("PREARMED\n");
				if (((SystemState&CLEAR_LASER_FIRING_ARMED_CALIB_MASK)==ENGAGE_AUTO) || 
						((SystemState&CLEAR_LASER_FIRING_ARMED_CALIB_MASK)==ARMED_MANUAL))
				{
					//laser(false);
					fire(false);
					calibrate(false);
					if ((SystemState&CLEAR_LASER_FIRING_ARMED_CALIB_MASK)==ENGAGE_AUTO)
					{
						AutoEngage.State=NOT_ACTIVE;
						AutoEngage.HaveFiringOrder=false;
						AutoEngage.NumberOfTartgets=0;
					}
					//SystemState=(SystemState_t)(state & CLEAR_LASER_FIRING_ARMED_CALIB_MASK);
					SystemState=state;
					SendSystemState(SystemState);
				}
			}
			break;

		case ENGAGE_AUTO:
			{
	//			printf("ENGAGE_AUTO\n");
				{
	//				printf("Activate\n");
					PrintfSend("Activate");
					calibrate(false);
					fire(false);
					SystemState=state;
					AutoEngage.State=ACTIVATE;
				}
			}
			break;
		case ARMED_MANUAL:
			{
	//			printf("ARMED_MANUAL\n");
				if ((SystemState&CLEAR_LASER_FIRING_ARMED_CALIB_MASK)==PREARMED)
				{
					laser(false);
					calibrate(false);
					fire(false);
					SystemState=(SystemState_t)(state & CLEAR_LASER_FIRING_ARMED_CALIB_MASK);
				}
				else {

					SystemState=state;
					SendSystemState(SystemState);
				}

			}
			break;
		default:
			{
	//			printf("UNKNOWN STATE REQUEST %d\n",state);
			}
			break;

	}

	if (SystemState & LASER_ON) { 
		laser(true);
	} else { laser(false);
	}

	if (SystemState & CALIB_ON)  
	{
		calibrate(true);
		CalibrateWasOn=true;
	}
	else 
	{
		calibrate(false);
		if (CalibrateWasOn) 
		{
			CalibrateWasOn=false;
	//		printf ("final offset is (%f, %f)\n", CenterPan, CenterTilt);
			WriteOffsets();
			SendSystemCalibrate();
		}
	}

	SendSystemState(SystemState);
}
//------------------------------------------------------------------------------------------------
// END static void ProcessStateChangeRequest
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void ProcessFiringOrder
//------------------------------------------------------------------------------------------------
/*
   static void ProcessFiringOrder(char * FiringOrder)
   {
   int len=strlen(FiringOrder);

   AutoEngage.State=NOT_ACTIVE;
   AutoEngage.HaveFiringOrder=false;
   AutoEngage.NumberOfTartgets=0;
   AutoEngage.Target=0;

   if (len>10) 
   {
   printf("Firing order error\n");
   return; 
   }
   for (int i=0;i<len;i++)
   {
   AutoEngage.FiringOrder[i]=FiringOrder[i]-'0';
   printf("firing order : %d\n", AutoEngage.FiringOrder[i]);
   }
   if (len>0)  AutoEngage.HaveFiringOrder=true;
   AutoEngage.NumberOfTartgets=len; 
   printf("Firing order\n");
   for (int i=0;i<len;i++) printf("%d\n",AutoEngage.FiringOrder[i]);
   printf("\n\n");
   }*/
//------------------------------------------------------------------------------------------------
// END static void ProcessFiringOrder
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void ProcessCommands
//------------------------------------------------------------------------------------------------
static void ProcessCommands(unsigned char cmd)
{
	if (((SystemState & CLEAR_LASER_FIRING_ARMED_CALIB_MASK)!=PREARMED) &&
			((SystemState & CLEAR_LASER_FIRING_ARMED_CALIB_MASK)!=ARMED_MANUAL))
	{
		printf("received Commands outside of Pre-Arm or Armed Manual State %x \n",cmd);
		return;
	} 
	if (((cmd==FIRE_START) || (cmd==FIRE_STOP)) && ((SystemState & CLEAR_LASER_FIRING_ARMED_CALIB_MASK)!=ARMED_MANUAL))
	{
		printf("received Fire Commands outside of Armed Manual State %x \n",cmd);
		return;
	} 


	//printf("%c\n", cmd);
	switch(cmd)
	{
		case PAN_LEFT_START:
			RunCmds|=PAN_LEFT_START;
			RunCmds&=PAN_RIGHT_STOP;
			Pan+=INC;
			Pan = ServoAngle(PAN_SERVO, Pan);
			break;
		case PAN_RIGHT_START:
			RunCmds|=PAN_RIGHT_START;
			RunCmds&=PAN_LEFT_STOP;
			Pan-=INC;
			Pan = ServoAngle(PAN_SERVO, Pan);
			break;
		case PAN_UP_START:
			RunCmds|=PAN_UP_START;
			RunCmds&=PAN_DOWN_STOP;
			Tilt+=INC; 
			Tilt = ServoAngle(TILT_SERVO, Tilt);
			break;
		case PAN_DOWN_START:
			RunCmds|=PAN_DOWN_START;
			RunCmds&=PAN_UP_STOP;
			Tilt-=INC; 
			Tilt = ServoAngle(TILT_SERVO, Tilt);
			break;
		case FIRE_START:
			RunCmds|=FIRE_START;
			fire(true);
			SendSystemState(SystemState);
			break;   
		case PAN_LEFT_STOP:
			RunCmds&=PAN_LEFT_STOP;
			break;
		case PAN_RIGHT_STOP:
			RunCmds&=PAN_RIGHT_STOP;
			break;
		case PAN_UP_STOP:
			RunCmds&=PAN_UP_STOP;
			break;
		case PAN_DOWN_STOP:
			RunCmds&=PAN_DOWN_STOP;
			break;
		case FIRE_STOP: 
			RunCmds&=FIRE_STOP;
			fire(false);
			SendSystemState(SystemState);
			break;
		default:
			printf("invalid command %x\n",cmd);
			break;
	}
	if (Pan == MAX_PAN || Pan == MIN_PAN || Tilt == MAX_TILT || Tilt == MIN_TILT) {
		SystemState = PREARMED;
		SendSystemState(SystemState);
		PrintfSend("Pan or Tilt reached min/max. Turn to PREARMED mode");
	}
	if (SystemState & CALIB_ON) {
		CenterPan = Pan;
		CenterTilt = Tilt;	
	}

}
//------------------------------------------------------------------------------------------------
static uint32_t sendFloat(float& number) {
	uint32_t net_number;
	memcpy(&net_number, &number, sizeof(number));
	uint32_t net_number2 = htonl(net_number);
	return net_number2;
}
// END static void ProcessCommands
//------------------------------------------------------------------------------------------------
static int SendSystemCalibrate()
{
//	printf("Sent Previously set calibration data : %f, %f\n",CenterPan,CenterTilt);
	TMesssageCal CalMsg;

	int               retval;
	pthread_mutex_lock(&TCP_Mutex);
	CalMsg.Pan = sendFloat(CenterPan);
	CalMsg.Tilt = sendFloat(CenterTilt);
//	printf("converted pan, tilt : %u %u\n", CalMsg.Pan, CalMsg.Tilt);
//	printf("re-converted pan, tilt : %f %f\n", receiveFloat(CalMsg.Pan), receiveFloat(CalMsg.Tilt));

	CalMsg.Hdr.Len=htonl(sizeof(uint32_t)*2);
	CalMsg.Hdr.Type=htonl(MT_CALIB_COMMANDS);
	memcpy(&CalBuff[0], &CalMsg, sizeof(TMesssageCal));
	/*for (int i = 0; i < sizeof(TMesssageCal); i++)  {
		printf("%02x\n", CalBuff[i]);
	}*/

	retval=WriteDataTcp(TcpConnectedPort, (unsigned char *)&CalBuff[0], sizeof(TMesssageCal));
	pthread_mutex_unlock(&TCP_Mutex);
	return(retval); 
}
//------------------------------------------------------------------------------------------------
// static void ProcessCalibCommands
//------------------------------------------------------------------------------------------------
static void ProcessCalibCommands(unsigned char cmd)
{
	if (((SystemState & CLEAR_LASER_FIRING_ARMED_CALIB_MASK)!=PREARMED) &&
			((SystemState & CLEAR_LASER_FIRING_ARMED_CALIB_MASK)!=ARMED_MANUAL) &&
			!(SystemState & CALIB_ON))
	{
		printf("received Commands outside of Armed Manual State %x \n",cmd);
		return;
	} 

	switch(cmd)
	{
		case DEC_X:
			xCorrect++;
			break;
		case INC_X:
			xCorrect--;
			break;
		case DEC_Y:
			yCorrect--;
			break;
		case INC_Y:
			yCorrect++;
			break;
		default:
			printf("invalid command %x\n",cmd);
			break;
	}

}



//------------------------------------------------------------------------------------------------
// END static void ProcessCalibCommands
//------------------------------------------------------------------------------------------------
//------------------------------------------------------------------------------------------------
// static void *NetworkInputThread
//------------------------------------------------------------------------------------------------
static void *NetworkInputThread(void *data)
{
//	printf("*NetworkInputThread start\n");
	unsigned char Buffer[512];
	TMesssageHeader *MsgHdr;
	int fd=TcpConnectedPort->ConnectedFd,retval;

	SendSystemState(SystemState);
//	printf("sizeof TMesssageHeader %d\n", (int)  sizeof(TMesssageHeader));

	while (1)
	{
		try{
			if ((retval=recv(fd, &Buffer, sizeof(TMesssageHeader),0)) != sizeof(TMesssageHeader)) 
			{
				if (retval==0) {
					printf("Client Disconnnected\n");
				} else { 
					printf("Connecton Lost %s  %d\n", strerror(errno), sizeof(TMesssageHeader), strlen((char*)Buffer));
				}
				break;
			}
		} catch (std::exception e) {
			printf("exception occur in demo\n");
			break;
		}
		MsgHdr=(TMesssageHeader *)Buffer;
		MsgHdr->Len = ntohl(MsgHdr->Len);
		MsgHdr->Type = ntohl(MsgHdr->Type);
//		printf("received MsgHdr->Type %02x\n", MsgHdr->Type);

		if (MsgHdr->Len+sizeof(TMesssageHeader)>sizeof(Buffer))
		{
			printf("oversized message error %d\n",MsgHdr->Len);
			break;
		}
		try {
			if ((retval=recv(fd, &Buffer[sizeof(TMesssageHeader)],  MsgHdr->Len,0)) !=  MsgHdr->Len) 
			{
				if (retval==0) 
					printf("Client Disconnnected\n");
				else 
					printf("Connecton Lost %s\n", strerror(errno));
				break;
			}
		} catch (std::exception e) {
			printf("exception occur in demo\n");
			break;
		}

		switch(MsgHdr->Type)
		{
			case MT_COMMANDS: 
				{
					printf("MT_COMMANDS\n");
					TMesssageCommands *msgCmds=(TMesssageCommands *)Buffer;
					ProcessCommands(msgCmds->Commands);
				}
				break;
			case MT_CALIB_COMMANDS: 
				{
					printf("MT_CALIB_COMMANDS\n");
					TMesssageCalibCommands *msgCmds=(TMesssageCalibCommands *)Buffer;
					ProcessCalibCommands(msgCmds->Commands);
				}
				break;

			case MT_TARGET_SEQUENCE: 
				{
					printf("MT_TARGET_SEQUENCE\n");
					TMesssageTargetOrder *msgTargetOrder=(TMesssageTargetOrder *)Buffer;
					//ProcessFiringOrder(msgTargetOrder->FiringOrder);
				}
				break;
			case MT_PREARM: 
				{
					printf("MT_PREARM \n");
					TMesssagePreArm *msgPreArm=(TMesssagePreArm *)Buffer;
					ProcessPreArm(msgPreArm->Code);
				}
				break;
			case MT_STATE_CHANGE_REQ: 
				{
					printf(" MT_STATE_CHANGE_REQ\n");
					TMesssageChangeStateRequest *msgChangeStateRequest=(TMesssageChangeStateRequest *)Buffer;
					msgChangeStateRequest->State=(SystemState_t)ntohl(msgChangeStateRequest->State);

					ProcessStateChangeRequest(msgChangeStateRequest->State);
				}
				break;
			case MT_TARGET_DIFF:
				{
					int ret;
					if (SystemState == PREARMED) {
						printf("Invalid state\n");
						break;
					}
					if (AutoEngage.HaveFiringOrder) {
						if (ret = pthread_cond_wait(&Engagement_cv2, &Engmnt_Mutex2) != 0) {
							printf("Engagement  pthread_cond_wait ERROR\n");
							break;
						}
					}
					printf("MT_NEXT_TARGET_DIFF\n");
					TMesssageNextTargetDiff *msgNextTargetDiff = (TMesssageNextTargetDiff *)Buffer;
					printf("before receive Pan : %u, Tilt : %u\n", msgNextTargetDiff->Servos.Pan, msgNextTargetDiff->Servos.Tilt);
					Pan = receiveFloat(msgNextTargetDiff->Servos.Pan);
					Tilt = receiveFloat(msgNextTargetDiff->Servos.Tilt);
					printf("receive Pan : %f, Tilt : %f\n", Pan, Tilt);
					ProcessStateChangeRequest(ENGAGE_AUTO);
				}
				break;
			case MT_COMPLETE :
				{
					printf("MT_COMPLETE\n");
					AutoEngage.State=ENGAGEMENT_COMPLETE;
				}
				break;
			case MT_FIRE :
				{
					printf("MT_FIRE\n");
					AutoEngage.State = ENGAGEMENT_IN_PROGRESS;
					AutoEngage.HaveFiringOrder=true;
//					printf("Signaling Engagement\n");
					if ((retval = pthread_cond_signal(&Engagement_cv)) != 0)
					{
						printf("pthread_cond_signal Error\n");
						exit(0);
					}
				}
				break;
			case MT_GO_CENTER :
				{
					int ret;

					if (AutoEngage.HaveFiringOrder) {
						if (ret = pthread_cond_wait(&Engagement_cv2, &Engmnt_Mutex2) != 0) {
							printf("Engagement  pthread_cond_wait ERROR\n");
							break;
						}
					}
					Pan = CenterPan;
					Tilt = CenterTilt;
					printf("MT_GO_CENTER (%f,%f) \n", Pan, Tilt);
					ServoAngle(PAN_SERVO, Pan);
					ServoAngle(TILT_SERVO, Tilt);
				}
				break;
			default:
				printf("Invalid Message Type\n");
				break; 
		}
	}
	isConnected=false;
	NetworkThreadID=-1; // Temp Fix OS probem determining if thread id are valid
	printf("Network Thread Exit\n");
	return NULL;
}
//------------------------------------------------------------------------------------------------
// END static void *NetworkInputThread
//------------------------------------------------------------------------------------------------
//----------------------------------------------------------------
// Setup_Control_C_Signal_Handler_And_Keyboard_No_Enter - This 
// sets uo the Control-c Handler and put the keyboard in a mode
// where it will not
// 1. echo input
// 2. need enter hit to get a character 
// 3. block waiting for input
//-----------------------------------------------------------------
static void Setup_Control_C_Signal_Handler_And_Keyboard_No_Enter(void)
{
	struct sigaction sigIntHandler;
	sigIntHandler.sa_handler = Control_C_Handler; // Setup control-c callback 
	sigemptyset(&sigIntHandler.sa_mask);
	sigIntHandler.sa_flags = 0;
	sigaction(SIGINT, &sigIntHandler, NULL);
	ConfigKeyboardNoEnterBlockEcho();             // set keyboard configuration
}
//-----------------------------------------------------------------
// END Setup_Control_C_Signal_Handler_And_Keyboard_No_Enter
//-----------------------------------------------------------------
//----------------------------------------------------------------
// CleanUp - Performs cleanup processing before exiting the
// the program
//-----------------------------------------------------------------
static void CleanUp(void)
{
	void *res;
	int s;

	RestoreKeyboard();                // restore Keyboard
	if (NetworkThreadID!=-1)
	{
		s = pthread_cancel(NetworkThreadID);
		if (s!=0)  printf("Network Thread Cancel Failure\n");

		s = pthread_join(NetworkThreadID, &res);
		if (s != 0)   printf("Network Thread Join Failure\n"); 

		if (res == PTHREAD_CANCELED)
			printf("Network Thread canceled\n"); 
		else
			printf("Network Thread was not canceled\n"); 
	}
	if (EngagementThreadID!=-1)
	{
		s = pthread_cancel(EngagementThreadID);
		if (s!=0)  printf("Engagement Thread Cancel Failure\n");

		s = pthread_join(EngagementThreadID, &res);
		if (s != 0)   printf("Engagement  Thread Join Failure\n"); 

		if (res == PTHREAD_CANCELED)
			printf("Engagement Thread canceled\n"); 
		else
			printf("Engagement Thread was not canceled\n"); 
	}

	CloseCamera();
	CloseServos();

	laser(false);
	fire(false);
	calibrate(false);
	CloseGPIO();

	CloseTcpConnectedPort(&TcpConnectedPort); // Close network port;

	if (HaveOLED) ssd1306_end();
	printf("CleanUp Complete\n");
}
//-----------------------------------------------------------------
// END CleanUp
//-----------------------------------------------------------------
//----------------------------------------------------------------
// Control_C_Handler - called when control-c pressed
//-----------------------------------------------------------------
static void Control_C_Handler(int s)
{
	printf("Caught signal %d\n",s);
	CleanUp();
	printf("Exiting\n");
	exit(1);
}
//-----------------------------------------------------------------
// END Control_C_Handler
//-----------------------------------------------------------------
//----------------------------------------------------------------
// HandleInputChar - check if keys are press and proccess keys of
// interest.
//-----------------------------------------------------------------
static void HandleInputChar( Mat &frame)
{
	int ch;
	static unsigned int ImageCount=0;

	if ((ch=getchar())!=EOF) 
	{
		if  (ch=='s')
		{
			char String[1024];
			ImageCount++;
			sprintf(String,"images/Capture%d.jpg",ImageCount);
			imwrite(String, frame);
			printf("saved %s\n", String);
		}

	}
}
//-----------------------------------------------------------------
// END HandleInputChar
//-----------------------------------------------------------------
//-----------------------------------------------------------------
// END of File
//-----------------------------------------------------------------

