#pragma once
#include <winsock2.h>
#include <ws2tcpip.h>
int ReadDataTcp(SOCKET socket, unsigned char* data, int length);
int ReadDataTcpNoBlock(SOCKET socket, unsigned char* data, int length);
int WriteDataTcp(SOCKET socket, unsigned char* data, int length);
//-----------------------------------------------------------------
// END of File
//-----------------------------------------------------------------