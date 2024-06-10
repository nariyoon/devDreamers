/********************************************************************************
@file		ClientSocket.cs
@auther		DevDremers at CMU
@biref		Client Socket file
@detail		Client Socket file
@version	0.01.00
@date	    2024.06.11
@history	
@copyright  No copyright
*********************************************************************************/
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Net;
using System.Net.Sockets;
using System.IO;
using System.Net.Http;
using System.Threading.Tasks;

namespace LGClientDisplayNew
{
    public class ClientSocket
    {
        public TcpClient tcpClientSocket;
        public UdpClient udpClientSocket;
        public NetworkStream serverTcpStream;
        public IPEndPoint clientIPEndPoint;
        public const Int32 MAX_BUFFER_SIZE = 2048;
        // public string message_information = ""; // 출력변수

        private Form1 mFrame;

        // mainForm에서 TCP 포트가 열려 있는 경우 처리하기 위한 로컬/공용변수
        private bool isEthernetPortUsed = false;
        private bool flagTcpPortRunning = true;
        private bool flagUdpPortRunning = false;

        public bool IsEthernetPortUsed
        {
            get { return isEthernetPortUsed; }
            set { isEthernetPortUsed = value; }
        }
        public bool FlagTcpPortRunning
        {
            get { return flagTcpPortRunning; }
            set { flagTcpPortRunning = value; }
        }
        public bool FlagUdpPortRunning
        {
            get { return flagUdpPortRunning; }
            set { flagUdpPortRunning = value; }
        }

        /// <summary>
        /// Comstructor to set the properties of our
        /// serial port communicator to nothing
        /// </summary>
        public ClientSocket(Form1 mFrame)
        {
            this.mFrame = mFrame;
            this.flagTcpPortRunning = true;
        }

        ///// <summary>
        ///// Overloaded constructor of gTalinCommManager for data insertion to TalinStruct
        ///// </summary>
        ///// <param name="mFrame"></param>
        //public ClientSocket(mainForm mFrame, ref mainForm.ModelStruct_t ModelStruct)
        //{
        //    this.mFrame = mFrame;
        //    this.ModelStruct = ModelStruct;
        //    this.flagTcpPortRunning = true;
        //}

        public void startTcpClient(TcpClient inClientSocket, string serverIP, Int32 serverPort)
        {
            try
            {
                // Socket binding 
                this.tcpClientSocket = inClientSocket;
                tcpClientSocket.Connect(serverIP, serverPort);
                isEthernetPortUsed = true;

                Console.WriteLine("Client Socket Connect to {0} : {1}", serverIP.ToString(), Convert.ToString(serverPort));

                // Thread ctThread = new Thread(DoTcpReceiveStreamAsync);
                Thread ctThread = new Thread(doTcpReceiveStream);
                ctThread.Start();
            }
            catch (ArgumentNullException ex)
            {
                Console.WriteLine("Client Socket Binding Error >> " + ex.ToString());
                // flagTcpPortRunning = false;
                isEthernetPortUsed = false;
                flagTcpPortRunning = false;
            }
            catch (SocketException ex)
            {
                Console.WriteLine("Client Socket Binding Error >> " + ex.ToString());
                // flagTcpPortRunning = false;
                isEthernetPortUsed = false;
                flagTcpPortRunning = false;
            }
            catch (Exception ex)
            {
                Console.WriteLine("Client Socket Binding Error >> " + ex.ToString());
                // flagTcpPortRunning = false;
                isEthernetPortUsed = false;
                flagTcpPortRunning = false;
            }
        }

