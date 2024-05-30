mkdir X64
mkdir X64\Release
mkdir X64\Debug
copy ..\..\opencv\build\x64\vc16\bin\opencv_world490.dll X64\Release
copy ..\..\opencv\build\x64\vc16\bin\opencv_world490d.dll X64\Debug
copy tflite-dist\libs\windows_x86_64\tensorflowlite_c.dll X64\Release
copy tflite-dist\libs\windows_x86_64\tensorflowlite_c.dll X64\Debug
copy ..\TfLite-2.17\Data\*.jpg images