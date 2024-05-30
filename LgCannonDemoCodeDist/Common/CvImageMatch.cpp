#include <iostream>
#include <string>
#include <vector>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <errno.h>
#include <opencv2/core/core.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <opencv2/features2d/features2d.hpp>
#include <opencv2/features2d.hpp>
#include "opencv2/video/tracking.hpp"
#include "opencv2/imgproc/imgproc.hpp"
#include "CvImageMatch.h"

#if  defined(_WIN32) || defined(_WIN64)
#ifndef PATH_MAX
#define PATH_MAX _MAX_PATH
#endif
#define realpath(N,R) _fullpath((R),(N),PATH_MAX)
#define sprintf sprintf_s
#endif



#define MIN_DIFF_MATCH       10000  // 12000
#define DEBUG 0

using namespace cv;
using namespace std;


Symbol symbols[NUM_SIGNS];

TDetectedMatches* DetectedMatches = NULL;
int NumMatches = 0;

// static int thresh = 50, N = 11; // Original DP
static int thresh = 50, N = 1;

// helper function:
// finds a cosine of angle between vectors
// from pt0->pt1 and from pt0->pt2
static double angle(Point pt1, Point pt2, Point pt0)
{
    double dx1 = pt1.x - pt0.x;
    double dy1 = pt1.y - pt0.y;
    double dx2 = pt2.x - pt0.x;
    double dy2 = pt2.y - pt0.y;
    return (dx1 * dx2 + dy1 * dy2) / sqrt((dx1 * dx1 + dy1 * dy1) * (dx2 * dx2 + dy2 * dy2) + 1e-10);
}


static void sortCorners(std::vector<cv::Point2f>& corners,
    cv::Point2f center)
{
    std::vector<cv::Point2f> top, bot;

    for (int i = 0; i < corners.size(); i++)
    {
        if (corners[i].y < center.y)
            top.push_back(corners[i]);
        else
            bot.push_back(corners[i]);
    }
    corners.clear();

    if (top.size() == 2 && bot.size() == 2) {
        cv::Point2f tl = top[0].x > top[1].x ? top[1] : top[0];
        cv::Point2f tr = top[0].x > top[1].x ? top[0] : top[1];
        cv::Point2f bl = bot[0].x > bot[1].x ? bot[1] : bot[0];
        cv::Point2f br = bot[0].x > bot[1].x ? bot[0] : bot[1];


        corners.push_back(tl);
        corners.push_back(tr);
        corners.push_back(br);
        corners.push_back(bl);
    }
}

int LoadRefImages(Symbol* symbols) {

    for (int i = 0; i < NUM_SIGNS; i++)
    {
        char filename[1024], name[255];
        sprintf(filename, "%sT%d.jpg", IMAGE_DIR, i);
        sprintf(name, "%d", i);
        symbols[i].img = imread(filename, cv::IMREAD_GRAYSCALE);
        if (!symbols[i].img.data) return -1;
#define REF_IMG_SCALE 0.50
        cv::resize(symbols[i].img, symbols[i].img, cv::Size(), REF_IMG_SCALE, REF_IMG_SCALE);
        threshold(symbols[i].img, symbols[i].img, 100, 255, THRESH_BINARY);
        symbols[i].name = name;
    }
    return 0;

}


