#include <fstream>
#include <string>
#include <vector>
#include <opencv2/opencv.hpp>
#include <tensorflow/lite/interpreter.h>
#include <tensorflow/lite/kernels/register.h>
#include <tensorflow/lite/string_util.h>
#include <tensorflow/lite/examples/label_image/get_top_n.h>
#include <tensorflow/lite/model.h>
#include <tensorflow/lite/optional_debug_tools.h>

using namespace cv;
using namespace std;

float input_mean = 127.5;
float  input_std = 127.5;

typedef cv::Point3_<float> Pixel;

std::vector<std::string> Labels;
std::unique_ptr<tflite::Interpreter> interpreter;

size_t resize_width;
size_t resize_height;
size_t resize_channels;
TfLiteType model_input_type;
int input_index;

void MatType(cv::Mat &inputMat)
{
    int inttype = inputMat.type();

    std::string r, a;
    uchar depth = inttype & CV_MAT_DEPTH_MASK;
    uchar chans = 1 + (inttype >> CV_CN_SHIFT);
    switch (depth) {
    case CV_8U:  r = "8U";   a = "Mat.at<uchar>(y,x)"; break;
    case CV_8S:  r = "8S";   a = "Mat.at<schar>(y,x)"; break;
    case CV_16U: r = "16U";  a = "Mat.at<ushort>(y,x)"; break;
    case CV_16S: r = "16S";  a = "Mat.at<short>(y,x)"; break;
    case CV_32S: r = "32S";  a = "Mat.at<int>(y,x)"; break;
    case CV_32F: r = "32F";  a = "Mat.at<float>(y,x)"; break;
    case CV_64F: r = "64F";  a = "Mat.at<double>(y,x)"; break;
    default:     r = "User"; a = "Mat.at<UKNOWN>(y,x)"; break;
    }
    r += "C";
    r += (chans + '0');
    std::cout << "Mat is of type " << r << " and should be accessed with " << a << std::endl;

}


static bool getFileContent(std::string fileName)
{

    // Open the File
    std::ifstream in(fileName.c_str());
    // Check if object is valid
    if (!in.is_open()) return false;

    std::string str;
    // Read the next line from File untill it reaches the end.
    while (std::getline(in, str))
    {
        // Line contains string of length > 0 then save it in vector
        if (str.size() > 0) Labels.push_back(str);
    }
    // Close The File
    in.close();
    return true;
}

void normalize(Pixel& pixel) {
    pixel.x = ((pixel.x - input_mean) / input_std);
    pixel.y = ((pixel.y - input_mean) / input_std);
    pixel.z = ((pixel.z - input_mean) / input_std);
}

