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
static int swi(int c) {TIC(0); 
    switch (TIC(42), c) {
        case 0: TIC(4); return 42;
        case 1: TIC(4); return 43;
        case 2: TIC(4); return 44;
        case 3: TIC(4); return 45;
        default: break;
    }
    TIC(12); 
    return -1;
}


int main() {TIC(0); 
    TIC(41)/* TODO: missing time from swi */; volatile int k;
    k=swi(k);
    return k;
}
