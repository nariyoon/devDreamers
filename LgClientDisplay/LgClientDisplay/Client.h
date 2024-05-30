#pragma once
bool ConnectToSever(const char* remotehostname, unsigned short remoteport);
bool StartClient(void);
bool StopClient(void);
bool IsClientConnected(void);
bool SendCodeToSever(unsigned char Code);
bool SendTargetOrderToSever(char *TargetOrder);
bool SendPreArmCodeToSever(char* Code);
bool SendStateChangeRequestToSever(SystemState_t State);
bool SendCalibToSever(unsigned char Code);
//-----------------------------------------------------------------
// END of File
//-----------------------------------------------------------------