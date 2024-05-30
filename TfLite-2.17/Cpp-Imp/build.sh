g++ -O2 tflite-cpp-api.cpp -o tflite-cpp-api -I/usr/local/include -I../include -I../Common -I/usr/include/opencv4/ -I/usr/include/libcamera -L/usr/local/lib -L../lib -ltensorflow-lite -llgpio -lopencv_core -lopencv_highgui -lopencv_imgcodecs -lopencv_imgproc -lopencv_video -lopencv_videoio -llccv
# ../Common/NetworkTCP.cpp ../Common/TcpSendRecvJpeg.cpp ../Common/KeyboardSetup.cpp 
 
