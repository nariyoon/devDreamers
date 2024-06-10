/********************************************************************************
@file		LGDisplayNewForm.cs
@auther		DevDremers at CMU
@biref		Main Form file
@detail		Main Form file
@version	0.01.00
@date	    2024.06.11
@history	
@copyright  No copyright
*********************************************************************************/
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Net.Sockets;
using System.Net;
using System.Text;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Threading;
using OpenCvSharp;

namespace LGClientDisplayNew
{
    public partial class Form1 : Form
    {
        /// Public Member Variables are defined here
        // Define critical section - LockSocketComm : lock(LockSocketComm) {  // critical section 으로 사용 ... }
        public object LockSocketComm = new object();

        /// Private Member Variables are defined here
        private string[] strModeSelect = { "", "Armed Manual", "Auto Engage", "Calibration" };
        private const Int32 HEARTBEAT_TIMER_INTERVAL = 1000; // 1000 msec = 1 sec
        private const string DEFAULT_IP_ADDR = "127.0.0.1";
        private const string DEFAULT_TCP_PORT = "5000";

        private ClientSocket clientThread;

        /********************************************************************************
        @brief      Constructor of Mainform
        @detail     Constructor of Mainform
        @param[in]  none
        @return     none
        @exception  none
        @remark
        *********************************************************************************/
        public Form1()
        {
            InitializeComponent();
        }

        /********************************************************************************
        @brief      Initilize when form loaded
        @detail     Initilize when form loaded
        @param[in]  sender - event object
        @param[in]  e - event arguments
        @return     void
        @exception  none
        @remark
        *********************************************************************************/
        private void Form1_Load(object sender, EventArgs e)
        {
            /// Initialize User Control of View
            TxtRcsIpAddr.Text = DEFAULT_IP_ADDR;
            TxtRcsTcpPort.Text = DEFAULT_TCP_PORT;
            BtnDiscon.Enabled = false;

            // After connecting to server, controls are enabled 
            TxtCurrentRcsState.Text = "Unknown";
            TxtCurrentRcsState.Enabled = false;
            TxtRcsPasswd.Enabled = false;
            BtnPreArmedSetup.Enabled = false;

            GbxRcsEngageCalControl.Visible = false;
            //LblAutoEngageList.Visible = false;
            //TxtAutoEngageList.Visible = false;

            //BtnUpIncY.Visible = false;
            //BtnDownDecY.Visible = false;
            //BtnRightIncX.Visible = false; 
            //BtnLeftDecX.Visible = false;
            //BtnFire.Visible = false;

            //BtnFireCancel.Visible = false;

            CmbModeSelect.DataSource = strModeSelect;
            CmbModeSelect.SelectedIndex = 0;



            /// Initialize ViewModel including ClientSocket
            clientThread = new ClientSocket(this);




            /// Initialize Model variables



        }

        /********************************************************************************
        @brief      Terminate when form closed
        @detail     Terminate when form closed
        @param[in]  sender - event object
        @param[in]  e - event arguments
        @return     void
        @exception  none
        @remark
        *********************************************************************************/

        private void Form1_FormClosed(object sender, FormClosedEventArgs e)
        {
            // HeartBeat Timer 동작하는 경우 정지
            if (TmrHeartBeatRequest.Enabled == true)
            {
                TmrHeartBeatRequest.Enabled = false;
            }

            Thread.Sleep(500); // TCP 스레드 종료까지 0.5초 대기
            // 열려있는 TCP가 존재하는 경우 정지
            if (clientThread.FlagTcpPortRunning == true)
            {
                clientThread.FlagTcpPortRunning = false;
            }
            Thread.Sleep(500); // TCP 스레드 종료까지 0.5초 대기
        }

        /********************************************************************************
        @brief      Connect to Server by Client Socket
        @detail     Connect to Server by Client Socket
        @param[in]  sender - event object
        @param[in]  e - event arguments
        @return     void
        @exception  exception related to socket
        @remark
        *********************************************************************************/
        private void ConnBtn_Click(object sender, EventArgs e)
        {
            String  strClientIp = "";
            Int32   nClientPort = 0;

            try
            {
                strClientIp = TxtRcsIpAddr.Text.ToString();
                nClientPort = Convert.ToInt32(TxtRcsTcpPort.Text);

                TcpClient clientTcpSocket = new TcpClient();
                clientThread.startTcpClient(clientTcpSocket, strClientIp, nClientPort);
            }
            catch (Exception ex)
            {   
            }
            
            // For the well-binded case, if statements are running
            if (clientThread.IsEthernetPortUsed == true)
            {
                //// 이더넷 포트 연결시 RCS 동작 여부를 확인할 Heartbeat 타이머 구동
                // Set Timer Interval and run the timer
                TmrHeartBeatRequest.Interval = HEARTBEAT_TIMER_INTERVAL; // 1000 msec = 1 sec
                TmrHeartBeatRequest.Enabled = true;

                // Control View controls for ClientSocket 
                BtnConn.Enabled = false;
                BtnDiscon.Enabled = true;

                // Set Pre-armed mode to start
                TxtCurrentRcsState.Text = Convert.ToString("Safe");
                TxtRcsPasswd.Enabled = true;
                BtnPreArmedSetup.Enabled = true;

                // Show the example cv image to the picturebox 
                // 이미지 파일 경로
                string imagePath = "../../test.jpg";

                // 이미지 파일을 바이트 배열로 읽어옴
                byte[] imageBytes = System.IO.File.ReadAllBytes(imagePath);

                // 바이트 배열을 Mat으로 디코딩
                Mat matImg = Cv2.ImDecode(imageBytes, ImreadModes.Unchanged);

                // Mat을 Bitmap으로 변환
                // Bitmap bitmap = OpenCvSharp.Extensions.BitmapConverter.ToBitmap(matImg);

                // 이미지 출력
                PictureBoxRcsVideo.Image = OpenCvSharp.Extensions.BitmapConverter.ToBitmap(matImg);
            }
            else
            {
                MessageBox.Show("TCP/IP binding error.", "Error");
            }
        }

