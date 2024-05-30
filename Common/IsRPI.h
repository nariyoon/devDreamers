//------------------------------------------------------------------------------------------------
// File: isrpi.h
// Project: LG Exec Ed Program
// Versions:
// 1.0 April 2024 - initial version
// Provides compatibility between rapicam and opencv so the same opencv API can be used seamlessly
//------------------------------------------------------------------------------------------------
#ifndef IsRPIH
#define IsRPIH
#ifdef  __aarch64__
#define  IsPi5 1
#else
#define  IsPi5 0
#endif
#endif
//------------------------------------------------------------------------------------------------
//END of Include
//------------------------------------------------------------------------------------------------