void FindTargets(const Mat& image)
{
    Mat pyr, timg, gray0(image.size(), CV_8U), gray;

    NumMatches = 0;
    // down-scale and upscale the image to filter out the noise
    pyrDown(image, pyr, Size(image.cols / 2, image.rows / 2));
    pyrUp(pyr, timg, image.size());
    vector<vector<Point> > contours;

    // find squares in every color plane of the image
    for (int c = 0; c < 3; c++)
    {
        int ch[] = { c, 0 };
        mixChannels(&timg, 1, &gray0, 1, ch, 1);

        // try several threshold levels
        for (int l = 0; l < N; l++)
        {
            // hack: use Canny instead of zero threshold level.
            // Canny helps to catch squares with gradient shading
            if (l == 0)
            {
                // apply Canny. Take the upper threshold from slider
                // and set the lower to 0 (which forces edges merging)
                Canny(gray0, gray, 0, thresh, 5);
                // dilate canny output to remove potential
                // holes between edge segments
                dilate(gray, gray, Mat(), Point(-1, -1));
            }
            else
            {
                // apply threshold if l!=0:
                //     tgray(x,y) = gray(x,y) < (l+1)*255/N ? 255 : 0
                gray = gray0 >= (l + 1) * 255 / N;
            }

            // find contours and store them all as a list
            findContours(gray, contours, RETR_LIST, CHAIN_APPROX_SIMPLE);
            vector<Point> approx;

            // test each contour
            for (size_t i = 0; i < contours.size(); i++)
            {
                // approximate contour with accuracy proportional
                // to the contour perimeter
                approxPolyDP(Mat(contours[i]), approx, arcLength(Mat(contours[i]), true) * 0.02, true);

                // square contours should have 4 vertices after approximation
                // relatively large area (to filter out noisy contours)
                // and be convex.
                // Note: absolute value of an area is used because
                // area may be positive or negative - in accordance with the
                // contour orientation
                double Area = fabs(contourArea(Mat(approx)));
                if (approx.size() == 4 &&
                    (Area > 1000) && (Area < 11000) &&
                    isContourConvex(Mat(approx)))
                {
                    double maxCosine = 0;

                    for (int j = 2; j < 5; j++)
                    {
                        // find the maximum cosine of the angle between joint edges
                        double cosine = fabs(angle(approx[j % 4], approx[j - 2], approx[j - 1]));
                        maxCosine = MAX(maxCosine, cosine);
                    }

                    // if cosines of all angles are small
                    // (all angles are ~90 degree) then write quandrange
                    // vertices to resultant sequence
                    if (maxCosine < 0.3)
                    {
                        Rect SquareCheck = boundingRect(approx);
                        float near1 = (float)SquareCheck.width / (float)SquareCheck.height;

                        if ((near1 > 0.75) && (near1 < 1.25))
                        {
                            std::vector<cv::Point2f> corners;

                            vector<Point>::iterator vertex;
                            vertex = approx.begin();

                            //circle(image, *vertex, 2, Scalar(0, 0, 255), -1, 8, 0);
                            corners.push_back(*vertex);
                            vertex++;
                            //circle(image, *vertex, 2, Scalar(0, 0, 255), -1, 8, 0);
                            corners.push_back(*vertex);
                            vertex++;
                            // circle(image, *vertex, 2, Scalar(0, 0, 255), -1, 8, 0);
                            corners.push_back(*vertex);
                            vertex++;
                            // circle(image, *vertex, 2, Scalar(0, 0, 255), -1, 8, 0);
                            corners.push_back(*vertex);

                            Moments mu;
                            mu = moments(contours[i], false);
                            Point2f center((float)(mu.m10 / mu.m00), (float)(mu.m01 / mu.m00));

                            sortCorners(corners, center);
                            if (corners.size() != 0)
                            {
                                Mat new_image;

                                //cv::rectangle(image, corners[0], corners[2], Scalar(10, 255, 0), 2);


                                 // Define the destination image
                                Mat correctedImg = ::Mat::zeros(symbols[0].img.rows, symbols[0].img.cols, CV_8UC3);

                                // Corners of the destination image
                                std::vector<cv::Point2f> quad_pts;
                                quad_pts.push_back(Point2f(0, 0));
                                quad_pts.push_back(Point2f((float)correctedImg.cols, 0));
                                quad_pts.push_back(
                                    Point2f((float)correctedImg.cols, (float)correctedImg.rows));
                                quad_pts.push_back(Point2f(0, (float)correctedImg.rows));

                                // Get transformation matrix
                                Mat transmtx = getPerspectiveTransform(corners, quad_pts);

                                // Apply perspective transformation
                                warpPerspective(image, correctedImg, transmtx,
                                    correctedImg.size());

                                cvtColor(correctedImg, new_image, cv::COLOR_RGB2GRAY);

#if 0
                                double minVal, maxVal, medVal;


                                minMaxLoc(new_image, &minVal, &maxVal);

                                medVal = (maxVal - minVal) / 2;

                                medVal *= 1.3;
                                //printf("medVal %lf\n", medVal);

                                threshold(new_image, new_image, medVal, 255, THRESH_BINARY);
#else
                                threshold(new_image, new_image, 0, 255, THRESH_BINARY + THRESH_OTSU);
#endif
                                // printf("start\n");
                                // imshow("Debug", new_image);
                                // waitKey(0);


                                Mat diffImg;
                                int match, minDiff, diff;
                                minDiff = INT_MAX;
                                match = -1;

                                for (int i = 0; i < NUM_SIGNS; i++)
                                {
                                    bitwise_xor(new_image, symbols[i].img, diffImg,
                                        noArray());
                                    diff = countNonZero(diffImg);
                                    if (diff < minDiff)
                                    {
                                        minDiff = diff;
                                        match = i;
                                    }
                                }

                                if ((match != -1) && (minDiff < MIN_DIFF_MATCH))
                                {
#if DEBUG
                                    printf("Match %d minDiff %d\n", match, minDiff);
#endif
                                    if (NumMatches == 0)
                                    {
                                        DetectedMatches[NumMatches].center = center;
                                        DetectedMatches[NumMatches].Diff = minDiff;
                                        DetectedMatches[NumMatches].match = match;
                                        DetectedMatches[NumMatches].xmin = corners[0].x;
                                        DetectedMatches[NumMatches].xmax = corners[2].x;
                                        DetectedMatches[NumMatches].ymin = corners[0].y;
                                        DetectedMatches[NumMatches].ymax = corners[2].y;
                                        NumMatches++;
                                    }
                                    else
                                    {
                                        bool found = false;
                                        for (int i = 0; i < NumMatches && i < MAX_DETECTED_MATCHES && !found; ++i)
                                        {
                                            double distance = cv::norm(center - DetectedMatches[i].center);
                                            if (distance < 5.00)
                                            {
                                                if (DetectedMatches[i].Diff > minDiff)
                                                {
                                                    if (DetectedMatches[i].match != match)
                                                        printf("Target Change\n");
                                                    DetectedMatches[i].center = center;
                                                    DetectedMatches[i].Diff = minDiff;
                                                    DetectedMatches[i].match = match;
                                                    DetectedMatches[i].xmin = corners[0].x;
                                                    DetectedMatches[i].xmax = corners[2].x;
                                                    DetectedMatches[i].ymin = corners[0].y;
                                                    DetectedMatches[i].ymax = corners[2].y;
#if DEBUG
                                                    printf("Updated %d\n", match);
#endif
                                                }
                                                found = true;
                                            }
                                        }
                                        if ((!found) && (NumMatches < MAX_DETECTED_MATCHES))
                                        {
                                            DetectedMatches[NumMatches].center = center;
                                            DetectedMatches[NumMatches].Diff = minDiff;
                                            DetectedMatches[NumMatches].match = match;
                                            DetectedMatches[NumMatches].xmin = corners[0].x;
                                            DetectedMatches[NumMatches].xmax = corners[2].x;
                                            DetectedMatches[NumMatches].ymin = corners[0].y;
                                            DetectedMatches[NumMatches].ymax = corners[2].y;
                                            NumMatches++;
                                        }

                                    }

                                }
#if DEBUG
                                else  printf("No Match minDiff %d\n", minDiff);
#endif
                            }
                            else  printf("out near %f w %d h %d\n", near1, SquareCheck.width, SquareCheck.height);


                        }
                    }
                }
            }
        }
    }

}

