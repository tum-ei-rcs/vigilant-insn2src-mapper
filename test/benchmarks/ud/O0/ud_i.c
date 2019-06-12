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
/* MDH WCET BENCHMARK SUITE. File version $Id: ud.c,v 1.4 2005/11/11 10:32:53 ael01 Exp $ */


/*************************************************************************/
/*                                                                       */
/*   SNU-RT Benchmark Suite for Worst Case Timing Analysis               */
/*   =====================================================               */
/*                              Collected and Modified by S.-S. Lim      */
/*                                           sslim@archi.snu.ac.kr       */
/*                                         Real-Time Research Group      */
/*                                        Seoul National University      */
/*                                                                       */
/*                                                                       */
/*        < Features > - restrictions for our experimental environment   */
/*                                                                       */
/*          1. Completely structured.                                    */
/*               - There are no unconditional jumps.                     */
/*               - There are no exit from loop bodies.                   */
/*                 (There are no 'break' or 'return' in loop bodies)     */
/*          2. No 'switch' statements.                                   */
/*          3. No 'do..while' statements.                                */
/*          4. Expressions are restricted.                               */
/*               - There are no multiple expressions joined by 'or',     */
/*                'and' operations.                                      */
/*          5. No library calls.                                         */
/*               - All the functions needed are implemented in the       */
/*                 source file.                                          */
/*                                                                       */
/*                                                                       */
/*************************************************************************/
/*                                                                       */
/*  FILE: ludcmp.c                                                       */
/*  SOURCE : Turbo C Programming for Engineering                         */
/*                                                                       */
/*  DESCRIPTION :                                                        */
/*                                                                       */
/*     Simultaneous linear equations by LU decomposition.                */
/*     The arrays a[][] and b[] are input and the array x[] is output    */
/*     row vector.                                                       */
/*     The variable n is the number of equations.                        */
/*     The input arrays are initialized in function main.                */
/*                                                                       */
/*                                                                       */
/*  REMARK :                                                             */
/*                                                                       */
/*  EXECUTION TIME :                                                     */
/*                                                                       */
/*                                                                       */
/*************************************************************************/

/*************************************************************************
 *  This file:
 *
 *  - Name changed to "ud.c"
 *  - Modified for use with Uppsala/Paderborn tool
 *    : doubles changed to int
 *    : some tests removed
 *  - Program is much more linear, all loops will run to end
 *  - Purpose: test the effect of conditional flows
 *
 *************************************************************************/






/*
** Benchmark Suite for Real-Time Applications, by Sung-Soo Lim
**
**    III-4. ludcmp.c : Simultaneous Linear Equations by LU Decomposition
**                 (from the book C Programming for EEs by Hyun Soon Ahn)
*/



long int a[50][50], b[50], x[50];

int ludcmp(int nmax, int n);


/*  static double fabs(double n) */
/*  { */
/*    double f; */

/*    if (n >= 0) f = n; */
/*    else f = -n; */
/*    return f; */
/*  } */

void main()
{TIC(0); 
  int      i, j, nmax = 50, n = 5, chkerr;
  long int /* eps, */ w;

  /* eps = 1.0e-6; */

  /* Init loop */
  for(i = 0; TIC(66), i <= n; i++)
    {
      w = 0.0;              /* data to fill in cells */
      for(j = 0; TIC(143), j <= n; j++)
        {
          a[i][j] = (i + 1) + (j + 1);
          if(i == j)            /* only once per loop pass */
            TIC(607), a[i][j] *= 2.0;
          w += a[i][j];
        }
      b[i] = w;
    }

  /*  chkerr = ludcmp(nmax, n, eps); */
  TIC(68)/* TODO: missing time from ludcmp */, chkerr = ludcmp(nmax,n);
}

int ludcmp(int nmax, int n)
{TIC(0); 
  int i, j, k;
  long w, y[100];

  /* if(n > 99 || eps <= 0.0) return(999); */
  for(i = 0; TIC(52), i < n; i++)
    {
      /* if(fabs(a[i][i]) <= eps) return(1); */
      for(j = i+1; TIC(891), j <= n; j++) /* triangular loop vs. i */
        {
          w = a[j][i];
          if(i != 0)            /* sub-loop is conditional, done
                                   all iterations except first of the
                                   OUTER loop */
            for(TIC(6), k = 0; TIC(191), k < i; k++)
              w -= a[j][k] * a[k][i];
          a[j][i] = w / a[i][i];
        }
      for(j = i+1; TIC(121), j <= n; j++) /* triangular loop vs. i */
        {
          w = a[i+1][j];
          for(k = 0; TIC(193), k <= i; k++) /* triangular loop vs. i */
            w -= a[i+1][k] * a[k][j];
          a[i+1][j] = w;
        }
    }
  y[0] = b[0];
  for(i = 1; TIC(94), i <= n; i++)       /* iterates n times */
    {
      w = b[i];
      for(j = 0; TIC(182), j < i; j++)    /* triangular sub loop */
        w -= a[i][j] * y[j];
      y[i] = w;
    }
  x[n] = y[n] / a[n][n];
  for(i = n-1; TIC(862), i >= 0; i--)     /* iterates n times */
    {
      w = y[i];
      for(j = i+1; TIC(181), j <= n; j++) /* triangular sub loop */
        w -= a[i][j] * x[j];
      x[i] = w / a[i][i] ;
    }
  TIC(919); return(0);
}

