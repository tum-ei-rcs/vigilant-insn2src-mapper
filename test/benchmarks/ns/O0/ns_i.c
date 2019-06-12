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
/* $Id: ns.c,v 1.2 2005/04/04 11:34:58 csg Exp $ */

/* Test of deeply nested loops and non-local exits */


/*-------------------------------------------------- *
 * LOG:
 *  $Log: ns.c,v $
 *  Revision 1.2  2005/04/04 11:34:58  csg
 *  again
 *
 *  Revision 1.1  2005/03/29 11:28:43  jgn
 *  New file.
 *
 *  Revision 1.8  2001/05/07 10:05:37  ijae
 *  no message
 *
 *  Revision 1.7  2001/04/25 12:48:15  ijae
 *  Corrected trace names.
 *
 *  Revision 1.6  2001/04/25 12:17:47  ijae
 *  no message
 *
 *  Revision 1.5  2001/04/25 12:11:31  ijae
 *  Compilable for V850
 *
 *  Revision 1.4  2001/04/25 12:09:55  ijae
 *  Now in target mode.
 *
 *  Revision 1.3  2001/04/25 12:06:36  ijae
 *  Now 4D array. Compiles & runs on PC
 *
 *  Revision 1.2  2001/04/25 11:59:38  ijae
 *  A bit more comments.
 *
 *-------------------------------------------------- */


/* -------------------------------------------------- *
 *  Define TEST to check the # iterations in inner loop,
 *  and that the right value is found and returned
 * -------------------------------------------------- */

//#define TEST

/* --------------------------------------------------
 *  Array of keys and values, 4-dimensional just
 *  for the fun of it.
 * -------------------------------------------------- */
int keys[5][5][5][5] =
{
  // [0]
  {
    // [0][0]
    {
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0}
    },
    // [0][1]
    {
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0}
    },
    // [0][2]
    {
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0}
    },
    // [0][3]
    {
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0}
    },
    // [0][4]
    {
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0},
      {0,0,0,0,0}
    }
  },
  // [1]
  {
    // [1][0]
    {
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1}
    },
    // [1][1]
    {
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1}
    },
    // [1][2]
    {
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1}
    },
    // [1][3]
    {
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1}
    },
    // [1][4]
    {
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1},
      {1,1,1,1,1}
    }
  },
  // [2]
  {
    // [2][0]
    {
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2}
    },
    // [2][1]
    {
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2}
    },
    // [2][2]
    {
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2}
    },
    // [2][3]
    {
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2}
    },
    // [2][4]
    {
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2},
      {2,2,2,2,2}
    }
  },
  // [3]
  {
    // [3][0]
    {
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3}
    },
    // [3][1]
    {
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3}
    },
    // [3][2]
    {
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3}
    },
    // [3][3]
    {
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3}
    },
    // [3][4]
    {
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3},
      {3,3,3,3,3}
    }
  },
  // [4]
  {
    // [4][0]
    {
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4}
    },
    // [4][1]
    {
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4}
    },
    // [4][2]
    {
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4}
    },
    // [4][3]
    {
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4}
    },
    // [4][4]
    {
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,4},
      {4,4,4,4,
#ifdef FIND_TARGET
       400
#else
       401                      /* not searched for */
#endif
      }
    }
  }
};



int answer[5][5][5][5] =
{
  // [0]
  {
    // [0][0]
    {
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123}
    },
    // [0][1]
    {
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123}
    },
    // [0][2]
    {
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123}
    },
    // [0][3]
    {
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123}
    },
    // [0][4]
    {
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123},
      {123,123,123,123,123}
    }
  },
  // [1]
  {
    // [1][0]
    {
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234}
    },
    // [1][1]
    {
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234}
    },
    // [1][2]
    {
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234}
    },
    // [1][3]
    {
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234}
    },
    // [1][4]
    {
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234},
      {234,234,234,234,234}
    }
  },
  // [2]
  {
    // [2][0]
    {
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345}
    },
    // [2][1]
    {
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345}
    },
    // [2][2]
    {
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345}
    },
    // [2][3]
    {
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345}
    },
    // [2][4]
    {
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345},
      {345,345,345,345}
    }
  },
  // [3]
  {
    // [3][0]
    {
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456}
    },
    // [3][1]
    {
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456}
    },
    // [3][2]
    {
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456}
    },
    // [3][3]
    {
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456}
    },
    // [3][4]
    {
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456},
      {456,456,456,456,456}
    }
  },
  // [4]
  {
    // [4][0]
    {
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567}
    },
    // [4][1]
    {
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567}
    },
    // [4][2]
    {
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567}
    },
    // [4][3]
    {
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567}
    },
    // [4][4]
    {
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,567},
      {567,567,567,567,1111}
    }
  }
};


int foo(int x)
{TIC(137); 
#ifdef TEST
  int c = 0;                    /* counter for innerloop */
#endif
  int i,j,k,l;

  for(i=0; TIC(26), i<5; i++)
    for(j=0 ; TIC(26), j<5 ; j++)
      for(k=0 ; TIC(26), k<5 ; k++)
        for(l=0 ; TIC(8), l<5 ; TIC(76), l++)
        {
#ifdef TEST
          c++;
#endif
          if( keys[i][j][k][l] == x )
            {
#ifdef TEST
              printf("   %d\n",c);
#endif
              return answer[i][j][k][l] + keys[i][j][k][l];
            }
        }
  return -1;
TIC(15); }


void main(void)
{TIC(0); 
#ifdef TEST
  printf("result=%d\n",foo(400));
#else
  TIC(25)/* TODO: missing time from foo */, foo(400);
#endif
}
