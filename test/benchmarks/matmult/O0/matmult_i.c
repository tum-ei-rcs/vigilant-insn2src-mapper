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
/* $Id: matmult.c,v 1.2 2005/04/04 11:34:58 csg Exp $ */

/* matmult.c */
/* was mm.c! */


/*----------------------------------------------------------------------*
 * To make this program compile under our assumed embedded environment,
 * we had to make several changes:
 * - Declare all functions in ANSI style, not K&R.
 *   this includes adding return types in all cases!
 * - Declare function prototypes
 * - Disable all output
 * - Disable all UNIX-style includes
 *
 * This is a program that was developed from mm.c to matmult.c by
 * Thomas Lundqvist at Chalmers.
 *----------------------------------------------------------------------*/
#define UPPSALAWCET 1


/* ***UPPSALA WCET***:
   disable stupid UNIX includes */
#ifndef UPPSALAWCET
#include <sys/types.h>
#include <sys/times.h>
#endif

/*
 * MATRIX MULTIPLICATION BENCHMARK PROGRAM:
 * This program multiplies 2 square matrices resulting in a 3rd
 * matrix. It tests a compiler's speed in handling multidimensional
 * arrays and simple arithmetic.
 */

#define UPPERLIMIT 20

typedef int matrix [UPPERLIMIT][UPPERLIMIT];

int Seed;
matrix ArrayA, ArrayB, ResultArray;

#ifdef UPPSALAWCET
/* Our picky compiler wants prototypes! */
void Multiply(matrix A, matrix B, matrix Res);
void InitSeed(void);
void Test(matrix A, matrix B, matrix Res);
void Initialize(matrix Array);
int RandomInteger(void);
#endif
void main();
void main()
{TIC(0); 
   TIC(37)/* TODO: missing time from InitSeed */, InitSeed();
/* ***UPPSALA WCET***:
   no printing please! */
#ifndef UPPSALAWCET
   printf("\n   *** MATRIX MULTIPLICATION BENCHMARK TEST ***\n\n");
   printf("RESULTS OF THE TEST:\n");
#endif
   Test(ArrayA, ArrayB, ResultArray);
}


void InitSeed(void)
/*
 * Initializes the seed used in the random number generator.
 */
{TIC(0); 
  /* ***UPPSALA WCET***:
     changed Thomas Ls code to something simpler.
   Seed = KNOWN_VALUE - 1; */
  TIC(19), Seed = 0;
}


void Test(matrix A, matrix B, matrix Res)
/*
 * Runs a multiplication test on an array.  Calculates and prints the
 * time it takes to multiply the matrices.
 */
{TIC(0); 
#ifndef UPPSALAWCET
   long StartTime, StopTime;
   float TotalTime;
#endif

   TIC(88)/* TODO: missing time from Initialize */, Initialize(A);
   Initialize(B);

   /* ***UPPSALA WCET***: don't print or time */
#ifndef UPPSALAWCET
   StartTime = ttime ();
#endif

   Multiply(A, B, Res);

   /* ***UPPSALA WCET***: don't print or time */
#ifndef UPPSALAWCET
   StopTime = ttime();
   TotalTime = (StopTime - StartTime) / 1000.0;
   printf("    - Size of array is %d\n", UPPERLIMIT);
   printf("    - Total multiplication time is %3.3f seconds\n\n", TotalTime);
#endif
}


void Initialize(matrix Array)
/*
 * Intializes the given array with random integers.
 */
{TIC(0); 
   int OuterIndex, InnerIndex;

   for (OuterIndex = 0; TIC(8), OuterIndex < UPPERLIMIT; TIC(16), OuterIndex++)
      for (InnerIndex = 0; TIC(8), InnerIndex < UPPERLIMIT; TIC(51)/* TODO: missing time from RandomInteger */, InnerIndex++)
         Array[OuterIndex][InnerIndex] = RandomInteger();
TIC(49); }


int RandomInteger(void)
/*
 * Generates random integers between 0 and 8095
 */
{TIC(0); 
   TIC(240), Seed = ((Seed * 133) + 81) % 8095;
   return (Seed);
}


#ifndef UPPSALAWCET
int ttime()
/*
 * This function returns in milliseconds the amount of compiler time
 * used prior to it being called.
 */
{
   struct tms buffer;
   int utime;

   /*   times(&buffer);   times not implemented */
   utime = (buffer.tms_utime / 60.0) * 1000.0;
   return (utime);
}
#endif

void Multiply(matrix A, matrix B, matrix Res)
/*
 * Multiplies arrays A and B and stores the result in ResultArray.
 */
{TIC(0); 
   register int Outer, Inner, Index;

   for (Outer = 0; TIC(14), Outer < UPPERLIMIT; Outer++)
      for (Inner = 0; TIC(37), Inner < UPPERLIMIT; Inner++)
      {
         Res [Outer][Inner] = 0;
         for (Index = 0; TIC(122), Index < UPPERLIMIT; Index++)
            Res[Outer][Inner]  +=
               A[Outer][Index] * B[Index][Inner];
       }
TIC(71); }