void detect_from_video(Mat& src)
{
    Mat image;
    int cam_width = src.cols;
    int cam_height = src.rows;


    if (model_input_type == kTfLiteFloat32)
    {
        cv::resize(src, image, cv::Size(resize_width, resize_height));
        cv::cvtColor(image, image, cv::COLOR_BGR2RGB);
        
        image.convertTo(image, CV_32FC3, 1 / input_std, -input_mean / input_std);

        float* in = image.ptr<float>(0);
        float* out = interpreter->typed_input_tensor<float>(0); //input_index
        memcpy(out, in, image.rows * image.cols * sizeof(float)* resize_channels);
    }
    else
    {
        cv::resize(src, image, cv::Size(resize_width, resize_height));
        memcpy(interpreter->typed_input_tensor<unsigned char>(0), image.data, image.total() * image.elemSize());
    }

    //cout << "M = " << endl << " " << image << endl << endl;
    //MatType(image);
   // Mat show_image;
   // image.convertTo(show_image, CV_8U, 255);
   // imshow("Display", show_image);
    //waitKey(0);

    interpreter->SetAllowFp16PrecisionForFp32(true);
    interpreter->SetNumThreads(4);      //quad core

    //        cout << "tensors size: " << interpreter->tensors_size() << "\n";
    //        cout << "nodes size: " << interpreter->nodes_size() << "\n";
    //        cout << "inputs: " << interpreter->inputs().size() << "\n";
    //        cout << "input(0) name: " << interpreter->GetInputName(0) << "\n";
    //        cout << "outputs: " << interpreter->outputs().size() << "\n";

    interpreter->Invoke();      // run your model

    printf("GetOutputName %s\n", interpreter->GetOutputName(0));

#if 0

    // Get Output
    int output = interpreter->outputs()[0];

    TfLiteIntArray* output_dims = interpreter->tensor(output)->dims;
    auto output_size = output_dims->data[output_dims->size - 1];
    std::vector<std::pair<float, int>> top_results;
    float threshold = 0.01f;

    switch (interpreter->tensor(output)->type)
    {
    case kTfLiteInt32:
        tflite::label_image::get_top_n<float>(interpreter->typed_output_tensor<float>(0), output_size, 1, threshold, &top_results, kTfLiteFloat32);
        break;
    case kTfLiteUInt8:
        tflite::label_image::get_top_n<uint8_t>(interpreter->typed_output_tensor<uint8_t>(0), output_size, 1, threshold, &top_results, kTfLiteUInt8);
        break;
    case kTfLiteFloat32:
        tflite::label_image::get_top_n<float>(interpreter->typed_output_tensor<float>(0), output_size, 10, threshold, &top_results, kTfLiteFloat32);
        break;
    default:
        fprintf(stderr, "cannot handle output type\n");
        exit(-1);
    }
    // Load Labels

    // Print labels with confidence in input image
    int xxx = 0;
    for (const auto& result : top_results)
    {
        const float confidence = result.first;
        const int index = result.second;
        std::string output_txt = "Label :" + format("%s", Labels[index].c_str()) + " Confidence : " + std::to_string(confidence);
        cv::putText(src, output_txt, cv::Point(10, 60), cv::FONT_HERSHEY_SIMPLEX, 0.8, cv::Scalar(0, 0, 255), 2);
        printf("%d is %s\n", xxx++, output_txt.c_str());
    }
#else
    int boxes_idx, classes_idx, scores_idx, num_idx;
    if (strcmp(interpreter->GetOutputName(0), "StatefulPartitionedCall:1") == 0)
    {
        boxes_idx = 1;
        classes_idx = 3;
        scores_idx = 0;
        num_idx = 2;
        printf("Stateful\n");
    }
    else
    {
        boxes_idx = 0;
        classes_idx = 1;
        scores_idx = 2;
        num_idx = 3;
    }

    const float* detection_locations = interpreter->tensor(interpreter->outputs()[boxes_idx])->data.f;
    const float* detection_classes = interpreter->tensor(interpreter->outputs()[classes_idx])->data.f;
    const float* detection_scores = interpreter->tensor(interpreter->outputs()[scores_idx])->data.f;
    const int    num_detections = *interpreter->tensor(interpreter->outputs()[num_idx])->data.f;

    //there are ALWAYS 10 detections no matter how many objects are detectable
     std::cout << "number of detections: " << num_detections << "\n";

    const float confidence_threshold = 0.5;
    for (int i = 0; i < num_detections; i++) {
        printf(" location %f\n", detection_locations[i]);
        printf(" classe   %f\n", detection_classes[i]);
        printf(" score    %f\n\n", detection_scores[i]);


        if (detection_scores[i] > confidence_threshold) {
            int  det_index = (int)detection_classes[i] + 0;
            float y1 = detection_locations[4 * i + 0] * cam_height;
            float x1 = detection_locations[4 * i + 1] * cam_width;
            float y2 = detection_locations[4 * i + 2] * cam_height;
            float x2 = detection_locations[4 * i + 3] * cam_width;

            Rect rec((int)x1, (int)y1, (int)(x2 - x1), (int)(y2 - y1));
            rectangle(src, rec, Scalar(0, 0, 255), 1, 8, 0);
            putText(src, format("%s-%f", Labels[det_index].c_str(), detection_scores[i]), Point(x1, y1 - 5), FONT_HERSHEY_SIMPLEX, 0.5, Scalar(0, 0, 255), 1, 8, 0);
        }

    }
    printf("\n\n\n\n");
#endif
}

