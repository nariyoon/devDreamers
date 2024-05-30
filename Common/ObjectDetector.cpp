#include "ObjectDetector.h"
#include <opencv2/imgproc.hpp>

using namespace cv;

ObjectDetector::ObjectDetector(const char* tfliteModelPath, bool quantized, bool useXnn) {
	m_modelQuantized = quantized;
	initDetectionModel(tfliteModelPath, useXnn);
}

ObjectDetector::~ObjectDetector() {
	if (m_model != nullptr)
		TfLiteModelDelete(m_model);
}

void ObjectDetector::initDetectionModel(const char* tfliteModelPath, bool useXnn) {
	m_model = TfLiteModelCreateFromFile(tfliteModelPath);
	if (m_model == nullptr) {
		printf("Failed to load model");
		return;
	}

	// Build the interpreter
	TfLiteInterpreterOptions* options = TfLiteInterpreterOptionsCreate();
	TfLiteInterpreterOptionsSetNumThreads(options, 1);

	if (useXnn) {
		TfLiteXNNPackDelegateOptions xnnOpts = TfLiteXNNPackDelegateOptionsDefault();
		m_xnnpack_delegate = TfLiteXNNPackDelegateCreate(&xnnOpts);
		TfLiteInterpreterOptionsAddDelegate(options, m_xnnpack_delegate);
	}

	// Create the interpreter.
	m_interpreter = TfLiteInterpreterCreate(m_model, options);
	if (m_interpreter == nullptr) {
		printf("Failed to create interpreter");
		return;
	}

	// Allocate tensor buffers.
	if (TfLiteInterpreterAllocateTensors(m_interpreter) != kTfLiteOk) {
		printf("Failed to allocate tensors!");
		return;
	}

	// Find input tensors.
	if (TfLiteInterpreterGetInputTensorCount(m_interpreter) != 1) {
		printf("Detection model graph needs to have 1 and only 1 input!");
		return;
	}

	m_input_tensor = TfLiteInterpreterGetInputTensor(m_interpreter, 0);
	if (m_modelQuantized && m_input_tensor->type != kTfLiteUInt8) {
		printf("Detection model input should be kTfLiteUInt8!");
		return;
	}

	if (!m_modelQuantized && m_input_tensor->type != kTfLiteFloat32) {
		printf("Detection model input should be kTfLiteFloat32!");
		return;
	}
        
        if (m_input_tensor->dims->data[0] != 1)
        {
         printf("Detection model error\n");
         return;
        }

        model_resize_height=m_input_tensor->dims->data[1];
        model_resize_width=m_input_tensor->dims->data[2];
        model_resize_channels=m_input_tensor->dims->data[3];

	// Find output tensors.
	if (TfLiteInterpreterGetOutputTensorCount(m_interpreter) != 4) {
		printf("Detection model graph needs to have 4 and only 4 outputs!");
		return;
	}


         const char * OutputName= TfLiteTensorName(TfLiteInterpreterGetOutputTensor(m_interpreter, 0));
         //printf("name %s\n",OutputName);

        if (strcmp(OutputName, "StatefulPartitionedCall:1") == 0)
         {
	  m_output_locations = TfLiteInterpreterGetOutputTensor(m_interpreter, 1);
	  m_output_classes = TfLiteInterpreterGetOutputTensor(m_interpreter, 3);
	  m_output_scores = TfLiteInterpreterGetOutputTensor(m_interpreter, 0);
	  m_num_detections = TfLiteInterpreterGetOutputTensor(m_interpreter, 2);
         }
        else
         {
    	  m_output_locations = TfLiteInterpreterGetOutputTensor(m_interpreter, 0);
	  m_output_classes = TfLiteInterpreterGetOutputTensor(m_interpreter, 1);
	  m_output_scores = TfLiteInterpreterGetOutputTensor(m_interpreter, 2);
	  m_num_detections = TfLiteInterpreterGetOutputTensor(m_interpreter, 3);
         }

}

DetectResult* ObjectDetector::detect(Mat src) {
	DetectResult* res = new DetectResult[DETECT_NUM];
	if (m_model == nullptr) {
		return res;
	}

	Mat image;
	resize(src, image, Size(model_resize_width, model_resize_height), 0, 0, INTER_AREA);
	int cnls = image.type();
	if (cnls == CV_8UC1) {
		cvtColor(image, image, COLOR_GRAY2RGB);
	}
	else if (cnls == CV_8UC3) {
		cvtColor(image, image, COLOR_BGR2RGB);
	}
	else if (cnls == CV_8UC4) {
		cvtColor(image, image, COLOR_BGRA2RGB);
	}

	if (m_modelQuantized) {
		// Copy image into input tensor
		uchar* dst = m_input_tensor->data.uint8;
		memcpy(dst, image.data,
			sizeof(uchar) * model_resize_width * model_resize_height * model_resize_channels);
	}
	else {
		// Normalize the image based on std and mean (p' = (p-mean)/std)
		Mat fimage;
		image.convertTo(fimage, CV_32FC3, 1 / IMAGE_STD, -IMAGE_MEAN / IMAGE_STD);

		// Copy image into input tensor
		float* dst = m_input_tensor->data.f;
		memcpy(dst, fimage.data,
			sizeof(float) * model_resize_width * model_resize_height * model_resize_channels);
	}

	if (TfLiteInterpreterInvoke(m_interpreter) != kTfLiteOk) {
		printf("Error invoking detection model");
		return res;
	}

	const float* detection_locations = m_output_locations->data.f;
	const float* detection_classes = m_output_classes->data.f;
	const float* detection_scores = m_output_scores->data.f;
	const int num_detections = (int)* m_num_detections->data.f;

	for (int i = 0; i < num_detections && i < DETECT_NUM; ++i) {
		res[i].score = detection_scores[i];
		res[i].label = (int)detection_classes[i];

		// Get the bbox, make sure its not out of the image bounds, and scale up to src image size
		res[i].ymin = std::fmax(0.0f, detection_locations[4 * i] * src.rows);
		res[i].xmin = std::fmax(0.0f, detection_locations[4 * i + 1] * src.cols);
		res[i].ymax = std::fmin(float(src.rows - 1), detection_locations[4 * i + 2] * src.rows);
		res[i].xmax = std::fmin(float(src.cols - 1), detection_locations[4 * i + 3] * src.cols);
	}

	return res;
}
