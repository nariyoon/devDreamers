#ifndef CvImageMatchH
#define CvImageMatchH

#if  defined(_WIN32) || defined(_WIN64)
#define IMAGE_DIR "..\\..\\..\\Targets\\"
#else
#define IMAGE_DIR "../Targets/"
#endif

#define NUM_SIGNS            10
#define MAX_DETECTED_MATCHES 20


class Symbol
{
public:
    cv::Mat img;
    std::string name;
};

typedef struct NDetectedMatches
{
    int     match = -1;
    int     Diff = -1;
    cv::Point2f center = { 0,0 };
    float   ymin = 0.0;
    float   xmin = 0.0;
    float   ymax = 0.0;
    float   xmax = 0.0;
} TDetectedMatches;

extern Symbol symbols[NUM_SIGNS];
extern TDetectedMatches* DetectedMatches;
extern int NumMatches;

int LoadRefImages(Symbol* symbols);
void DrawTargets(cv::Mat src);
void FindTargets(const cv::Mat& image);
void WriteFile(const  char* path, const char* folder, const char* filename,char* ext, const cv::Mat src);
#endif
