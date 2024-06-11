using System.Net.Sockets;
using System.Net;

namespace TcpServerTest
{
    class Program
    {
        static void Main(string[] args)
        {
            // [1] 서버의 Listen 동작을 바로 실행 할 수 있다.
            IPEndPoint ipt = new IPEndPoint(IPAddress.Parse("127.0.0.1"), 5000); // 7000);
            TcpListener listener = new TcpListener(ipt);
            String welcomMsg = "hello";

            // [2] "서버" 클라가이언트의 접속 요청을 대기하도록 명령
            listener.Start();

            // 버퍼 준비
            byte[] receiverBuff = new byte[2048];

            while (true)
            {
                // [4] 대기중인 서버 소켓이 Aceept()를 실행하고, 서버는 클라이언트와 연결이 성공된 소켓을 하나 더 만든다.
                TcpClient Connected_TCPClient = listener.AcceptTcpClient();

                // TcpClient 객체에서 TCP 네트워크 스트림을 가져와서 사용하도록 한다
                NetworkStream stream = Connected_TCPClient.GetStream();

                receiverBuff[0] = (byte)'h';
                receiverBuff[1] = (byte)'e';
                receiverBuff[2] = (byte)'\0';
                stream.Write(receiverBuff, 0, 2);

                // [5] 데이터 수신
                int nbytes;
                while ((nbytes = stream.Read(receiverBuff, 0, receiverBuff.Length)) > 0)
                {
                    // 데이터 송신, 받은것을 다시 보낸다.(Echo)
                    stream.Write(receiverBuff, 0, nbytes);
                }

                // [6] 연결된 소켓을 닫는다.
                stream.Close();
                Connected_TCPClient.Close();

                // 계속 반복
            }
        }
    }
}