        /********************************************************************************
        @brief      Disconnect to Server
        @detail     Disconnect to Server
        @param[in]  sender - event object
        @param[in]  e - event arguments
        @return     void
        @exception  exception related to socket
        @remark
        *********************************************************************************/
        private void DisconBtn_Click(object sender, EventArgs e)
        {
            // HeartBeat Timer 동작하는 경우 정지
            if (TmrHeartBeatRequest.Enabled == true)
            {
                TmrHeartBeatRequest.Enabled = false;
            }
            
            Thread.Sleep(500); // TCP 스레드 종료까지 0.5초 대기
            // 열려있는 TCP가 존재하는 경우 정지
            if (clientThread.FlagTcpPortRunning == true)
            {
                clientThread.FlagTcpPortRunning = false;
            }
            Thread.Sleep(500); // TCP 스레드 종료까지 0.5초 대기

            // Control View controls for ClientSocket 
            BtnConn.Enabled = true;
            BtnDiscon.Enabled = false;

            TxtCurrentRcsState.Text = "Unknown";
            TxtCurrentRcsState.Enabled = false;
            TxtRcsPasswd.Enabled = false;
            BtnPreArmedSetup.Enabled = false;

            GbxRcsEngageCalControl.Visible = false;
        }

        /********************************************************************************
        @brief      TmrHeartBeatRequest_Tick
        @detail     When robot control software does not work from heart beat timer, 
                    state of RUI should be switched to safe mode
        @param[in]  sender - event object
        @param[in]  e - event arguments
        @return     void
        @exception  exception
        @remark
        *********************************************************************************/
        private void TmrHeartBeatRequest_Tick(object sender, EventArgs e)
        {
        }

        /********************************************************************************
        @brief      CmbModeSelect_SelectedIndexChanged
        @detail     When the combobox including armed manual, auto engage, and calibration
                    switches each other, the group of controls must be changed.
        @param[in]  sender - event object
        @param[in]  e - event arguments
        @return     void
        @exception  exception
        @remark
        *********************************************************************************/
        private void CmbModeSelect_SelectedIndexChanged(object sender, EventArgs e)
        {
            // string[] strModeSelect = { "", "Armed Manual", "Auto Engage", "Calibration" };

            if (CmbModeSelect.SelectedIndex == 0) // Pre-armed 
            {
                // Change the state of RCS as Pre-armed
                TxtCurrentRcsState.Text = "Pre-armed";

                LblAutoEngageList.Visible = false;
                TxtAutoEngageList.Visible = false;

                BtnUpIncY.Visible = false;
                BtnDownDecY.Visible = false;
                BtnRightIncX.Visible = false;
                BtnLeftDecX.Visible = false;
                BtnFire.Visible = false;

                BtnFireCancel.Visible = false;
            }
            else if (CmbModeSelect.SelectedIndex == 1) // Armed Manual
            {
                // Change the state of RCS as Armed Manual
                TxtCurrentRcsState.Text = "Armed Manual";

                LblAutoEngageList.Visible = false;
                TxtAutoEngageList.Visible = false;

                BtnUpIncY.Visible = true;
                BtnDownDecY.Visible = true;
                BtnRightIncX.Visible = true;
                BtnLeftDecX.Visible = true;

                BtnFire.Visible = true;
                BtnFireCancel.Visible = false;
            }
            else if (CmbModeSelect.SelectedIndex == 2) // Auto Engage
            {
                // Change the state of RCS as Auto Engage
                TxtCurrentRcsState.Text = "Auto Engage";

                LblAutoEngageList.Visible = true;
                TxtAutoEngageList.Visible = true;

                BtnUpIncY.Visible = false;
                BtnDownDecY.Visible = false;
                BtnRightIncX.Visible = false;
                BtnLeftDecX.Visible = false;
                
                BtnFire.Visible = true;
                BtnFireCancel.Visible = true;
            }
            else if (CmbModeSelect.SelectedIndex == 3) // Calibration
            {
                // Change the state of RCS as Pre-armed due to no Calibration State
                TxtCurrentRcsState.Text = "Pre-armed";

                LblAutoEngageList.Visible = false;
                TxtAutoEngageList.Visible = false;

                BtnUpIncY.Visible = true;
                BtnDownDecY.Visible = true;
                BtnRightIncX.Visible = true;
                BtnLeftDecX.Visible = true;

                BtnFire.Visible = false;
                BtnFireCancel.Visible = false;
            }
        }

        /********************************************************************************
        @brief      BtnPreArmedSetup_Click
        @detail     BtnPreArmedSetup_Click
        @param[in]  sender - event object
        @param[in]  e - event arguments
        @return     void
        @exception  exception
        @remark
        *********************************************************************************/
        private void BtnPreArmedSetup_Click(object sender, EventArgs e)
        {
            // Change the state of RCS as Pre-armed
            TxtCurrentRcsState.Text = "Pre-armed";

            // Visibility changes
            GbxRcsEngageCalControl.Visible = true;
        }

        /********************************************************************************
        @brief      BtnFire_Click
        @detail     BtnFire_Click
        @param[in]  sender - event object
        @param[in]  e - event arguments
        @return     void
        @exception  exception
        @remark
        *********************************************************************************/
        private void BtnFire_Click(object sender, EventArgs e)
        {
            MessageBox.Show("Fires", "Information");
        }

    }
}