        public void startUdpClient(UdpClient inUdpClientSocket, IPEndPoint ipEndPoint)
        {
            try
            {
                // Socket binding 
                this.udpClientSocket = inUdpClientSocket;
                this.clientIPEndPoint = ipEndPoint;

                udpClientSocket.Connect(ipEndPoint);
                
                // if success wihtout exception
                isEthernetPortUsed = true;
                flagTcpPortRunning = false;
                flagUdpPortRunning = true;

                // Console.WriteLine("Client Socket Connect to {0} : {1}", serverIP.ToString(), Convert.ToString(serverPort));
                // msg = udpClientSocket.Receive(ref ipEndPoint);
                // String returnData = Encoding.ASCII.GetString(msg);

                Thread ctThread = new Thread(doUdpReceiveStream);
                ctThread.Start();
            }
            catch (ArgumentNullException ex)
            {
                Console.WriteLine("Client Socket Binding Error >> " + ex.ToString());
                isEthernetPortUsed = false;
                flagTcpPortRunning = true;
                flagUdpPortRunning = false;
            }
            catch (SocketException ex)
            {
                Console.WriteLine("Client Socket Binding Error >> " + ex.ToString());
                isEthernetPortUsed = false;
                flagTcpPortRunning = true;
                flagUdpPortRunning = false;
            }
            catch (Exception ex)
            {
                Console.WriteLine("Client Socket Binding Error >> " + ex.ToString());
                isEthernetPortUsed = false;
                flagTcpPortRunning = true;
                flagUdpPortRunning = false;
            }
        }

        // public async DoTcpReceiveStreamAsync()
        public void doTcpReceiveStream()
        {
            int requestCount = 0;
            String receivedMsg = null;
            // mainForm.ModelStruct_t threadStruct = new mainForm.ModelStruct_t();

            requestCount = 0;

            // 스트림 정의
            serverTcpStream = tcpClientSocket.GetStream();

            while (flagTcpPortRunning)
            {
                try
                {
                    // Release thread when server is not sending data by async-read
                    // serverTcpStream.Read(inStream, 0, MAX_BUFFER_SIZE);
                    // await serverTcpStream.ReadAsync(inStream, 0, MAX_BUFFER_SIZE);
                    // byte[] buffer = new byte[4096];
                    // int bytesRead = await serverTcpStream.ReadAsync(buffer, 0, buffer.Length);
                    byte[] inStream = new byte[MAX_BUFFER_SIZE];
                    serverTcpStream.Read(inStream, 0, MAX_BUFFER_SIZE);
                    serverTcpStream.Flush();

                    // Critical Section Lock
                    lock (mFrame.LockSocketComm)
                    {
                        // decode received message from server of robot control software
                        // decode_message(inStream, ref receivedMsg, ref threadStruct);
                        // save_to_file_motion("c:\\output.csv", serverResponse);  // 검증용

                        // mFrame.ModelStruct = threadStruct;
                    }
                    // Critical Section Unlock

                    requestCount++;
                }
                catch (Exception ex)
                {
                    Console.WriteLine("Client Socket Streaming Thread Error >> " + ex.ToString());
                }
            }

            tcpClientSocket.Close();
        }

        public void doUdpReceiveStream()
        {
            int requestCount = 0;
            String receivedMsg = null;
            // mainForm.ModelStruct_t threadStruct = new mainForm.ModelStruct_t();

            requestCount = 0;

            // UDP는 스트림 정의 생략
            
            while (flagUdpPortRunning)
            {
                try
                {
                    byte[] inStream = new byte[MAX_BUFFER_SIZE];
                    inStream = udpClientSocket.Receive(ref clientIPEndPoint);

                    // Critical Section Lock
                    lock (mFrame.LockSocketComm)
                    {
                        // decode received message from server of robot control software
                        // decode_message(inStream, ref receivedMsg, ref threadStruct);
                        // save_to_file_motion("c:\\output.csv", serverResponse);  // 검증용

                        // mFrame.ModelStruct = threadStruct;
                    }
                    // Critical Section Unlocked

                    requestCount++;
                }
                catch (Exception ex)
                {
                    Console.WriteLine("Client Socket Streaming Thread Error >> " + ex.ToString());
                }
            }

            udpClientSocket.Close();
        }

        // Little endian 방식 - Byte를 Word로 변환
        private void convert_little_endian(Byte[] read_byte_arr, ref UInt16 conv_word)
        {
            conv_word = (UInt16)(read_byte_arr[1] << 8);
            conv_word += (UInt16)read_byte_arr[0];
        }

        private void convert_byte_to_UInt16(Byte[] input_byte, Int32 index_byte, ref UInt16 output_data)
        {
            output_data = (UInt16)input_byte[index_byte];
            output_data += (UInt16)(input_byte[index_byte + 1] << 8);
        }

