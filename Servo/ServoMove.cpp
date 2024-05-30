#include <stdint.h>
#include <stdio.h>
#include <stdexcept>
#include <time.h>
#include <unistd.h>
#include <iostream>

#include "ServoPi.h"

int main(int argc, char **argv)
{
	// initialise a servo object with an I2C address of 0x40 and the Output Enable pin enabled.
	Servo servo(0x40, 0.750, 2.250);
	//servo.set_frequency(50);

	while (1)
	{
		servo.angle(1, 0.0); 		
                usleep(2000000);	  // sleep 2 seconds
		servo.angle(1, -90.0); 		
                usleep(2000000);	  // sleep 2 seconds
		servo.angle(1, 90.0); 		
                usleep(2000000);	  // sleep 2 seconds
	}

	(void)argc;
	(void)argv;
	return (0);
}
