g++ -O2 tflite-c-api.cpp ../../Common/ObjectDetector.cpp ../../Common/NetworkTCP.cpp ../../Common/TcpSendRecvJpeg.cpp -o tflite-c-api -I/usr/local/include -I../include -I../../Common  -I/usr/include/opencv4/ -I/usr/include/libcamera -L/usr/local/lib -L../lib -ltensorflowlite_c -llgpio -lopencv_core -lopencv_highgui -lopencv_imgcodecs -lopencv_imgproc -lopencv_video -lopencv_videoio -llccv
# ../Common/KeyboardSetup.cpp 
 
