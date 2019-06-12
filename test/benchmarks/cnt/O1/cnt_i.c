/* Time-annotations by cbb-analyzer 
 * Using WCET library for target Atmega128 from 2018-02-16_13:40:25
 */
#ifdef WCETREPLAY
  #define EXTRA_INSTRUCTION __asm__("nop");
#else
  #define EXTRA_INSTRUCTION /* nada */
#endif
#define TIC(X) ({timeElapsed += (X); EXTRA_INSTRUCTION})

unsigned long timeElapsed = 0;
/* $Id: cnt.c,v 1.3 2005/04/04 11:34:58 csg Exp $ */

/* sumcntmatrix.c */

//#include <sys/types.h>
//#include <sys/times.h>

// #define WORSTCASE 1
// #define MAXSIZE 100 Changed JG/Ebbe
#define MAXSIZE 10

// Typedefs
typedef int matrix [MAXSIZE][MAXSIZE];

// Forwards declarations
int main(void);
int Test(matrix);
int Initialize(matrix);
int InitSeed(void);
void Sum(matrix);
int RandomInteger(void);

// Globals
int Seed;
matrix Array;
int Postotal, Negtotal, Poscnt, Negcnt;

// The main function
int main (void)
{TIC(0); 
   TIC(20)/* TODO: missing time from Test */, InitSeed();
   //printf("\n   *** MATRIX SUM AND COUNT BENCHMARK TEST ***\n\n");
   //printf("RESULTS OF THE TEST:\n");
   Test(Array);
   return 1;
}


int Test(matrix Array)
{TIC(0); 
   TIC(32)/* TODO: missing time from Initialize */; long StartTime, StopTime;
   float TotalTime;

   Initialize(Array);
   StartTime = 1000.0; //ttime();
   Sum(Array);
   StopTime = 1500.0; //ttime();

   TotalTime = (StopTime - StartTime) / 1000.0;

   //printf("    - Size of array is %d\n", MAXSIZE);
   //printf("    - Num pos was %d and Sum was %d\n", Poscnt, Postotal);
   //printf("    - Num neg was %d and Sum was %d\n", Negcnt, Negtotal);
   //printf("    - Num neg was %d\n", Negcnt);
   //printf("    - Total sum time is %3.3f seconds\n\n", TotalTime);
   return 0;
}


// Intializes the given array with random integers.
int Initialize(matrix Array)
{TIC(0); 
   register int OuterIndex, InnerIndex;

   for (OuterIndex = 0; TIC(7), OuterIndex < MAXSIZE; OuterIndex++) //100 + 1
      for (InnerIndex = 0; TIC(16)/* TODO: missing time from RandomInteger */, InnerIndex < MAXSIZE; InnerIndex++) //100 + 1
         Array[OuterIndex][InnerIndex] = RandomInteger();

   TIC(35); return 0;
}


// Initializes the seed used in the random number generator.
int InitSeed (void)
{
   Seed = 0;
   return 0;
}

void Sum(matrix Array)
{TIC(0); 
  register int Outer, Inner;

  int Ptotal = 0; /* changed these to locals in order to drive worst case */
  int Ntotal = 0;
  int Pcnt = 0;
  int Ncnt = 0;

  for (Outer = 0; TIC(11), Outer < MAXSIZE; Outer++) //Maxsize = 100
    for (Inner = 0; TIC(7), Inner < MAXSIZE; TIC(4), Inner++)
#ifdef WORSTCASE
      if (Array[Outer][Inner] >= 0) {
#else
	if (Array[Outer][Inner] < 0) {
#endif
	  TIC(4), Ptotal += Array[Outer][Inner];
	  Pcnt++;
	}
	else {
	  TIC(6), Ntotal += Array[Outer][Inner];
	  Ncnt++;
	}

  TIC(52), Postotal = Ptotal;
  Poscnt = Pcnt;
  Negtotal = Ntotal;
  Negcnt = Ncnt;
}


// This function returns in milliseconds the amount of compiler time
//int ttime()
//{
//  struct tms buffer;
//int utime;

//times(&buffer);
//utime = (buffer.tms_utime / 60.0) * 1000.0;
//return (utime);
//}


// Generates random integers between 0 and 8095
int RandomInteger(void)
{TIC(0); 
   TIC(225), Seed = ((Seed * 133) + 81) % 8095;
   return Seed;
}





