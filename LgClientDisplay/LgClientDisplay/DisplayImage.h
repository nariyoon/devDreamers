#pragma once

bool InitializeImageDisplay(HWND hWndMain);
bool DisplayImage(void);
bool ProcessImage(cv::Mat& ImageIn);
void SetDisplayNoData(void);
//-----------------------------------------------------------------
// END of File
//-----------------------------------------------------------------