void DrawTargets(Mat src)
{
    for (int i = 0; i < NumMatches; ++i)
    {
        int match = DetectedMatches[i].match;
        int xmin = (int)DetectedMatches[i].xmin;
        int xmax = (int)DetectedMatches[i].xmax;
        int ymin = (int)DetectedMatches[i].ymin;
        int ymax = (int)DetectedMatches[i].ymax;
        int baseline = 0;

        cv::rectangle(src, Point(xmin, ymin), Point(xmax, ymax), Scalar(10, 255, 0), 2);
        cv::String label = symbols[match].name;

        Size labelSize = cv::getTextSize(label, cv::FONT_HERSHEY_SIMPLEX, 0.7, 2, &baseline); // Get font size
        int label_ymin = (std::max)((int)ymin, (int)(labelSize.height + 10)); // Make sure not to draw label too close to top of window
        rectangle(src, Point(xmin, label_ymin - labelSize.height - 10), Point(xmin + labelSize.width, label_ymin + baseline - 10), Scalar(255, 255, 255), cv::FILLED); // Draw white box to put label text in
        putText(src, label, Point(xmin, label_ymin - 7), cv::FONT_HERSHEY_SIMPLEX, 0.7, Scalar(0, 0, 0), 2); // Draw label text
    }
#if DEBUG
    printf("Matches was %d\n", NumMatches);
#endif
}