        private void convert_byte_to_Int32(Byte[] input_byte, Int32 index_byte, ref Int32 output_data)
        {
            UInt32 tmp_data;

            tmp_data = (UInt32)input_byte[index_byte];
            tmp_data += (UInt32)(input_byte[index_byte + 1] << 8);
            tmp_data += (UInt32)(input_byte[index_byte + 2] << 16);
            tmp_data += (UInt32)(input_byte[index_byte + 3] << 24);

            output_data = (Int32)tmp_data; // * scale_factor;
        }

        private void convert_byte_to_Int64(Byte[] input_byte, Int32 index_byte, ref Int64 output_data)
        {
            UInt64 tmp_data;

            tmp_data = (UInt64)input_byte[index_byte];
            tmp_data += (UInt64)(input_byte[index_byte + 1] << 8);
            tmp_data += (UInt64)(input_byte[index_byte + 2] << 16);
            tmp_data += (UInt64)(input_byte[index_byte + 3] << 24);
            tmp_data += (UInt64)(input_byte[index_byte + 4] << 32);
            tmp_data += (UInt64)(input_byte[index_byte + 5] << 40);
            tmp_data += (UInt64)(input_byte[index_byte + 6] << 48);
            tmp_data += (UInt64)(input_byte[index_byte + 7] << 56);

            output_data = (Int64)tmp_data; // * scale_factor;
        }

        private void convert_byte_to_UInt32(Byte[] input_byte, Int32 index_byte, ref UInt32 output_data)
        {
            output_data = (UInt32)input_byte[index_byte];
            output_data += (UInt32)(input_byte[index_byte + 1] << 8);
            output_data += (UInt32)(input_byte[index_byte + 2] << 16);
            output_data += (UInt32)(input_byte[index_byte + 3] << 24);
        }

        private void convert_byte_to_UInt64(Byte[] input_byte, Int32 index_byte, ref UInt64 output_data)
        {
            output_data = (UInt64)input_byte[index_byte];
            output_data += (UInt64)(input_byte[index_byte + 1]) << 8;
            output_data += (UInt64)(input_byte[index_byte + 2]) << 16;
            output_data += (UInt64)(input_byte[index_byte + 3]) << 24;
            output_data += (UInt64)(input_byte[index_byte + 4]) << 32;
            output_data += (UInt64)(input_byte[index_byte + 5]) << 40;
            output_data += (UInt64)(input_byte[index_byte + 6]) << 48;
            output_data += (UInt64)(input_byte[index_byte + 7]) << 56;
        }

        private void convert_byte_to_Float(Byte[] input_byte, Int32 index_byte, ref float output_data)
        {
            Byte[] tmp_byte = new Byte[4];
            float[] tmp_float = new float[2];

            for (int i = 0; i < 4; i++)
            {
                tmp_byte[i] = input_byte[index_byte + i];
            }
            Buffer.BlockCopy(tmp_byte, 0, tmp_float, 0, sizeof(float));
            output_data = tmp_float[0];
        }

        private void convert_byte_to_Double(Byte[] input_byte, Int32 index_byte, ref Double output_data)
        {
            Byte[] tmp_byte = new Byte[8];
            Double[] tmp_double = new Double[2];

            for (int i = 0; i < 8; i++)
            {
                tmp_byte[i] = input_byte[index_byte + i];
            }
            Buffer.BlockCopy(tmp_byte, 0, tmp_double, 0, sizeof(Double));
            output_data = tmp_double[0];
        }

        // 검증용 파일 출력 메소드
        private void save_data_to_file(String fileStreamName, String saveStringMessage)
        {
            try
            {
                // 수신 성공한 binary를 CSV로 저장
                FileStream FWrite = new FileStream(fileStreamName, FileMode.Truncate, FileAccess.Write);
                StreamWriter SWrite = new StreamWriter(FWrite, System.Text.Encoding.UTF8);

                SWrite.WriteLine(saveStringMessage);

                SWrite.Close();
                FWrite.Close();
            }
            catch (Exception ex)
            {
                Console.WriteLine("Save File Stream Error >> " + ex.ToString());
            }
        }

    }
}