int main(int argc, char** argv)
{
    float f;
    float FPS[16];
    int i, Fcnt = 0;
    Mat frame;
    chrono::steady_clock::time_point Tbegin, Tend;

    for (i = 0; i < 16; i++) FPS[i] = 0.0;

    // Load model
    std::unique_ptr<tflite::FlatBufferModel> model = tflite::FlatBufferModel::BuildFromFile("detect.tflite");
    //std::unique_ptr<tflite::FlatBufferModel> model = tflite::FlatBufferModel::BuildFromFile("mobilenet_v1_1.0_224_quant.tflite");
    
    if (model == nullptr)
    {
        fprintf(stderr, "failed to load model\n");
        exit(-1);
    }

    // Build the interpreter
    tflite::ops::builtin::BuiltinOpResolver resolver;
    tflite::InterpreterBuilder(*model.get(), resolver)(&interpreter);
    if (interpreter == nullptr)
    {
        fprintf(stderr, "Failed to initiate the interpreter\n");
        exit(-1);
    }

    if (interpreter->AllocateTensors() != kTfLiteOk)
    {
        fprintf(stderr, "Failed to allocate tensor\n");
        exit(-1);
    }

    // Configure the interpreter
    interpreter->SetAllowFp16PrecisionForFp32(true);
    interpreter->SetNumThreads(1);
    // Get Input Tensor Dimensions
    input_index = interpreter->inputs()[0];
    resize_height = interpreter->tensor(input_index)->dims->data[1];
    resize_width = interpreter->tensor(input_index)->dims->data[2];
    resize_channels = interpreter->tensor(input_index)->dims->data[3];
    model_input_type = interpreter->tensor(input_index)->type;
    
    printf("type %s\n", TfLiteTypeGetName(model_input_type));


    // Get the names
    //bool result = getFileContent("labels_mobilenet_quant_v1_224.txt");
    bool result = getFileContent("labelmap.txt");
    if (!result)
    {
        cout << "loading labels failed";
        exit(-1);
    }
#if 0
    VideoCapture cap("James.mp4");
    if (!cap.isOpened()) {
        cerr << "ERROR: Unable to open the camera" << endl;
        return 0;
    }
#endif
    cout << "Start grabbing, press ESC on Live window to terminate" << endl;
    while (1) {
       // frame = imread("classification_example.jpg");
       frame = imread("Capture1.jpg");  //need to refresh frame before dnn class detection
       // cap >> frame;
        if (frame.empty()) {
            cerr << "ERROR: Unable to grab from the camera" << endl;
            break;
        }

        Tbegin = chrono::steady_clock::now();

        detect_from_video(frame);

        Tend = chrono::steady_clock::now();
        //calculate frame rate
        f = chrono::duration_cast <chrono::milliseconds> (Tend - Tbegin).count();
        if (f > 0.0) FPS[((Fcnt++) & 0x0F)] = 1000.0 / f;
        for (f = 0.0, i = 0; i < 16; i++) { f += FPS[i]; }
        putText(frame, format("FPS %0.2f", f / 16), Point(10, 20), FONT_HERSHEY_SIMPLEX, 0.6, Scalar(0, 0, 255));

        //show output
//        cout << "FPS" << f/16 << endl;
        cv::resize(frame, frame, cv::Size(frame.cols/2, frame.rows/2));
        imshow("Display", frame);

        char esc = waitKey(5);
        if (esc == 27) break;
    }

    cout << "Closing the camera" << endl;
    destroyAllWindows();
    cout << "Bye!" << endl;

    return 0;
}