int compare(const void* s1, const void* s2)
{
    struct NDetectedMatches * m1 = (struct NDetectedMatches*)s1;
    struct NDetectedMatches * m2 = (struct NDetectedMatches*)s2;
    return m1->match - m2->match;
}

void WriteFile(const  char* path, const char* folder, const char* filename, char * ext, const cv::Mat src)
{

    FILE* f;
    char PathFilename_xml[PATH_MAX];
    char PathFilename_jpg[PATH_MAX];
    char FullPath[PATH_MAX];

    sprintf(PathFilename_xml, "%s%s/%s.xml",path,folder, filename);
    sprintf(PathFilename_jpg, "%s%s/%s.%s", path, folder, filename,ext);
#if DEBUG
    printf("%s\n", PathFilename_jpg);
#endif
#if  defined(_WIN32) || defined(_WIN64)
    errno_t err;
    err=fopen_s(&f, PathFilename_xml, "w");
    if (err != 0)
    {
        printf("Error opening file!\n");
        exit(1);
    }
#else
    if ((f=fopen(PathFilename_xml, "w"))==NULL)
     {
        printf("Error opening file!\n");
        exit(1);
     }   
#endif

    if (realpath(PathFilename_jpg, FullPath) == NULL)
    {
        printf("FULL Path Failire\n");
        exit(1);
    }
    const char* header= "<annotation>\n"
                        "\t<folder>%s</folder>\n"
                        "\t<filename>%s.%s</filename>\n"
                        "\t<path>%s</path>\n"
                        "\t<source>\n"
                        "\t\t<database>%s</database>\n"
                        "\t</source>\n"
                        "\t<size>\n"
                        "\t\t<width>%d</width>\n"
                        "\t\t<height>%d</height>\n"
                        "\t\t<depth>%d</depth>\n"
                        "\t</size>\n"
                        "\t<segmented>%d</segmented>\n";

    fprintf(f, header, folder, filename,ext, FullPath,"Unknown",src.cols, src.rows, src.channels(), 0);


    const char* body = "\t<object>\n"
                       "\t\t<name>%s</name>\n"
                       "\t\t<pose>%s</pose>\n"
                       "\t\t<truncated>%d</truncated>\n"
                       "\t\t<difficult>%d</difficult>\n"
                       "\t\t<bndbox>\n"
                       "\t\t\t<xmin>%d</xmin>\n"
                       "\t\t\t<ymin>%d</ymin>\n"
                       "\t\t\t<xmax>%d</xmax>\n"
                       "\t\t\t<ymax>%d</ymax>\n"
                       "\t\t</bndbox>\n"
                       "\t</object>\n";

    qsort(DetectedMatches, NumMatches, sizeof(struct NDetectedMatches), compare);

        for (int i = 0; i < NumMatches; ++i)
        {
            char name[256];

            int match = DetectedMatches[i].match;
            int xmin = (int)DetectedMatches[i].xmin;
            int xmax = (int)DetectedMatches[i].xmax;
            int ymin = (int)DetectedMatches[i].ymin;
            int ymax = (int)DetectedMatches[i].ymax;
            sprintf(name, "%d", match);

            fprintf(f, body, name,"Unspecified",0,0, xmin, ymin, xmax, ymax);
        }


    const char* trail = "</annotation>\n";

    fprintf(f, trail);
    fclose(f);
}