#if 0
int main(int argc, char **argv)
{

    // Get Model label and input image
    if (argc != 4)
    {
        fprintf(stderr, "TfliteClassification.exe modelfile labels image\n");
        exit(-1);
    }
    const char *modelFileName = argv[1];
    const char *labelFile = argv[2];
    const char *imageFile = argv[3];

    bool result = getFileContent("labelmap.txt");
    if (!result)
    {
        cout << "loading labels failed";
        exit(-1);
    }


    // Load Model
    std::unique_ptr<tflite::FlatBufferModel> model = tflite::FlatBufferModel::BuildFromFile(modelFileName);
    if (model == nullptr)
    {
        fprintf(stderr, "failed to load model\n");
        exit(-1);
    }
    // Initiate Interpreter
    tflite::ops::builtin::BuiltinOpResolver resolver;
    tflite::InterpreterBuilder(*model.get(), resolver)(&interpreter);
    if (interpreter == nullptr)
    {
        fprintf(stderr, "Failed to initiate the interpreter\n");
        exit(-1);
    }

    if (interpreter->AllocateTensors() != kTfLiteOk)
    {
        fprintf(stderr, "Failed to allocate tensor\n");
        exit(-1);
    }
    // Configure the interpreter
    interpreter->SetAllowFp16PrecisionForFp32(true);
    interpreter->SetNumThreads(1);
    // Get Input Tensor Dimensions
    int input = interpreter->inputs()[0];
    auto height = interpreter->tensor(input)->dims->data[1];
    auto width = interpreter->tensor(input)->dims->data[2];
    auto channels = interpreter->tensor(input)->dims->data[3];


    TfLiteType input_type = interpreter->tensor(input)->type;
    printf("type %s\n", TfLiteTypeGetName(input_type));
    //input_type, kTfLiteFloat32, kTfLiteUInt8);


    // Load Input Image
    cv::Mat image;
    auto frame = cv::imread(imageFile);
    if (frame.empty())
    {
        fprintf(stderr, "Failed to load iamge\n");
        exit(-1);
    }

    // Copy image to input tensor
    cv::resize(frame, image, cv::Size(width, height), cv::INTER_NEAREST);

    if (input_type == kTfLiteFloat32)
    {
        float input_mean = 127.5;
        float  input_std = 127.5;

        cv::cvtColor(image, image, cv::COLOR_BGR2RGB);
        float* out = interpreter->typed_tensor<float>(input);
        image.convertTo(image, CV_32F, 255.f / input_std);
        cv::subtract(image, cv::Scalar(input_mean / input_std), image);
        float* in = image.ptr<float>(0);
        memcpy(out, in, image.rows * image.cols * sizeof(float));
    }
    else  memcpy(interpreter->typed_input_tensor<unsigned char>(0), image.data, image.total() * image.elemSize());

    MatType(image);

    
   

    // Inference
    std::chrono::steady_clock::time_point start, end;
    start = std::chrono::steady_clock::now();
    interpreter->Invoke();
    end = std::chrono::steady_clock::now();
    auto inference_time = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

   // tflite::PrintInterpreterState(interpreter.get());
    printf("GetOutputName %s\n", interpreter->GetOutputName(0));
 
    // Get Output
    int output = interpreter->outputs()[0];

    TfLiteIntArray *output_dims = interpreter->tensor(output)->dims;
    auto output_size = output_dims->data[output_dims->size - 1];
    std::vector<std::pair<float, int>> top_results;
    float threshold = 0.01f;

    switch (interpreter->tensor(output)->type)
    {
    case kTfLiteInt32:
        tflite::label_image::get_top_n<float>(interpreter->typed_output_tensor<float>(0), output_size, 1, threshold, &top_results, kTfLiteFloat32);
        break;
    case kTfLiteUInt8:
        tflite::label_image::get_top_n<uint8_t>(interpreter->typed_output_tensor<uint8_t>(0), output_size, 1, threshold, &top_results, kTfLiteUInt8);
        break;
    case kTfLiteFloat32:
        tflite::label_image::get_top_n<float>(interpreter->typed_output_tensor<float>(0), output_size, 1, threshold, &top_results, kTfLiteFloat32);
        break;
    default:
        fprintf(stderr, "cannot handle output type\n");
        exit(-1);
    }
    // Print inference ms in input image
    cv::putText(frame, "Infernce Time in ms: " + std::to_string(inference_time), cv::Point(10, 30), cv::FONT_HERSHEY_SIMPLEX, 0.8, cv::Scalar(0, 0, 255), 2);

    // Load Labels
    auto labels = load_labels(labelFile);

    // Print labels with confidence in input image
    for (const auto &result : top_results)
    {
        const float confidence = result.first;
        const int index = result.second;
        std::string output_txt = "Label :" + labels[index] + " Confidence : " + std::to_string(confidence);
        cv::putText(frame, output_txt, cv::Point(10, 60), cv::FONT_HERSHEY_SIMPLEX, 0.8, cv::Scalar(0, 0, 255), 2);
    }

    // Display image
    cv::imshow("Output", frame);
    cv::waitKey(0);

    return 0;
}
#endif